"""R3 generalization / real-Indian-data validation — regime classification,
real-data risk calibration (R0 == R1), no leakage, SIMULATED decision
comparison isolation, real-LLM BLOCKED handling, no fabricated outcomes,
prior-experiment / model-registry immutability, pre-registered verdict.
"""
import pytest

from app.analytics import digital_twin_service as dtsvc
from app.services import model_registry_service
from app.services import risk_manager_generalization_service as g


# --- pre-registered regime classifier (pure) --------------------------


def test_regime_thresholds_are_prespecified():
    assert g.REGIME_LOW_MAX == 0.15
    assert g.REGIME_MODERATE_MAX == 0.40
    assert g._regime(0.10) == "LOW_VARIANCE"
    assert g._regime(0.15) == "MODERATE_VARIANCE"
    assert g._regime(0.399) == "MODERATE_VARIANCE"
    assert g._regime(0.40) == "HIGH_VARIANCE"


def test_robust_cv_matches_definition():
    # constant -> 0 ; 1.4826 * MAD / |median|
    assert g._robust_cv([5, 5, 5, 5]) == 0.0
    # [6,8,10,12,14]: median 10, abs devs [4,2,0,2,4] -> MAD = median = 2
    assert g._robust_cv([6, 8, 10, 12, 14]) == pytest.approx(1.4826 * 2 / 10, abs=1e-4)


def test_legit_moves_and_extreme_probes_are_fixed():
    assert set(g.LEGIT_MOVES) == {-5.0, -3.0, -10.0, 5.0, 10.0}
    assert g.EXTREME_PROBES == [25.0, 50.0, 100.0]


# --- Part A on the real committed Benroshan data ---------------------


def test_part_a_real_data_r0_equals_r1_everywhere():
    """The central real-data finding: on real Indian implied-price series the
    R0 zero-variance pathology does not occur, so R0 and R1 give identical
    risk on every row, and risk ordering is preserved."""
    pa = g._part_a()
    assert pa["sub_series_count"] >= 15
    assert sum(pa["regime_counts"].values()) == pa["sub_series_count"]
    # >= 2 regimes present in the real data
    assert len([r for r, c in pa["regime_counts"].items() if c > 0]) >= 2

    ov = pa["overall"]
    assert ov["r0_equals_r1_all_rows"] is True
    assert ov["r1_never_below_r0"] is True
    assert ov["monotonicity_violations_r0"] == 0
    assert ov["monotonicity_violations_r1"] == 0
    assert ov["spearman_rho_dist_vs_r0"] == ov["spearman_rho_dist_vs_r1"]
    assert (ov["spearman_rho_dist_vs_r1"] or 0) >= 0.30
    # R1 does NOT flatten every strategy to low risk
    assert (ov["extreme_outside_range_penalised_r1"] or 0) >= 0.5

    for regime in ("LOW_VARIANCE", "MODERATE_VARIANCE", "HIGH_VARIANCE"):
        a = pa["by_regime"][regime]
        if a["n_rows"]:
            assert a["monotonicity_violations_r1"] == 0
            assert a["r0_equals_r1_all_rows"] is True


def test_part_a_is_deterministic():
    a1, a2 = g._part_a(), g._part_a()
    assert a1["regime_counts"] == a2["regime_counts"]
    assert a1["overall"] == a2["overall"]


def test_part_a_r0_path_uses_the_production_risk_function():
    # the R0 column is exactly _risk_from_extrapolation; R1 is the calibrated one
    r0, r1, dist = g._risk_for_move([100.0, 100.0, 100.0, 100.0, 100.0], 5.0)
    # constant history: this is the synthetic-style pathology -> here R0 != R1
    assert r0 == 1.0
    assert r1 < 1.0
    _, direct = dtsvc._risk_from_extrapolation(
        {"price": (100.0, 100.0), "marketing_spend": (0.0, 0.0)},
        {"price": 105.0, "marketing_spend": 0.0},
    )
    assert r0 == direct


# --- real-LLM + DecisionOutcome state --------------------------------


def test_real_llm_blocked_when_no_provider(db_session, monkeypatch):
    from app.core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "llm_provider", None, raising=False)
    monkeypatch.setattr(s, "llm_api_key", None, raising=False)
    monkeypatch.setattr(s, "llm_model", None, raising=False)
    c = g._part_c()
    assert c["status"] == "BLOCKED"
    assert "NOT real-LLM evidence" in c["reason"]


def test_decision_outcome_insufficient_and_not_fabricated(db_session):
    d = g._part_d(db_session)
    assert d["decision_outcome_records"] == 0
    assert d["status"] == "INSUFFICIENT"
    assert d["table_2"] == "NOT READY"


# --- end-to-end (materialises the real business, ~1-2 min) -----------


@pytest.fixture()
def _full(db_session):
    model_registry_service.sync_from_file_registry(db_session)
    return g.run_generalization_validation(db_session)


def test_part_b_no_leakage_and_risk_only_isolation(_full):
    pb = _full["part_b_decision_comparison_simulated"]
    lk = pb["leakage_check"]
    assert lk["no_future_rows_in_history"] is True
    assert lk["history_last_date"] == lk["forecast_origin_date"] == lk["max_sale_date"]

    dc = pb["decision_comparison"]
    assert set(dc) >= {"R0", "R1", "R2-0.25", "R3"}
    r0 = dc["R0"]
    for v in ("R1", "R2-0.25", "R3"):
        # only the risk formulation / lambda differ -> on this wide-range real
        # series every variant makes the identical SIMULATED decision
        assert dc[v]["selected_strategy"] == r0["selected_strategy"]
        assert dc[v]["goal_achievement"] == r0["goal_achievement"]
        assert dc[v]["risk_adjusted_score"] == r0["risk_adjusted_score"]
        assert dc[v]["confidence"] == r0["confidence"]
    for row in pb["rows"]:
        assert row["decision_label"] == "SIMULATED DECISION"


def test_part_b_candidate_sets_and_dt_predictions_identical_r0_r3(_full):
    rows = {r["variant"]: r for r in _full["part_b_decision_comparison_simulated"]["rows"] if not r.get("error")}
    r0 = {s["strategy_name"]: s for s in rows["R0"]["strategy_rows"]}
    r3 = {s["strategy_name"]: s for s in rows["R3"]["strategy_rows"]}
    assert set(r0) == set(r3)                       # identical candidate set
    for name in r0:
        assert r0[name]["BA_score"] == r3[name]["BA_score"]   # agent growth scores unchanged
        assert r0[name]["FA_score"] == r3[name]["FA_score"]
        # DT risk on this wide-range real series is identical (R1 == R0 here)
        assert r0[name]["digital_twin_risk"] == r3[name]["digital_twin_risk"]


def test_verdict_and_hypotheses_are_prespecified_values(_full):
    ev = _full["external_validation"]
    assert ev["verdict"] in {
        "VALIDATED FOR CONTROLLED PRODUCTION TEST",
        "PROMISING BUT NOT VALIDATED",
        "NOT VALIDATED",
    }
    assert ev["anything_regressed_on_real_data"] is False
    assert ev["central_benefit_confirmed_on_real_data"] is False  # pathology absent on real data
    for k, v in _full["hypotheses"].items():
        if k.startswith("_") or k.endswith("_note"):
            continue
        assert any(v.startswith(p) for p in ("SUPPORTED", "NOT SUPPORTED", "NOT ASSESSABLE", "NOT TESTABLE"))
    assert _full["production_default"] == "R0"
    assert _full["part_c_real_llm"]["status"] == "BLOCKED"


def test_prior_experiments_and_model_registry_unchanged(_full, db_session):
    from app.models.experiment import ExperimentRun
    from app.models.ml_model import MLModel
    from app.services import experiment_service

    before_models = {(m.model_name, m.version): m.status for m in db_session.query(MLModel).all()}
    prior = experiment_service.run_experiment(db_session, "causal", {"seed": 7, "name": "prior"})
    pid, pmetrics = prior.id, dict(prior.metrics_json)

    g.run_generalization_validation(db_session)

    assert {(m.model_name, m.version): m.status for m in db_session.query(MLModel).all()} == before_models
    kept = db_session.get(ExperimentRun, pid)
    assert kept is not None and kept.metrics_json == pmetrics


def test_experiment_type_registered_and_traceable(db_session):
    from app.services import experiment_service

    assert "risk_manager_real_data_validation" in experiment_service.SUPPORTED_EXPERIMENT_TYPES
    model_registry_service.sync_from_file_registry(db_session)
    run = experiment_service.run_experiment(
        db_session, "risk_manager_real_data_validation", {"name": "rmg-test"}
    )
    assert run.status == "completed"
    assert run.dataset_version == "external-india-ecommerce-v1"
    assert run.metrics_json["label"] == "RISK_MANAGER_GENERALIZATION"
    assert run.metrics_json["dataset"]["category"] == "INDIA_REAL_BUSINESS"
    assert run.metrics_json["production_default"] == "R0"
