"""Unit tests for backend/app/evaluation/mechanism.py (Phase 2). Pure module."""
import numpy as np
import pytest

from app.evaluation import mechanism as mech
from app.evaluation import scenario_families as sf


def test_extract_factors_returns_every_named_factor_with_sane_ranges():
    for s in sf.generate_suite(51, master_seed=20260906):
        f = mech.extract_factors(s)
        for name in mech.FACTOR_NAMES:
            assert name in f, f"{s.scenario_id} missing factor {name}"
        assert 0.0 <= f["uncertainty"] <= 3.0
        assert 0.0 <= f["constraint_tightness"] <= 1.0
        assert 0.0 <= f["risk_exposure"] <= 1.0
        assert f["action_space_size"] >= 3
        assert f["prediction_error"] is None          # pre-run
        assert f["agent_disagreement"] is None        # pre-run
        assert f["risk_exposure_source"] == "analytic_R0_proxy"


def test_constraint_tightness_reflects_binding_constraints():
    suite = sf.generate_suite(60, master_seed=20260906)
    by_fam = {}
    for s in suite:
        by_fam.setdefault(s.family_id, mech.extract_factors(s)["constraint_tightness"])
    # a family with a tight inventory cap should score higher than an unconstrained one
    assert by_fam["inventory_constraint"] > by_fam["demand_uncertainty"]
    assert by_fam["cash_constraint"] > by_fam["demand_uncertainty"]


def test_adversarial_family_has_high_risk_exposure_proxy():
    suite = sf.generate_suite(60, master_seed=20260906)
    adv = [mech.extract_factors(s)["risk_exposure"] for s in suite if s.family_id == "adversarial_risk_trap"]
    price_unc = [mech.extract_factors(s)["risk_exposure"] for s in suite if s.family_id == "price_uncertainty"]
    assert max(adv) >= 0.9                       # constant price history -> any move overshoots
    assert np.mean(adv) > np.mean(price_unc)


def test_objective_conflict_zero_when_aligned_positive_when_reversed():
    suite = sf.generate_suite(60, master_seed=20260906)
    # competing_objectives family is constructed so revenue-optimal != profit-optimal
    conf = [mech.extract_factors(s)["objective_conflict"] for s in suite if s.family_id == "competing_objectives"]
    aligned = [mech.extract_factors(s)["objective_conflict"] for s in suite if s.family_id == "demand_uncertainty"]
    assert np.mean(conf) > np.mean(aligned)


def test_merge_run_factors_folds_in_post_run_quantities():
    s = sf.generate_suite(len(sf.FAMILY_IDS), master_seed=1)[0]
    pre = mech.extract_factors(s)
    merged = mech.merge_run_factors(pre, prediction_error=0.12, agent_disagreement=0.03,
                                    real_risk_score=0.8)
    assert merged["prediction_error"] == 0.12
    assert merged["agent_disagreement"] == 0.03
    assert merged["risk_exposure"] == 0.8
    assert merged["risk_exposure_source"] == "digital_twin_risk_score"


def test_interaction_analysis_returns_coefficients_with_cis_and_a_non_causal_note():
    rng = np.random.default_rng(0)
    factors, contrast = {}, {}
    for i in range(24):
        sid = f"s{i:02d}"
        u = float(rng.uniform(0, 1))
        ct = float(rng.uniform(0, 1))
        factors[sid] = {"uncertainty": u, "constraint_tightness": ct, "objective_conflict": 0.1,
                        "prediction_error": 0.2, "risk_exposure": 0.3,
                        "action_space_size": 8.0, "agent_disagreement": 0.05}
        # contrast increases with constraint tightness by construction
        contrast[sid] = 0.4 * ct - 0.1 * u + float(rng.normal(0, 0.02))
    res = mech.interaction_analysis(factors, contrast, contrast="D_vs_B")
    assert res["n_scenarios"] == 24
    coeffs = res["ols_coefficients_on_standardised_factors"]
    assert "constraint_tightness" in coeffs and len(coeffs["constraint_tightness"]["ci95"]) == 2
    assert coeffs["constraint_tightness"]["beta"] > coeffs["uncertainty"]["beta"]
    assert "not causal" in res["note"]
    assert "constraint_tightness" in res["tertile_contrast_means"]


def test_interaction_analysis_degrades_gracefully_on_too_few_scenarios():
    res = mech.interaction_analysis({"s1": {"uncertainty": 0.1}}, {"s1": 0.2}, contrast="D_vs_B")
    assert "insufficient" in res["note"]
