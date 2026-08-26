"""Conservative causal-evidence feedback from real decision outcomes
(docs Phase 5 / docs/CAUSAL_GRAPH_SPECIFICATION.md §3, §9, §11).

One recorded outcome NEVER proves causation. This mechanism does exactly
one thing: after enough real interventions on the same lever have moved the
outcome in the direction the Digital Twin predicted, it lifts the affected
edges from ASSUMED to OBSERVATIONAL — and nothing further. DATA_SUPPORTED
still requires the Granger test in causal_graph_service; CAUSALLY_VALIDATED
is never assigned by any automated path.

Every change writes a fully-inspectable ``CausalEvidenceUpdate`` row
(graph id + version, edge, previous/new level, supporting decision/outcome
ids, method, sample size, consistency count, timestamp) and produces a new
CausalGraph version so the change is a first-class, versioned event.
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.causal import CausalEdge, CausalGraph
from app.models.decision import Decision, DecisionOutcome
from app.models.evaluation import CAUSAL_FEEDBACK_METHOD, CausalEvidenceUpdate
from app.models.strategy import Strategy

ASSUMED = "assumed"
OBSERVATIONAL = "observational"

# Conservative thresholds. Deliberately not configurable via the request —
# a caller can never lower the bar for "observational".
MIN_OUTCOMES_FOR_OBSERVATIONAL = 3
CONSISTENCY_THRESHOLD = 2 / 3

# Which causal-graph lever an SME action operates on.
ACTION_START_NODE = {
    "marketing_change": "marketing_spend",
    "price_change": "price",
    "inventory_change": "inventory",
}


def _sign(x: float | None) -> int:
    if x is None or abs(x) < 1e-9:
        return 0
    return 1 if x > 0 else -1


def _direction_confirmed(decision: Decision, outcome: DecisionOutcome) -> bool | None:
    """Did reality move revenue in the same direction the simulation
    predicted for this decision? None when either side is ~flat."""
    exp = decision.expected_outcome_json or {}
    act = outcome.actual_outcome_json or {}
    base = exp.get("baseline_revenue")
    pred = exp.get("expected_revenue")
    actual = act.get("revenue")
    if base is None or pred is None or actual is None:
        return None
    ps, as_ = _sign(pred - base), _sign(actual - base)
    if ps == 0 or as_ == 0:
        return None
    return ps == as_


def _latest_graph(db: Session, business_id: str) -> CausalGraph | None:
    return (
        db.query(CausalGraph)
        .filter(CausalGraph.business_id == business_id)
        .order_by(CausalGraph.created_at.desc())
        .first()
    )


def _edges_acted_on(decision: Decision) -> set[tuple[str, str]]:
    """(source, target) pairs the chosen strategy's causal pathways touch,
    from the decision's stored causal context."""
    ctx = decision.causal_context_json or {}
    pairs: set[tuple[str, str]] = set()
    for p in ctx.get("pathways", []):
        for link in p.get("links", []):
            if link.get("source") and link.get("target"):
                pairs.add((link["source"], link["target"]))
    return pairs


def _action_types_of(db: Session, decision: Decision) -> set[str]:
    strategy = db.get(Strategy, decision.selected_strategy_id) if decision.selected_strategy_id else None
    if strategy is None:
        return set()
    return {a["type"] for a in (strategy.actions_json or [])}


def apply_outcome_feedback(
    db: Session, business_id: str, decision: Decision, outcome: DecisionOutcome
) -> list[CausalEvidenceUpdate]:
    """Called from memory_service.record_outcome (same transaction). Never
    raises on missing data — returns an empty list instead."""
    graph = _latest_graph(db, business_id)
    if graph is None:
        return []

    candidate_edges = _edges_acted_on(decision)
    if not candidate_edges:
        return []

    edge_rows = {
        (e.source_node, e.target_node): e
        for e in db.query(CausalEdge).filter(CausalEdge.causal_graph_id == graph.id).all()
    }
    upgradable = [
        pair for pair in candidate_edges
        if pair in edge_rows and edge_rows[pair].evidence_type == ASSUMED
    ]
    if not upgradable:
        return []

    # Gather every recorded outcome for this business whose decision's
    # strategy used a lever that feeds these pathways.
    lever_action_types = {
        atype for atype, node in ACTION_START_NODE.items()
        if any(node == src for (src, _t) in upgradable) or any(node in (src, tgt) for (src, tgt) in upgradable)
    }
    # Fall back to this decision's own action types if the mapping is loose.
    lever_action_types |= _action_types_of(db, decision)

    business_decisions = (
        db.query(Decision).filter(Decision.business_id == business_id).all()
    )
    supporting: list[tuple[Decision, DecisionOutcome, bool]] = []
    for d in business_decisions:
        if not (_action_types_of(db, d) & lever_action_types):
            continue
        o = db.query(DecisionOutcome).filter(DecisionOutcome.decision_id == d.id).first()
        if o is None:
            continue
        confirmed = _direction_confirmed(d, o)
        if confirmed is None:
            continue
        supporting.append((d, o, confirmed))

    n = len(supporting)
    consistent = sum(1 for (_d, _o, ok) in supporting if ok)
    if n < MIN_OUTCOMES_FOR_OBSERVATIONAL or consistent / n < CONSISTENCY_THRESHOLD:
        # Not enough evidence — do NOT touch the graph. This is the common
        # case and it must be silent, not a fabricated upgrade.
        return []

    decision_ids = [d.id for (d, _o, _ok) in supporting]
    outcome_ids = [o.id for (_d, o, _ok) in supporting]
    rationale = (
        f"{consistent}/{n} recorded interventions on this lever moved revenue in the direction the "
        f"Digital Twin predicted (threshold {CONSISTENCY_THRESHOLD:.2f}, minimum {MIN_OUTCOMES_FOR_OBSERVATIONAL} "
        "outcomes). This is observational support only — not identified causation, and not the "
        "Granger 'data_supported' bar."
    )

    # New graph version: copy the graph, apply only the ASSUMED->OBSERVATIONAL
    # upgrades, everything else unchanged.
    version_count = (
        db.query(CausalGraph).filter(CausalGraph.business_id == business_id).count()
    )
    new_graph = CausalGraph(
        business_id=business_id,
        version=f"v{version_count + 1}",
        graph_json=dict(graph.graph_json or {}),
        method=(graph.method or "") + "+outcome_feedback",
        evidence_summary=(
            f"{len(upgradable)} edge(s) lifted ASSUMED->OBSERVATIONAL from real outcome feedback "
            f"(see causal_evidence_updates). {graph.evidence_summary or ''}"
        ).strip(),
    )
    db.add(new_graph)
    db.flush()

    updates: list[CausalEvidenceUpdate] = []
    for pair, old_edge in edge_rows.items():
        new_evidence = old_edge.evidence_type
        if pair in upgradable:
            new_evidence = OBSERVATIONAL
        db.add(
            CausalEdge(
                causal_graph_id=new_graph.id,
                source_node=old_edge.source_node,
                target_node=old_edge.target_node,
                relationship=old_edge.relationship,
                strength=old_edge.strength,
                confidence=old_edge.confidence,
                evidence_type=new_evidence,
                time_lag=old_edge.time_lag,
            )
        )
        if pair in upgradable:
            upd = CausalEvidenceUpdate(
                business_id=business_id,
                causal_graph_id=new_graph.id,
                graph_version=new_graph.version,
                source_node=pair[0],
                target_node=pair[1],
                previous_evidence=ASSUMED,
                new_evidence=OBSERVATIONAL,
                method=CAUSAL_FEEDBACK_METHOD,
                rationale=rationale,
                supporting_decision_ids_json=decision_ids,
                supporting_outcome_ids_json=outcome_ids,
                sample_size=n,
                consistent_direction_count=consistent,
            )
            db.add(upd)
            updates.append(upd)

    return updates


def get_feedback_log(db: Session, business_id: str | None = None) -> list[dict]:
    q = db.query(CausalEvidenceUpdate).order_by(CausalEvidenceUpdate.created_at.desc())
    if business_id:
        q = q.filter(CausalEvidenceUpdate.business_id == business_id)
    return [
        {
            "id": u.id,
            "business_id": u.business_id,
            "graph_version": u.graph_version,
            "edge": f"{u.source_node} → {u.target_node}",
            "source_node": u.source_node,
            "target_node": u.target_node,
            "previous_evidence": u.previous_evidence,
            "new_evidence": u.new_evidence,
            "method": u.method,
            "rationale": u.rationale,
            "sample_size": u.sample_size,
            "consistent_direction_count": u.consistent_direction_count,
            "supporting_decision_ids": u.supporting_decision_ids_json,
            "supporting_outcome_ids": u.supporting_outcome_ids_json,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in q.all()
    ]
