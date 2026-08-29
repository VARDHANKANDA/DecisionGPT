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
