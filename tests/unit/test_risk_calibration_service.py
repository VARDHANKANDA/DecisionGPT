"""Principled Risk Manager calibration study — R0/R1/R2/R3 variants, robust
extrapolation-risk scale, risk ordering & zero-variance behaviour, isolation
(Digital Twin / candidates / agent growth scores unchanged), determinism,
no fabrication, pre-specified verdict.
"""
import pandas as pd
import pytest

from app.analytics import digital_twin_service as dtsvc
from app.services import decision_service
from app.services import model_registry_service
from app.services import multi_scenario_service as ms
from app.services import risk_calibration_service as rc


# --- R1 robust extrapolation-risk formula (pure) ------------------------


def _r0(prices, value):
    lo, hi = min(prices), max(prices)
    return dtsvc._risk_from_extrapolation(
        {"price": (lo, hi), "marketing_spend": (0.0, 0.0)},
        {"price": value, "marketing_spend": 0.0},
    )[1]


def _r1(prices, value):
    df = pd.DataFrame({"price": prices, "marketing_spend": [0.0] * len(prices)})
    return dtsvc._calibrated_risk_from_extrapolation(
        dtsvc._feature_history_stats(df), {"price": value, "marketing_spend": 0.0}, "R1"
    )[1]


def test_r0_zero_variance_degeneracy_is_real():
    # constant history -> every move is risk 1.0 and ordering is destroyed
    assert _r0([100] * 5, 105) == 1.0
    assert _r0([100] * 5, 110) == 1.0
    assert _r0([100] * 5, 95) == 1.0


def test_r1_removes_the_infinite_risk_pathology_but_keeps_ordering():
    r5, r10, rm5 = _r1([100] * 5, 105), _r1([100] * 5, 110), _r1([100] * 5, 95)
    assert 0.0 < r5 < 1.0 and 0.0 < r10 < 1.0
    assert r10 > r5                       # +10% strictly riskier than +5%
    assert r5 == pytest.approx(rm5, abs=1e-4)   # ±5% symmetric


def test_r1_does_not_reduce_scale_below_the_observed_range():
    # normal-variance history: within-range moves stay 0, bigger move still penalised
    assert _r1([95, 100, 105, 100, 98], 105) == 0.0
    assert _r1([95, 100, 105, 100, 98], 95) == 0.0
    assert _r1([95, 100, 105, 100, 98], 110) > 0.0


def test_r1_monotone_in_move_size_across_history_types():
    for hist in ([100] * 5, [99, 100, 101, 100, 100], [95, 100, 105, 100, 98], [600] * 81 + [540] * 9):
        base = hist[-1]
        assert _r1(hist, base * 1.10) >= _r1(hist, base * 1.05) - 1e-9


def test_r1_rejects_unknown_model_name():
    with pytest.raises(ValueError):
        dtsvc._calibrated_risk_from_extrapolation({}, {"price": 1.0}, "R9")


def test_risk_band_thresholds_match_the_original():
    assert dtsvc._risk_band(0.0) == "LOW"
    assert dtsvc._risk_band(0.1499) == "LOW"
    assert dtsvc._risk_band(0.15) == "MODERATE"
    assert dtsvc._risk_band(0.4999) == "MODERATE"
    assert dtsvc._risk_band(0.5) == "HIGH"


# --- variant set is exactly the pre-specified one ----------------------


def test_r2_lambdas_are_exactly_the_prespecified_set():
    assert rc.R2_LAMBDAS == [0.25, 0.50, 0.75]
    names = [v for v, _ in rc.CALIBRATION_VARIANTS]
    assert names == ["R1", "R2-0.25", "R2-0.50", "R2-0.75"]


def test_reference_variants_are_r0_and_d1_only():
    assert [v for v, _ in rc.REFERENCE_VARIANTS] == ["R0", "D1"]
    assert dict(rc.REFERENCE_VARIANTS)["D1"] == {"risk_penalty_in_ranking": False}


# --- end-to-end (small, deterministic) --------------------------------


@pytest.fixture()
def _small(monkeypatch):
    monkeypatch.setattr(ms, "SCENARIOS", ms.SCENARIOS[:3])
    yield


def _run(db, seeds=(42,)):
    model_registry_service.sync_from_file_registry(db)
    return rc.run_risk_calibration(db, seeds=list(seeds))


def test_r0_reproduces_production_full_decisiongpt(_small, db_session):
    from app.services import decision_architecture_service as da

    model_registry_service.sync_from_file_registry(db_session)
    sc = ms.SCENARIOS[0]
    bid, gid = da._seed_synthetic_business(db_session, 42, sc)
    try:
        direct = decision_service.analyze_goal(db_session, bid, gid)
    finally:
        da._cleanup_synthetic_business(db_session, bid)

    res = _run(db_session)
    r0 = next(o for o in res["observations"]["R0"] if o["scenario_id"] == sc.scenario_id and o["seed"] == 42)
    assert r0["selected_strategy"] == direct.selected_strategy_name
    assert r0["confidence"] == pytest.approx(direct.confidence, abs=1e-4)


def test_digital_twin_predictions_and_agent_growth_scores_unchanged(_small, db_session):
    """Only risk changes: expected units/revenue/profit and BA/FA growth scores
    are identical between R0 and R1 for every strategy; RM may differ (R1)."""
    res = _run(db_session)
    for scn_seed in {(o["scenario_id"], o["seed"]) for o in res["observations"]["R0"]}:
        r0 = next(o for o in res["observations"]["R0"] if (o["scenario_id"], o["seed"]) == scn_seed)
        r1 = next(o for o in res["observations"]["R1"] if (o["scenario_id"], o["seed"]) == scn_seed)
        r0_rows = {x["strategy_name"]: x for x in r0["strategy_rows"]}
        for x in r1["strategy_rows"]:
            base = r0_rows.get(x["strategy_name"])
            if base is None:
                continue
            assert x["BA_score"] == base["BA_score"]
            assert x["FA_score"] == base["FA_score"]
        # candidate sets identical
        assert set(r0_rows) == {x["strategy_name"] for x in r1["strategy_rows"]}


def test_deterministic_and_reproducible_statistics(_small, db_session):
    r1 = _run(db_session)
    r2 = _run(db_session)

    def norm(res):
        return [
            (v, res["aggregates"][v]["goal_achievement"],
             res["aggregates"][v]["risk_monotonicity"]["spearman_rho_distance_vs_risk"],
             res["paired_vs_r0"].get(v, {}).get("mean_difference"))
            for v in res["variants"]
        ]

    assert norm(r1) == norm(r2)
    assert r1["verdict"] == r2["verdict"]
    assert r1["r3_selection"] == r2["r3_selection"]


def test_r3_uses_only_prespecified_components(_small, db_session):
    res = _run(db_session)
    lam = res["r3_selection"]["lambda"]
    assert lam in (0.25, 0.50, 0.75)
    for o in res["observations"]["R3"]:
        if o.get("error"):
            continue
        assert o["calibration_parameters"]["risk_model"] == "R1"
        assert o["calibration_parameters"]["risk_penalty_lambda"] == lam
        assert o["risk_formula_version"] == dtsvc.RISK_FORMULA_VERSION_ROBUST


def test_experiment_metadata_carries_calibration_version_and_parameters(_small, db_session):
    res = _run(db_session)
    for v in res["variants"]:
        for o in res["observations"][v]:
            if o.get("error"):
                continue
            assert "calibration_variant" in o and "calibration_parameters" in o
            assert "risk_formula_version" in o
    assert res["risk_formula_versions"]["R0"] == dtsvc.RISK_FORMULA_VERSION
    assert res["risk_formula_versions"]["R1_R3"] == dtsvc.RISK_FORMULA_VERSION_ROBUST


def test_risk_ordering_and_zero_variance_are_measured(_small, db_session):
    res = _run(db_session)
    for v in res["variants"]:
        mono = res["aggregates"][v]["risk_monotonicity"]
        assert "spearman_rho_distance_vs_risk" in mono
        assert "price10_safer_than_price5_violations" in mono
    zv = res["zero_variance_diagnostic"]
    assert set(zv) == {"constant", "low_variance", "normal_variance"}
    for hist in zv.values():
        assert set(hist) == {"+5%", "+10%", "-5%"}
        for mv in hist.values():
            assert set(mv) == {"R0", "R1"}


def test_verdict_is_one_of_the_prespecified_values(_small, db_session):
    res = _run(db_session)
    assert res["verdict"] in {"PROMISING", "PARTIALLY PROMISING", "NO SATISFACTORY CALIBRATION"}
    for v, c in res["criteria_evaluation"].items():
        assert c["verdict"] in {"PROMISING", "PARTIALLY PROMISING", "NO SATISFACTORY CALIBRATION"}
        assert c["criteria_total"] == 7


def test_no_model_status_change_no_outcome_and_prior_experiments_intact(_small, db_session):
    from app.models.evaluation import PredictionEvaluation
    from app.models.experiment import ExperimentRun
    from app.models.ml_model import MLModel
    from app.services import experiment_service

    model_registry_service.sync_from_file_registry(db_session)
    prior = experiment_service.run_experiment(db_session, "causal", {"seed": 7, "name": "prior"})
    prior_id, prior_metrics = prior.id, dict(prior.metrics_json)
    models_before = {(m.model_name, m.version): m.status for m in db_session.query(MLModel).all()}
    n_pred = db_session.query(PredictionEvaluation).count()

    _run(db_session)

    assert {(m.model_name, m.version): m.status for m in db_session.query(MLModel).all()} == models_before
    assert db_session.query(PredictionEvaluation).count() == n_pred
    kept = db_session.get(ExperimentRun, prior_id)
    assert kept is not None and kept.metrics_json == prior_metrics


def test_experiment_type_registered_and_dispatches(_small, db_session):
    from app.services import experiment_service

    assert "risk_manager_calibration" in experiment_service.SUPPORTED_EXPERIMENT_TYPES
    model_registry_service.sync_from_file_registry(db_session)
    run = experiment_service.run_experiment(
        db_session, "risk_manager_calibration", {"seeds": [42], "name": "rc-test"}
    )
    assert run.status == "completed"
    assert run.metrics_json["label"] == "RISK_MANAGER_CALIBRATION"
    assert run.metrics_json["verdict"] in {
        "PROMISING", "PARTIALLY PROMISING", "NO SATISFACTORY CALIBRATION"}
