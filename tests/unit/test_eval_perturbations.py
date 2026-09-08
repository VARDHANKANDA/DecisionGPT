"""Unit tests for backend/app/evaluation/perturbations.py (Phase 2). Pure module."""
import copy

import pytest

from app.evaluation import perturbations as pz
from app.evaluation import scenario_families as sf


def _hist_constraints():
    s = sf.generate_suite(len(sf.FAMILY_IDS), master_seed=1)[0]
    return (copy.deepcopy(sf.realise_history(s, s.seed)),
            copy.deepcopy(s.constraints), copy.deepcopy(s.params))


def test_every_perturbation_registered_and_callable():
    assert len(pz.PERTURBATIONS) >= 10
    h, c, _ = _hist_constraints()
    for name in pz.PERTURBATIONS:
        nh, nc, meta = pz.apply(name, h, c, 0.5, seed=7)
        assert isinstance(nh, dict) and isinstance(nc, dict)
        assert meta["kind"] == name and meta["severity"] == 0.5


def test_severity_bounds_enforced():
    h, c, _ = _hist_constraints()
    with pytest.raises(ValueError):
        pz.apply("input_noise", h, c, 1.5, seed=1)
    with pytest.raises(ValueError):
        pz.apply("input_noise", h, c, -0.1, seed=1)
    with pytest.raises(KeyError):
        pz.apply("does_not_exist", h, c, 0.5, seed=1)


def test_perturbations_only_touch_observed_data_not_ground_truth_params():
    s = sf.generate_suite(20, master_seed=3)[5]
    params_before = copy.deepcopy(s.params)
    hist = sf.realise_history(s, s.seed)
    for name in pz.PERTURBATIONS:
        nh, nc, _ = pz.apply(name, hist, s.constraints, 1.0, seed=11)
        # the perturbation returns NEW history/constraints and never mutates params
        assert s.params == params_before
        assert nh is not hist and nc is not s.constraints


def test_missing_values_shrinks_and_keeps_arrays_aligned():
    h, c, _ = _hist_constraints()
    n0 = len(h["units"])
    nh, _, meta = pz.apply("missing_values", h, c, 0.8, seed=2)
    assert meta["kept"] <= n0
    L = len(nh["units"])
    for k in ("day_offsets", "price", "marketing_spend"):
        assert len(nh[k]) == L
    assert nh["days"] == L


def test_length_preserving_perturbations_keep_series_length():
    h, c, _ = _hist_constraints()
    n0 = len(h["units"])
    for name in ("input_noise", "forecast_error_bias", "uncertainty_inflation",
                 "distribution_shift", "contradictory_signals", "extreme_but_feasible", "adversarial"):
        nh, _, _ = pz.apply(name, h, c, 0.5, seed=4)
        assert len(nh["units"]) == n0 and len(nh["price"]) == n0


def test_constraint_tighten_and_relax_move_caps_the_right_way():
    h = {"day_offsets": [0, 1], "price": [10.0, 10.0], "units": [5.0, 5.0], "marketing_spend": [100.0, 100.0]}
    c = {"cash_cap": 200.0, "inventory_cap": 100.0, "price_ceiling_pct": 10.0}
    _, ct, _ = pz.apply("constraint_tighten", h, c, 1.0, seed=1)
    _, cr, _ = pz.apply("constraint_relax", h, c, 1.0, seed=1)
    assert ct["cash_cap"] < c["cash_cap"] < cr["cash_cap"]
    assert ct["inventory_cap"] < c["inventory_cap"] < cr["inventory_cap"]


def test_adversarial_compresses_price_range():
    h = {"day_offsets": list(range(6)), "price": [8.0, 12.0, 9.0, 11.0, 7.0, 13.0],
         "units": [5.0] * 6, "marketing_spend": [100.0] * 6}
    nh, _, meta = pz.apply("adversarial", h, {}, 1.0, seed=1)
    assert (max(nh["price"]) - min(nh["price"])) < (max(h["price"]) - min(h["price"]))
    assert "median" in meta["note"]


def test_degradation_curve_math():
    dc = pz.degradation_curve({0.0: 1.0, 0.5: 0.7, 1.0: 0.4}, higher_is_better=True)
    assert dc["baseline"] == 1.0
    assert dc["degradation"] == [0.0, pytest.approx(0.3), pytest.approx(0.6)]
    assert dc["severity_at_50pct_degradation"] == 1.0
    assert dc["auc_degradation"] > 0
