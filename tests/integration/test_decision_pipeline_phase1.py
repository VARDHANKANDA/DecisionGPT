"""Phase 1 — causal-graph integration, multi-agent debate, full traceability
exercised through the real /decisions/analyze pipeline.
"""
from app.services import model_registry_service
from tests.integration.test_analytics import _create_business, _seed_rich_business
from tests.integration.test_decisions import _create_goal


def _analyze(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)
    goal_id = _create_goal(client, business_id, "Increase revenue by 10% in 2 months")
    resp = client.post(f"/api/v1/businesses/{business_id}/decisions/analyze", json={"goal_id": goal_id})
    assert resp.status_code == 200, resp.text
    return business_id, goal_id, resp.json()


def test_decision_carries_causal_context_with_evidence_labels(client, db_session):
    _, _, body = _analyze(client, db_session)
    cc = body["causal_context"]
    assert cc["built"] is True
    assert cc["graph_version"]
    assert cc["strongest_pathway_evidence"] in {
        "assumed", "observational", "data_supported", "causally_validated"
    }
    # At least one pathway from an action lever to revenue/profit.
    assert cc["pathways"], cc
    for p in cc["pathways"]:
        assert p["nodes"][0] in {"marketing_spend", "price", "inventory"}
        assert p["nodes"][-1] in {"revenue", "profit"}
        for link in p["links"]:
            assert link["evidence_type"] in {
                "assumed", "observational", "data_supported", "causally_validated"
            }
    # The selected simulation stored that graph version too.
    assert body["expected_outcome"]  # sanity


def test_decision_records_a_two_round_debate_with_resolution(client, db_session):
    _, _, body = _analyze(client, db_session)
    debate = body["debate"]
    assert debate["rounds"] == 2
    assert set(debate["round1"].keys()) == {"business_analyst", "financial_advisor", "risk_manager"}
    for a, ev in debate["round1"].items():
        assert ev["round"] == 1
        assert 0.0 <= ev["score"] <= 1.0
    assert len(debate["round2_reviews"]) == 3
    for rv in debate["round2_reviews"]:
        assert rv["round"] == 2
        assert "concurs" in rv and "challenges" in rv
    res = debate["resolution"]
    assert "final_score" in res and "confidence" in res
    # Confidence is derived from documented components, never a bare number.
    basis = res["confidence_basis"]
    for k in ("agreement_factor", "risk_factor", "causal_evidence_factor", "uncertainty_penalty"):
        assert k in basis
    assert 0.0 <= res["confidence"] <= 1.0


def test_confidence_matches_documented_basis_formula(client, db_session):
    _, _, body = _analyze(client, db_session)
    basis = body["debate"]["resolution"]["confidence_basis"]
    expected = (
        basis["agreement_factor"]
        * basis["risk_factor"]
        * basis["causal_evidence_factor"]
        * (1.0 - basis["uncertainty_penalty"])
    )
    assert abs(body["confidence"] - max(0.0, min(1.0, expected))) < 1e-3


def test_full_trace_endpoint_is_reproducible_and_complete(client, db_session):
    business_id, goal_id, body = _analyze(client, db_session)
    decision_id = body["id"]

    resp = client.get(f"/api/v1/businesses/{business_id}/decisions/{decision_id}/trace")
    assert resp.status_code == 200, resp.text
    trace = resp.json()

    assert trace["decision_id"] == decision_id
    assert trace["goal_id"] == goal_id
    assert trace["business_state_version"]
    assert trace["candidate_strategy_ids"]
    assert trace["simulation_ids"]
    assert trace["agent_run_ids"]
    assert trace["model_versions"].get("forecasting")
    assert trace["causal_graph_version"]
    assert trace["causal_context"]["built"] is True
    assert trace["debate"]["rounds"] == 2
    assert trace["strategy_generation"]["objective"] == "increase_revenue"
    assert trace["assumptions"]
    assert trace["uncertainty"]["confidence_basis"]
    assert trace["prompt_version"]

    # Every persisted agent_run id resolves to a stored run.
    run_ids = {r["id"] for r in trace["agent_runs"]}
    assert set(trace["agent_run_ids"]).issubset(run_ids)
    assert any(r["agent_name"] == "strategy_optimizer" for r in trace["agent_runs"])
    # round-1 + round-2 runs both present for each agent
    round1 = [r for r in trace["agent_runs"] if r["input"].get("round") == 1]
    round2 = [r for r in trace["agent_runs"] if r["input"].get("round") == 2]
    assert len(round1) == 3 and len(round2) == 3

    # Freshly analyzed against unchanged data -> reproducible.
    assert trace["reproducible"]["ok"] is True, trace["reproducible"]


def test_trace_is_isolated_per_business(client, db_session):
    business_a, _, body = _analyze(client, db_session)
    decision_id = body["id"]
    business_b = _create_business(client)
    resp = client.get(f"/api/v1/businesses/{business_b}/decisions/{decision_id}/trace")
    assert resp.status_code == 404
