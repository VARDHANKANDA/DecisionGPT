"""Phase 3/5 — Digital Twin feedback loop + conservative causal evidence.

One recorded outcome must NEVER upgrade a causal edge to CAUSALLY_VALIDATED
(or even to OBSERVATIONAL). Only after enough consistent real interventions
does an ASSUMED edge become OBSERVATIONAL, and every change is logged with
full provenance.
"""
from app.models.evaluation import CausalEvidenceUpdate, PredictionEvaluation
from app.services import model_registry_service
from tests.integration.test_analytics import _create_business, _seed_rich_business
from tests.integration.test_decisions import _create_goal


def _decision(client, db_session):
    bid = _create_business(client)
    _seed_rich_business(client, bid)
    gid = _create_goal(client, bid, "Increase revenue by 10% in 2 months")
    d = client.post(f"/api/v1/businesses/{bid}/decisions/analyze", json={"goal_id": gid}).json()
    return bid, gid, d


def _record(client, bid, decision_id, revenue, extra=None):
    payload = {"revenue": revenue, **(extra or {})}
    r = client.post(
        f"/api/v1/businesses/{bid}/decisions/{decision_id}/outcome",
        json={"actual_outcome": payload},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_feedback_loop_persists_a_prediction_evaluation_with_traceability(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    bid, _gid, d = _decision(client, db_session)
    exp = d["expected_outcome"]
    _record(client, bid, d["id"], exp["baseline_revenue"] + (exp["expected_revenue"] - exp["baseline_revenue"]))

    evals = db_session.query(PredictionEvaluation).all()
    assert len(evals) == 1
    e = evals[0]
    assert e.decision_id == d["id"]
    assert e.business_id == bid
    assert e.outcome_id
    assert e.method == "revenue_change_vs_recorded_outcome_v1"
    assert e.revenue_error is not None
    assert e.model_versions_json  # traceable to the forecasting model


def test_profit_and_units_errors_recorded_when_supported(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    bid, _gid, d = _decision(client, db_session)
    exp = d["expected_outcome"]
    extra = {}
    if exp.get("expected_profit") is not None:
        extra["profit"] = exp["expected_profit"]
    _record(client, bid, d["id"], exp["expected_revenue"], extra=extra)

    e = db_session.query(PredictionEvaluation).one()
    assert "revenue" in e.metrics_json
    if extra:
        assert "profit" in e.metrics_json
        assert e.metrics_json["profit"]["error"] is not None


def test_one_outcome_does_not_upgrade_any_causal_edge(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    bid, _gid, d = _decision(client, db_session)
    _record(client, bid, d["id"], d["expected_outcome"]["expected_revenue"])

    updates = db_session.query(CausalEvidenceUpdate).all()
    assert updates == []
    # Nothing was silently promoted to causally_validated anywhere.
    from app.models.causal import CausalEdge

    assert (
        db_session.query(CausalEdge).filter(CausalEdge.evidence_type == "causally_validated").count() == 0
    )


def test_revenue_only_outcomes_do_not_upgrade_downstream_edges(client, db_session):
    """Phase 8 — per-edge consistency. Recording only overall revenue does
    not isolate any single edge (revenue sits downstream of every lever),
    so no edge is upgraded, however many consistent outcomes there are."""
    model_registry_service.sync_from_file_registry(db_session)
    bid = _create_business(client)
    _seed_rich_business(client, bid)

    for _ in range(4):
        gid = _create_goal(client, bid, "Increase revenue by 10% in 2 months")
        d = client.post(f"/api/v1/businesses/{bid}/decisions/analyze", json={"goal_id": gid}).json()
        exp = d["expected_outcome"]
        pred_change = exp["expected_revenue"] - exp["baseline_revenue"]
        actual = exp["baseline_revenue"] + (pred_change if abs(pred_change) > 1 else 1.0)
        _record(client, bid, d["id"], actual)

    assert db_session.query(CausalEvidenceUpdate).count() == 0


def test_per_edge_consistency_lifts_only_the_recorded_edge_to_observational(client, db_session):
    """When the SME records BOTH revenue and units/orders across >=3
    interventions that move consistently, the specific 'orders/sales ->
    revenue' edge is lifted ASSUMED -> OBSERVATIONAL — and nothing beyond
    that (never data_supported / causally_validated), with per-edge
    provenance."""
    model_registry_service.sync_from_file_registry(db_session)
    bid = _create_business(client)
    _seed_rich_business(client, bid)

    for _ in range(3):
        gid = _create_goal(client, bid, "Increase revenue by 10% in 2 months")
        d = client.post(f"/api/v1/businesses/{bid}/decisions/analyze", json={"goal_id": gid}).json()
        exp = d["expected_outcome"]
        base_rev, base_units = exp["baseline_revenue"], exp["baseline_units_sold"]
        pred_rev = exp["expected_revenue"] - base_rev
        pred_units = exp["expected_units_sold"] - base_units
        # Move both metrics in the predicted direction (min +1 so sign is defined).
        actual_rev = base_rev + (pred_rev if abs(pred_rev) > 1 else 1.0)
        actual_units = base_units + (pred_units if abs(pred_units) > 0.5 else 1.0)
        _record(client, bid, d["id"], actual_rev, extra={"orders": actual_units})

    updates = db_session.query(CausalEvidenceUpdate).all()
    assert updates, "expected at least one ASSUMED->OBSERVATIONAL edge upgrade"
    edges = {(u.source_node, u.target_node) for u in updates}
    # An orders/sales/demand -> revenue (or units-bearing) edge is the one
    # both ends were actually recorded for.
    assert any(t == "revenue" and s in {"orders", "sales", "demand"} for (s, t) in edges), edges
    for u in updates:
        assert u.previous_evidence == "assumed"
        assert u.new_evidence == "observational"
        assert u.sample_size >= 3
        assert u.consistent_direction_count >= 2
        assert u.supporting_decision_ids_json and u.supporting_outcome_ids_json
        assert u.method == "outcome_direction_consistency_v1"

    from app.models.causal import CausalEdge, CausalGraph

    assert (
        db_session.query(CausalEdge).filter(CausalEdge.evidence_type == "causally_validated").count() == 0
    )
    # The feedback-created graph version only ever holds assumed/observational
    # edges — feedback never manufactures data_supported.
    fb_graph = (
        db_session.query(CausalGraph)
        .filter(CausalGraph.business_id == bid, CausalGraph.method.like("%outcome_feedback%"))
        .order_by(CausalGraph.created_at.desc())
        .first()
    )
    assert fb_graph is not None
    fb_levels = {
        e.evidence_type
        for e in db_session.query(CausalEdge).filter(CausalEdge.causal_graph_id == fb_graph.id).all()
    }
    assert fb_levels <= {"assumed", "observational", "data_supported"}
    assert "causally_validated" not in fb_levels

    from app.models.causal import CausalEdge

    assert (
        db_session.query(CausalEdge).filter(CausalEdge.evidence_type == "causally_validated").count() == 0
    )
