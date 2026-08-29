"""Phase 1/4/6/8 — dedicated research evaluation endpoints.

All read real recorded data. Where no data exists yet, a proper empty
state must be returned — never a fabricated metric.
"""
import pytest

from app.core.config import get_settings
from app.services import model_registry_service
from tests.integration.test_analytics import _create_business, _seed_rich_business
from tests.integration.test_decisions import _create_goal

RESEARCH_PATHS = [
    "/api/v1/research/model-performance",
    "/api/v1/research/digital-twin-evaluation",
    "/api/v1/research/causal-evaluation",
    "/api/v1/research/agent-evaluation",
    "/api/v1/research/paper-results",
]


def _h():
    return {"X-Research-Token": get_settings().research_console_token}


def _decision(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    bid = _create_business(client)
    _seed_rich_business(client, bid)
    gid = _create_goal(client, bid, "Increase revenue by 10% in 2 months")
    d = client.post(f"/api/v1/businesses/{bid}/decisions/analyze", json={"goal_id": gid}).json()
    return bid, gid, d


# --- security ------------------------------------------------------------


def test_all_research_eval_endpoints_require_token(client):
    for path in RESEARCH_PATHS:
        assert client.get(path).status_code == 403


@pytest.fixture()
def auth_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_enabled", True)
    yield


def test_sme_cannot_reach_eval_endpoints_admin_can(client, auth_on):
    sme = client.post(
        "/api/v1/auth/register", json={"email": "s@x.com", "password": "password123", "role": "sme"}
    ).json()["access_token"]
    admin = client.post(
        "/api/v1/auth/register", json={"email": "a@x.com", "password": "password123", "role": "admin"}
    ).json()["access_token"]
    for path in RESEARCH_PATHS:
        assert client.get(path, headers={"Authorization": f"Bearer {sme}"}).status_code == 403
        assert client.get(path, headers={"Authorization": f"Bearer {admin}"}).status_code == 200


# --- model performance -------------------------------------------------


def test_model_performance_empty_state(client):
    body = client.get("/api/v1/research/model-performance", headers=_h()).json()
    assert body["empty_state"]
    assert body["summary"]["registered_models"] == 0
    assert body["forecasting"]["models"] == []


def test_model_performance_aggregates_real_registry(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    body = client.get("/api/v1/research/model-performance", headers=_h()).json()
    assert body["empty_state"] is None
    assert body["summary"]["registered_models"] >= 3
    assert body["summary"]["best_forecasting"]["metric"] == "mae"
    assert body["summary"]["best_forecasting"]["value"] is not None
    names = {m["model_name"] for m in body["forecasting"]["models"]}
    assert "sales_forecast_xgboost" in names
    # No metric is invented — every chart point is a real stored number.
    for pt in body["forecasting"]["chart"]:
        assert pt["mae"] is None or isinstance(pt["mae"], (int, float))


def test_model_performance_task_filter(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    body = client.get("/api/v1/research/model-performance?task=churn", headers=_h()).json()
    assert body["forecasting"]["models"] == []
    assert len(body["classification"]["models"]) >= 3


# --- digital twin evaluation -----------------------------------------


def test_digital_twin_eval_empty_state_without_outcomes(client, db_session):
    _decision(client, db_session)
    body = client.get("/api/v1/research/digital-twin-evaluation", headers=_h()).json()
    assert body["empty_state"]
    assert body["summary"]["evaluated_predictions"] == 0
    assert body["summary"]["decisions_awaiting_outcome"] >= 1


def test_digital_twin_eval_exposes_separated_real_indian_sme_block_empty(client, db_session):
    """Real Indian SME outcomes are a strictly separate block with an honest
    empty state — synthetic decisions never populate it. Table 2 = NOT READY."""
    _decision(client, db_session)  # a synthetic decision exists but no real SME outcome
    body = client.get("/api/v1/research/digital-twin-evaluation", headers=_h()).json()
    r = body["real_indian_sme"]
    assert r["data_category"] == "REAL_INDIAN_SME_OUTCOME"
    assert r["collection_status"] == "PENDING"
    assert r["table_2"] == "NOT READY"
    assert r["n_outcomes"] == 0
    assert "No real Indian SME outcomes available" in r["empty_state"]
    assert r["r0_vs_r3"].startswith("NOT APPLICABLE")


def test_real_sme_import_then_report_is_separated_and_descriptive(client, db_session):
    from app.services import real_sme_outcome_service as svc

    rec = {
        "business_id": "SME-TEST-1", "industry": "Grocery Retail", "state": "Karnataka",
        "district": "Bengaluru", "decision_date": "2026-01-10", "decision_type": "price_increase",
        "goal": "increase_profit", "strategy": "Price +5%", "prediction_horizon_days": 30,
        "baseline_revenue": 500000, "predicted_revenue": 520000, "actual_revenue": 511000,
        "baseline_profit": 60000, "predicted_profit": 66000, "actual_profit": 62000,
        "baseline_units": 8000, "predicted_units": 7950, "actual_units": 7900,
        "predicted_risk": 0.2, "predicted_confidence": 0.55,
        "outcome_recorded_date": "2026-02-09", "outcome_status": "partially_achieved",
        "source_type": "real_indian_sme", "business_country": "IN",
        "data_consent_status": "consented", "anonymization_status": "anonymized",
        "collection_method": "sme_self_report_form",
    }
    svc.import_outcome_record(db_session, rec)

    body = client.get("/api/v1/research/digital-twin-evaluation", headers=_h()).json()
    r = body["real_indian_sme"]
    assert r["n_outcomes"] == 1 and r["n_businesses"] == 1
    assert r["table_2"] == "NOT READY"          # < 5
    assert r["statistical_inference"] == "DESCRIPTIVE ONLY"
    assert r["digital_twin"]["revenue"]["n"] == 1
    assert r["provenance"]["all_real_source"] is True
    # the imported record IS a real matched predicted/actual outcome, so the
    # top-level count reflects it; the real_indian_sme block is the CATEGORISED
    # (Table 2) view that must never contain a synthetic outcome.
    assert body["summary"]["evaluated_predictions"] == 1
    assert all(row["source_type"] == "real_indian_sme" for row in r["rows"])


def test_recording_outcome_creates_a_matched_prediction_evaluation(client, db_session):
    bid, _gid, d = _decision(client, db_session)
    exp = d["expected_outcome"]
    actual_revenue = exp["baseline_revenue"] + (exp["expected_revenue"] - exp["baseline_revenue"]) * 0.5
    r = client.post(
        f"/api/v1/businesses/{bid}/decisions/{d['id']}/outcome",
        json={"actual_outcome": {"revenue": actual_revenue}},
    )
    assert r.status_code == 200, r.text

    body = client.get("/api/v1/research/digital-twin-evaluation", headers=_h()).json()
    assert body["empty_state"] is None
    assert body["summary"]["evaluated_predictions"] == 1
    row = body["rows"][0]
    assert row["decision_id"] == d["id"]
    assert row["error"] is not None
    assert row["simulation_id"]  # traceability
    assert row["model_versions"]
    assert body["metrics"]["revenue"]["mae"] is not None
    assert len(body["charts"]["predicted_vs_actual"]) == 1


def test_digital_twin_eval_backfill_is_idempotent(client, db_session):
    bid, _gid, d = _decision(client, db_session)
    client.post(
        f"/api/v1/businesses/{bid}/decisions/{d['id']}/outcome",
        json={"actual_outcome": {"revenue": d["expected_outcome"]["expected_revenue"]}},
    )
    first = client.post("/api/v1/research/digital-twin-evaluation/backfill", headers=_h()).json()
    second = client.post("/api/v1/research/digital-twin-evaluation/backfill", headers=_h()).json()
    assert first["evaluations_created"] == 0  # feedback loop already made it
    assert second["evaluations_created"] == 0


# --- causal graph evaluation ----------------------------------------


def test_causal_eval_empty_state(client):
    body = client.get("/api/v1/research/causal-evaluation", headers=_h()).json()
    assert body["empty_state"]


def test_causal_eval_shows_real_graph_and_no_fabricated_accuracy(client, db_session):
    _decision(client, db_session)  # analysing a goal builds a causal graph
    body = client.get("/api/v1/research/causal-evaluation", headers=_h()).json()
    assert body["empty_state"] is None
    assert body["overview"]["businesses_with_a_graph"] == 1
    assert body["graphs"], body
    g = body["graphs"][0]
    assert g["edge_count"] > 0
    assert set(g["evidence_counts"].keys()) == {
        "assumed", "observational", "data_supported", "causally_validated"
    }
    # No ground-truth business graph -> no fabricated recovery accuracy.
    assert body["ground_truth_comparison"]["available"] is False


def test_causal_eval_method_validation_uses_a_real_experiment(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    client.post(
        "/api/v1/research/experiments/run",
        json={"experiment_type": "causal", "configuration": {"seed": 7}},
        headers=_h(),
    )
    body = client.get("/api/v1/research/causal-evaluation", headers=_h()).json()
    mv = body["method_validation"]
    assert mv is not None
    assert mv["label"] == "SYNTHETIC_METHOD_VALIDATION"
    assert mv["experiment_id"]
    assert "recovered_edges" in mv and "missing_edges" in mv


# --- multi-agent evaluation ----------------------------------------


def test_agent_eval_empty_state(client):
    body = client.get("/api/v1/research/agent-evaluation", headers=_h()).json()
    assert body["empty_state"]


def test_agent_eval_reads_real_architecture_experiment(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    client.post(
        "/api/v1/research/experiments/run",
        json={"experiment_type": "decision_architecture", "configuration": {"seed": 11}},
        headers=_h(),
    )
    body = client.get("/api/v1/research/agent-evaluation", headers=_h()).json()
    assert body["empty_state"] is None
    rows = body["architecture_comparison"]["rows"]
    assert {r["architecture"] for r in rows} == {"A", "B", "C", "D"}
    assert body["architecture_comparison"]["experiment_id"]


def test_agent_eval_debate_analysis_from_real_decisions(client, db_session):
    _decision(client, db_session)
    body = client.get("/api/v1/research/agent-evaluation", headers=_h()).json()
    da = body["debate_analysis"]
    assert da["decisions_with_debate"] == 1
    assert da["avg_agents_involved"] == 3
    assert "latest_decision" in da


def test_agent_eval_exposes_pre_and_post_correction_diagnostic(client, db_session):
    """The candidate-space correction re-runs multi_agent_diagnostic under a new
    experiment id; the endpoint must surface BOTH the latest (post-correction)
    and the immediately-previous (pre-correction) run so the dashboard can show
    the before/after, without deleting or overwriting the old one."""
    from datetime import timedelta

    from app.models.common import utcnow
    from app.models.experiment import ExperimentRun

    def _mk(name, created, coverage_rate):
        run = ExperimentRun(
            experiment_name=name,
            experiment_type="multi_agent_diagnostic",
            status="completed",
            configuration_json={"seeds": [42]},
            metrics_json={
                "seeds": [42],
                "total_scenario_seed_pairs": 12,
                "candidate_coverage": {
                    "pairs_checked": 12,
                    "candidate_coverage_rate": coverage_rate,
                    "missing_supported_strategy_rate": 0.0 if coverage_rate > 0.5 else 0.5,
                    "invariant_dt_best_present_when_supported": coverage_rate > 0.5,
                },
                "digital_twin_to_final": {"override_rate": 1.0},
                "override_outcomes": {"improved": 0, "degraded": 9, "neutral": 3},
                "failure_modes": {},
                "central_hypothesis": {},
            },
        )
        run.created_at = created
        db_session.add(run)
        return run

    now = utcnow()
    _mk("PRE_CORRECTION multi_agent_diagnostic", now - timedelta(hours=2), 0.333)
    _mk("POST_CORRECTION multi_agent_diagnostic", now, 0.833)
    db_session.commit()

    body = client.get("/api/v1/research/agent-evaluation", headers=_h()).json()

    cur = body["multi_agent_diagnostic"]
    prev = body["multi_agent_diagnostic_previous"]
    assert cur is not None and prev is not None
    assert cur["experiment_name"] == "POST_CORRECTION multi_agent_diagnostic"
    assert prev["experiment_name"] == "PRE_CORRECTION multi_agent_diagnostic"
    assert cur["experiment_id"] != prev["experiment_id"]
    assert cur["candidate_coverage"]["candidate_coverage_rate"] == 0.833
    assert prev["candidate_coverage"]["candidate_coverage_rate"] == 0.333
    assert cur["candidate_coverage"]["invariant_dt_best_present_when_supported"] is True
    assert prev["candidate_coverage"]["invariant_dt_best_present_when_supported"] is False


def test_agent_eval_exposes_risk_manager_diagnostic(client, db_session):
    """The risk-penalty sensitivity study is surfaced on /agent-evaluation with
    D0 (Full DecisionGPT) and D1 (labelled sensitivity variant) side by side —
    read straight from the stored risk_manager_diagnostic experiment."""
    from app.models.experiment import ExperimentRun

    run = ExperimentRun(
        experiment_name="risk_manager_diagnostic v1",
        experiment_type="risk_manager_diagnostic",
        status="completed",
        configuration_json={"seeds": [42, 43, 44, 45, 46]},
        metrics_json={
            "seeds": [42, 43, 44, 45, 46],
            "total_scenario_seed_pairs": 60,
            "baseline": {
                "full_decisiongpt_mean_goal_achievement": 0.0844,
                "digital_twin_mean_goal_achievement": 0.4856,
                "d1_risk_penalty_sensitivity_mean_goal_achievement": 0.5834,
            },
            "formula_verification": {
                "checked": "final_score == (BA+FA)/2 - (1-RM) for every strategy row",
                "max_deviation_observed": 0.0, "holds_for_all_rows": True, "rows_checked": 390,
            },
            "risk_manager_disagreement": {"disagreements_vs_dt_best": 60, "disagreement_rate": 1.0},
            "rm_decisive": {
                "count": 45, "percentage": 75.0, "improved": 35, "degraded": 0, "neutral": 10,
                "definition": "removing ONLY the risk-penalty term changes the selected strategy",
                "pairs": [],
            },
            "risk_score_mismatch": {
                "count": 0, "strategy_rows_inspected": 390, "percentage": 0.0,
                "definition": "DT risk < 0.15 (LOW band) but RM score == 0.0",
                "rm_distinguishes_low_vs_high_risk_price_strategies": {"assessable": True, "verdict": "YES"},
                "calibration_table": [
                    {"strategy": "Price +5%", "observations": 50, "mean_digital_twin_risk": 0.68,
                     "mean_risk_manager_score": 0.015, "rm_score_zero_rate": 0.8, "dt_risk_low_rate": 0.0},
                ],
            },
            "d0_vs_d1": {
                "goal_achievement": {
                    "D0": {"n": 60, "mean": 0.0844, "median": 0.0, "std": 0.28, "min": 0.0, "max": 1.0,
                           "ci95": [0.0125, 0.1564]},
                    "D1": {"n": 60, "mean": 0.5834, "median": 0.758, "std": 0.44, "min": 0.0, "max": 1.0,
                           "ci95": [0.4692, 0.6976]},
                },
                "risk_adjusted_score": {"D0": None, "D1": None},
                "confidence": {
                    "D0": {"n": 60, "mean": 0.139, "median": 0.15, "std": 0.05, "min": 0.0, "max": 0.22,
                           "ci95": [0.1255, 0.1524]},
                    "D1": {"n": 60, "mean": 0.0184, "median": 0.0, "std": 0.04, "min": 0.0, "max": 0.15,
                           "ci95": [0.0069, 0.0299]},
                },
                "dt_best_agreement_rate": {"D0": 0.0, "D1": 0.0},
                "override_rate_vs_dt_best": {"D0": 1.0, "D1": 1.0},
            },
            "paired_d1_minus_d0": {
                "comparison": "D1 (Risk-Penalty Sensitivity) vs D0 (Full DecisionGPT)",
                "metric": "goal_achievement", "n_pairs": 60,
                "mean_difference": 0.4989, "median_difference": 0.5689, "std_difference": 0.45,
                "d1_wins": 35, "ties": 25, "d0_wins": 0,
                "mean_difference_ci95": [0.3827, 0.6152],
                "test": "Wilcoxon signed-rank", "statistic": 0.0, "p_value": 0.0, "effect_size_r": 0.8926,
                "interpretation": "D1 goal achievement is higher than D0 by +0.4989 (p=0.0000).",
                "difference_is": "D1 - D0",
            },
            "interpretation": {
                "outcome": "A", "removing_rm_penalty_improves_full": "YES",
                "rm_penalty_explains_the_gap": "YES", "paired_significant": True,
                "delta_d1_minus_d0": 0.499, "fraction_of_gap_closed": 1.24,
                "text": "D1 reaches 0.583 vs D0 0.084 and approaches the Digital Twin's 0.486.",
            },
            "traces": [
                {"scenario_id": "S01", "seed": 42, "goal_objective": "increase_revenue",
                 "d0_selected_strategy": "Marketing +10%", "d1_selected_strategy": "Price +10%",
                 "d0_goal_achievement": 0.0, "d1_goal_achievement": 0.83,
                 "d0_confidence": 0.15, "d1_confidence": 0.0,
                 "rm_decisive": True, "rm_decisive_outcome": "improved",
                 "rm_top_pick": "Marketing +10%", "dt_sweep_best_strategy": "Price +5%",
                 "risk_score_mismatch_count": 0},
            ],
        },
    )
    db_session.add(run)
    db_session.commit()

    body = client.get("/api/v1/research/agent-evaluation", headers=_h()).json()
    rm = body["risk_manager_diagnostic"]
    assert rm is not None
    assert rm["experiment_name"] == "risk_manager_diagnostic v1"
    assert rm["baseline"]["full_decisiongpt_mean_goal_achievement"] == 0.0844
    assert rm["baseline"]["d1_risk_penalty_sensitivity_mean_goal_achievement"] == 0.5834
    assert rm["rm_decisive"]["percentage"] == 75.0
    assert rm["risk_score_mismatch"]["count"] == 0
    assert rm["formula_verification"]["holds_for_all_rows"] is True
    assert rm["paired_d1_minus_d0"]["difference_is"] == "D1 - D0"
    assert rm["interpretation"]["outcome"] == "A"
    assert len(rm["scenario_drilldown"]) == 1
    assert rm["scenario_drilldown"][0]["d1_selected_strategy"] == "Price +10%"


def test_agent_eval_exposes_risk_manager_calibration(client, db_session):
    """The calibration study (R0/D1/R1/R2-λ/R3) is surfaced on /agent-evaluation
    with the pre-specified verdict — read straight from the stored experiment.
    All variants are EXPERIMENTAL; the payload never implies promotion."""
    from app.models.experiment import ExperimentRun

    def _summ(mean_, ci):
        return {"n": 60, "mean": mean_, "median": mean_, "std": 0.1, "min": 0.0, "max": 1.0, "ci95": ci}

    def _agg(v, ga, ra, cf, rho, viol):
        return {
            "variant": v, "n_pairs": 60,
            "goal_achievement": _summ(ga, [ga - 0.05, ga + 0.05]),
            "risk_adjusted_score": _summ(ra, [ra - 10, ra + 10]),
            "confidence": _summ(cf, [cf - 0.01, cf + 0.01]),
            "mean_selected_dt_risk": 0.5, "mean_strategy_dt_risk": 0.27, "mean_strategy_rm_score": 0.33,
            "dt_best_agreement_rate": 0.0, "override_rate": 1.0,
            "override_improved": 0, "override_degraded": 40, "override_neutral": 20,
            "risk_monotonicity": {
                "spearman_rho_distance_vs_risk": rho,
                "price10_safer_than_price5_violations": viol, "violation_pairs": [],
            },
        }

    variants = ["R0", "D1", "R1", "R2-0.25", "R2-0.50", "R2-0.75", "R3"]
    run = ExperimentRun(
        experiment_name="risk_manager_calibration v1",
        experiment_type="risk_manager_calibration",
        status="completed",
        configuration_json={"seeds": [42, 43, 44, 45, 46]},
        metrics_json={
            "seeds": [42, 43, 44, 45, 46], "total_scenario_seed_pairs": 60,
            "risk_formula_versions": {
                "R0": "extrapolation_range_v1", "R1_R3": "extrapolation_robust_v1",
                "robust_scale_rel_floor": 0.15,
            },
            "r3_selection": {"lambda": 0.25, "rule": "smallest lambda ..."},
            "digital_twin_mean_goal_achievement": 0.4856,
            "variants": variants,
            "aggregates": {
                "R0": _agg("R0", 0.0844, -2614.8, 0.139, 0.976, 0),
                "D1": _agg("D1", 0.5834, -2522.0, 0.018, 0.976, 0),
                "R1": _agg("R1", 0.0844, -2263.0, 0.141, 0.969, 0),
                "R2-0.25": _agg("R2-0.25", 0.1678, -2614.8, 0.109, 0.976, 0),
                "R2-0.50": _agg("R2-0.50", 0.0844, -2614.8, 0.139, 0.976, 0),
                "R2-0.75": _agg("R2-0.75", 0.0844, -2614.8, 0.139, 0.976, 0),
                "R3": _agg("R3", 0.1678, 40.5, 0.109, 0.969, 0),
            },
            "paired_vs_r0": {
                v: {
                    "comparison": f"{v} vs R0 (D0 / production)", "difference_is": f"{v} - R0",
                    "metric": "goal_achievement", "n_pairs": 60,
                    "mean_difference": 0.0833 if v in ("R2-0.25", "R3") else 0.0,
                    "median_difference": 0.0, "std_difference": 0.2, "ties": 55,
                    "mean_difference_ci95": [0.019, 0.148] if v in ("R2-0.25", "R3") else None,
                    "test": "Wilcoxon signed-rank",
                    "p_value": 0.0253 if v in ("R2-0.25", "R3") else None,
                    "effect_size_r": 1.0 if v in ("R2-0.25", "R3") else None,
                    "interpretation": "…", f"{v}_wins": 5 if v in ("R2-0.25", "R3") else 0, "r0_wins": 0,
                }
                for v in variants if v != "R0"
            },
            "zero_variance_diagnostic": {
                "constant": {"+5%": {"R0": 1.0, "R1": 0.3333}, "+10%": {"R0": 1.0, "R1": 0.6667},
                             "-5%": {"R0": 1.0, "R1": 0.3333}},
                "low_variance": {"+5%": {"R0": 1.0, "R1": 0.2667}, "+10%": {"R0": 1.0, "R1": 0.6},
                                 "-5%": {"R0": 1.0, "R1": 0.2667}},
                "normal_variance": {"+5%": {"R0": 0.0, "R1": 0.0}, "+10%": {"R0": 0.5, "R1": 0.3333},
                                    "-5%": {"R0": 0.0, "R1": 0.0}},
            },
            "pre_specified_criteria": ["improves goal achievement over D0", "..."],
            "criteria_evaluation": {
                v: {"checks": {"improves_goal_achievement": v in ("R2-0.25", "R3")},
                    "criteria_passed": 7 if v in ("R2-0.25", "R3") else 6,
                    "criteria_total": 7,
                    "verdict": "PROMISING" if v in ("R2-0.25", "R3") else "NO SATISFACTORY CALIBRATION"}
                for v in ("R1", "R2-0.25", "R2-0.50", "R2-0.75", "R3")
            },
            "verdict": "PROMISING",
            "verdict_by_variant": {"R1": "NO SATISFACTORY CALIBRATION", "R2-0.25": "PROMISING",
                                   "R2-0.50": "NO SATISFACTORY CALIBRATION",
                                   "R2-0.75": "NO SATISFACTORY CALIBRATION", "R3": "PROMISING"},
            "best_calibration_variant": "R2-0.25",
        },
    )
    db_session.add(run)
    db_session.commit()

    body = client.get("/api/v1/research/agent-evaluation", headers=_h()).json()
    rc = body["risk_manager_calibration"]
    assert rc is not None
    assert rc["experiment_name"] == "risk_manager_calibration v1"
    assert rc["verdict"] == "PROMISING"
    assert rc["variants"] == variants
    assert rc["r3_selection"]["lambda"] == 0.25
    assert rc["aggregates"]["R3"]["goal_achievement"]["mean"] == 0.1678
    assert rc["aggregates"]["R3"]["risk_adjusted_score"]["mean"] == 40.5
    assert rc["aggregates"]["R1"]["goal_achievement"]["mean"] == 0.0844  # R1 alone doesn't help
    assert rc["criteria_evaluation"]["R3"]["verdict"] == "PROMISING"
    assert rc["zero_variance_diagnostic"]["constant"]["+5%"]["R0"] == 1.0
    assert rc["zero_variance_diagnostic"]["constant"]["+5%"]["R1"] < 1.0


def test_agent_eval_exposes_risk_manager_generalization(client, db_session):
    """The R3 real-Indian-data generalization / external-validation study is
    surfaced on /agent-evaluation with the pre-registered verdict — read from
    the stored risk_manager_real_data_validation experiment. Production = R0."""
    from app.models.experiment import ExperimentRun

    def _regime(rho, viol, r0eq):
        return {
            "label": "x", "n_rows": 60, "n_sub_series": 8,
            "spearman_rho_dist_vs_r0": rho, "spearman_rho_dist_vs_r1": rho,
            "monotonicity_violations_r0": viol, "monotonicity_violations_r1": viol,
            "r0_equals_r1_all_rows": r0eq, "r1_never_below_r0": True,
            "mean_r0_risk_legit_moves": 0.0, "mean_r1_risk_legit_moves": 0.0,
            "mean_r0_risk_extreme_probes": 0.33, "mean_r1_risk_extreme_probes": 0.33,
            "extreme_outside_range_penalised_r1": 0.82, "n_extreme_probes_outside_range": 30,
        }

    run = ExperimentRun(
        experiment_name="risk_manager_real_data_validation v1",
        experiment_type="risk_manager_real_data_validation",
        status="completed",
        configuration_json={},
        metrics_json={
            "label": "RISK_MANAGER_GENERALIZATION",
            "dataset": {"id": "external-india-ecommerce-v1", "name": "India E-Commerce Orders (Benroshan)",
                        "category": "INDIA_REAL_BUSINESS", "provenance": "UNVERIFIED",
                        "license": "CC0", "geography": "India"},
            "synthetic_calibration_reference": {"experiment": "risk_manager_calibration b8516eef",
                                                "r3_verdict": "PROMISING"},
            "part_a_risk_regime": {
                "regime_classifier": {"statistic": "robust CV = 1.4826 * MAD / |median|",
                                      "low_max": 0.15, "moderate_max": 0.40},
                "regime_counts": {"LOW_VARIANCE": 3, "MODERATE_VARIANCE": 11, "HIGH_VARIANCE": 9},
                "sub_series": [{"sub_series": "Clothing", "grain": "monthly", "n_points": 12,
                                "n_line_items": 949, "price_variance_regime": "LOW_VARIANCE",
                                "historical_price_scale_rcv": 0.129, "historical_price_min": 20.99,
                                "historical_price_max": 55.82, "historical_price_median": 27.0}],
                "by_regime": {"LOW_VARIANCE": _regime(0.9985, 0, True),
                              "MODERATE_VARIANCE": _regime(0.9868, 0, True),
                              "HIGH_VARIANCE": _regime(0.9925, 0, True)},
                "overall": _regime(0.9892, 0, True),
            },
            "part_b_decision_comparison_simulated": {
                "business_meta": {"forecast_origin_date": "2019-03-31", "n_sale_days": 307, "span_days": 365},
                "leakage_check": {"history_last_date": "2019-03-31", "max_sale_date": "2019-03-31",
                                  "forecast_origin_date": "2019-03-31", "no_future_rows_in_history": True},
                "decision_comparison": {
                    v: {"selected_strategy": "Price +10%", "goal_achievement": 1.0,
                        "risk_adjusted_score": 5848.25, "confidence": 0.161,
                        "selected_dt_risk": 0.0, "mean_strategy_dt_risk": 0.0,
                        "strategy_changed_vs_r0": False}
                    for v in ("R0", "R1", "R2-0.25", "R3", "D1")
                },
            },
            "part_c_real_llm": {"status": "BLOCKED", "reason": "No LLM provider configured",
                                "provider": "", "model": ""},
            "part_d_decision_outcome": {"decision_outcome_records": 0,
                                        "matched_prediction_evaluations": 0,
                                        "status": "INSUFFICIENT", "table_2": "NOT READY"},
            "hypotheses": {
                "H1_low_variance_pathology_reduced": "NOT ASSESSABLE",
                "H2_ordering_preserved_realistic_variation": "SUPPORTED",
                "H3_risk_adjusted_not_worse_simulated": "SUPPORTED",
                "H4_extreme_extrapolation_still_penalised": "SUPPORTED",
                "H5_generalizes_beyond_one_regime": "SUPPORTED",
                "H5_note": "R0 == R1 on all real rows; R3 has no measurable effect.",
                "H6_survives_real_llm": "NOT TESTABLE — real-LLM validation BLOCKED",
            },
            "external_validation": {
                "criteria": {"1_low_variance_inflation_reduced": False, "2_risk_ordering_monotonic": True,
                             "3_extreme_extrapolation_not_low_risk": True, "4_risk_adjusted_not_worse": True,
                             "5_confidence_not_collapsed": True, "6_not_dependent_on_single_regime": True,
                             "7_reproducible": True, "8_survives_real_llm": False},
                "core_criteria_passed": False,
                "central_benefit_confirmed_on_real_data": False,
                "anything_regressed_on_real_data": False,
                "verdict": "PROMISING BUT NOT VALIDATED",
            },
            "production_default": "R0",
        },
    )
    db_session.add(run)
    db_session.commit()

    body = client.get("/api/v1/research/agent-evaluation", headers=_h()).json()
    rg = body["risk_manager_generalization"]
    assert rg is not None
    assert rg["experiment_name"] == "risk_manager_real_data_validation v1"
    assert rg["dataset"]["category"] == "INDIA_REAL_BUSINESS"
    assert rg["external_validation"]["verdict"] == "PROMISING BUT NOT VALIDATED"
    assert rg["external_validation"]["central_benefit_confirmed_on_real_data"] is False
    assert rg["risk_regime_overall"]["r0_equals_r1_all_rows"] is True
    assert rg["risk_regime_overall"]["monotonicity_violations_r1"] == 0
    assert rg["real_llm"]["status"] == "BLOCKED"
    assert rg["decision_outcome"]["table_2"] == "NOT READY"
    assert rg["decision_comparison_simulated"]["R3"]["selected_strategy"] == "Price +10%"
    assert rg["production_default"] == "R0"


# --- paper results ------------------------------------------------


def test_paper_results_reports_readiness_not_fabrication(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    body = client.get("/api/v1/research/paper-results", headers=_h()).json()
    keys = {t["key"] for t in body["tables"]}
    assert keys == {
        "predictive_model_performance",
        "digital_twin_evaluation",
        "causal_graph_evaluation",
        "decision_architecture",
        "ablation_study",
    }
    t1 = next(t for t in body["tables"] if t["key"] == "predictive_model_performance")
    assert t1["available"] is True  # models synced
    t2 = next(t for t in body["tables"] if t["key"] == "digital_twin_evaluation")
    assert t2["available"] is False  # no outcomes yet
    assert t2["missing_reason"]
    assert t2.get("data_category") == "REAL_INDIAN_SME_OUTCOME"


def test_paper_table_2_needs_five_genuine_real_sme_outcomes(client, db_session):
    """Table 2 stays NOT READY below 5 real Indian SME outcomes, and never
    counts a synthetic / demo-recorded outcome."""
    from app.services import real_sme_outcome_service as rso

    model_registry_service.sync_from_file_registry(db_session)

    def _rec(i):
        return {
            "business_id": f"SME-P{i}", "industry": "Grocery Retail", "state": "KA",
            "district": "Bengaluru", "decision_date": "2026-01-10",
            "decision_type": "price_increase", "goal": "increase_profit",
            "strategy": "Price +5%", "prediction_horizon_days": 30,
            "baseline_revenue": 500000, "predicted_revenue": 520000, "actual_revenue": 511000,
            "predicted_risk": 0.2, "predicted_confidence": 0.55,
            "outcome_recorded_date": "2026-02-09", "outcome_status": "partially_achieved",
            "source_type": "real_indian_sme", "business_country": "IN",
            "data_consent_status": "consented", "anonymization_status": "anonymized",
            "collection_method": "sme_self_report_form",
        }

    for i in range(3):
        rso.import_outcome_record(db_session, _rec(i))
    t2 = next(t for t in client.get("/api/v1/research/paper-results", headers=_h()).json()["tables"]
              if t["key"] == "digital_twin_evaluation")
    assert t2["available"] is False
    assert "3/5" in t2["missing_reason"]
    assert t2["source_refs"]["real_matched"] == 3 and t2["source_refs"]["min_required"] == 5

    for i in range(3, 5):
        rso.import_outcome_record(db_session, _rec(i))
    t2b = next(t for t in client.get("/api/v1/research/paper-results", headers=_h()).json()["tables"]
               if t["key"] == "digital_twin_evaluation")
    assert t2b["available"] is True
    assert t2b["source_refs"]["real_matched"] == 5
