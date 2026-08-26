"""Conservative, per-edge causal-evidence feedback from real decision
outcomes (docs Phase 5 / Phase 8, docs/CAUSAL_GRAPH_SPECIFICATION.md
§3, §9, §11).

One recorded outcome NEVER proves causation. This mechanism does exactly
one thing, and only per individual edge:

    intervention lever / upstream node
        -> downstream causal node
        -> hypothesised direction (edge.relationship)
        -> the actual metric the SME recorded for that node
        -> direction consistency

After >= MIN_OUTCOMES_FOR_OBSERVATIONAL real interventions have moved BOTH
ends of a specific ASSUMED edge in a way consistent with its hypothesised
sign (>= CONSISTENCY_THRESHOLD of the time), that one edge is lifted to
OBSERVATIONAL — and nothing further. Edges whose downstream node was never
actually recorded get no verdict and are left untouched. DATA_SUPPORTED
still requires the Granger test in causal_graph_service; CAUSALLY_VALIDATED
is never assigned by any automated path.

Every change writes a fully-inspectable ``CausalEvidenceUpdate`` row
(graph id + version, edge, previous/new level, the specific supporting
decision/outcome ids, method, per-edge sample size + consistency count,
timestamp) and produces a new versioned CausalGraph.
"""
from sqlalchemy.orm import Session

from app.models.causal import CausalEdge, CausalGraph
from app.models.decision import Decision, DecisionOutcome
from app.models.evaluation import CAUSAL_FEEDBACK_METHOD, CausalEvidenceUpdate
from app.models.strategy import Strategy

ASSUMED = "assumed"
OBSERVATIONAL = "observational"

# Conservative thresholds. Deliberately not request-configurable — a caller
# can never lower the bar for "observational".
MIN_OUTCOMES_FOR_OBSERVATIONAL = 3
CONSISTENCY_THRESHOLD = 2 / 3

# Graph node <-> SME action lever.
ACTION_START_NODE = {
    "marketing_change": "marketing_spend",
    "price_change": "price",
    "inventory_change": "inventory",
}
NODE_TO_ACTION = {v: k for k, v in ACTION_START_NODE.items()}

# Graph node -> (baseline_key, predicted_key) in expected_outcome_json.
_NODE_EXPECTED = {
    "revenue": ("baseline_revenue", "expected_revenue"),
    "profit": ("baseline_profit", "expected_profit"),
    "orders": ("baseline_units_sold", "expected_units_sold"),
    "sales": ("baseline_units_sold", "expected_units_sold"),
    "demand": ("baseline_units_sold", "expected_units_sold"),
}
# Graph node -> the actual_outcome_json keys the SME might record for it.
_NODE_ACTUAL_KEYS = {
    "revenue": ["revenue"],
    "profit": ["profit"],
    "orders": ["orders", "sales", "units"],
    "sales": ["orders", "sales", "units"],
    "demand": ["orders", "sales", "units"],
    "marketing_spend": ["marketing_spend"],
}


def _sign(x: float | None) -> int:
    if x is None or abs(x) < 1e-9:
        return 0
    return 1 if x > 0 else -1


def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _action_map(db: Session, decision: Decision) -> dict[str, float]:
    strategy = db.get(Strategy, decision.selected_strategy_id) if decision.selected_strategy_id else None
    if strategy is None:
        return {}
    return {a["type"]: a["value"] for a in (strategy.actions_json or [])}


def _node_change_dir(actions: dict[str, float], exp: dict, act: dict, node: str) -> int | None:
    """The observed change direction of a causal node for one recorded
    outcome: from the intervention when the node is a lever, otherwise from
    the actually-recorded metric vs the simulation's baseline. None when
    unavailable or flat."""
    # 1. lever node — direction is the sign of the SME's action on it.
    action_type = NODE_TO_ACTION.get(node)
    if action_type and action_type in actions:
        return _sign(actions[action_type])

    # 2. recorded downstream metric vs baseline.
    exp_keys = _NODE_EXPECTED.get(node)
    if exp_keys is None:
        return None
    baseline = _num(exp.get(exp_keys[0]))
    if baseline is None:
        return None
    for k in _NODE_ACTUAL_KEYS.get(node, []):
        if k in act:
            actual = _num(act[k])
            if actual is not None:
                return _sign(actual - baseline)
    return None


def _edge_confirmed(
    actions: dict[str, float], exp: dict, act: dict, source: str, target: str, relationship: str
) -> bool | None:
    """Did both ends of this specific edge move consistently with its
    hypothesised sign for this recorded outcome? None when either end
    wasn't observed."""
    sd = _node_change_dir(actions, exp, act, source)
    td = _node_change_dir(actions, exp, act, target)
    if sd in (0, None) or td in (0, None):
        return None
    expected_same_direction = relationship == "positive"
    observed_same_direction = sd == td
    return observed_same_direction == expected_same_direction


def _latest_graph(db: Session, business_id: str) -> CausalGraph | None:
    return (
        db.query(CausalGraph)
        .filter(CausalGraph.business_id == business_id)
        .order_by(CausalGraph.created_at.desc())
        .first()
    )


def _edges_acted_on(decision: Decision) -> set[tuple[str, str, str]]:
    """(source, target, relationship) triples the chosen strategy's causal
    pathways touch, from the decision's stored causal context."""
    ctx = decision.causal_context_json or {}
    out: set[tuple[str, str, str]] = set()
    for p in ctx.get("pathways", []):
        for link in p.get("links", []):
            if link.get("source") and link.get("target"):
                out.add((link["source"], link["target"], link.get("relationship", "positive")))
    return out


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

    candidate_triples = _edges_acted_on(decision)
    if not candidate_triples:
        return []

    edge_rows = {
        (e.source_node, e.target_node): e
        for e in db.query(CausalEdge).filter(CausalEdge.causal_graph_id == graph.id).all()
    }
    upgradable = [
        (s, t, rel)
        for (s, t, rel) in candidate_triples
        if (s, t) in edge_rows and edge_rows[(s, t)].evidence_type == ASSUMED
    ]
    if not upgradable:
        return []

    # Candidate supporting decisions: same business, strategy shares an
    # action lever with this decision (so the same edge could plausibly
    # have been exercised).
    lever_action_types = _action_types_of(db, decision)
    business_decisions = db.query(Decision).filter(Decision.business_id == business_id).all()
    dec_outcomes: list[tuple[Decision, DecisionOutcome, dict, dict, dict]] = []
    for d in business_decisions:
        if lever_action_types and not (_action_types_of(db, d) & lever_action_types):
            continue
        o = db.query(DecisionOutcome).filter(DecisionOutcome.decision_id == d.id).first()
        if o is None:
            continue
        dec_outcomes.append(
            (d, o, _action_map(db, d), d.expected_outcome_json or {}, o.actual_outcome_json or {})
        )

    # Per-edge verdicts.
    per_edge: dict[tuple[str, str], dict] = {}
    for (s, t, rel) in upgradable:
        verdicts: list[tuple[str, str, bool]] = []
        for (d, o, actions, exp, act) in dec_outcomes:
            v = _edge_confirmed(actions, exp, act, s, t, rel)
            if v is None:
                continue
            verdicts.append((d.id, o.id, v))
        n = len(verdicts)
        consistent = sum(1 for (_d, _o, ok) in verdicts if ok)
        if n >= MIN_OUTCOMES_FOR_OBSERVATIONAL and consistent / n >= CONSISTENCY_THRESHOLD:
            per_edge[(s, t)] = {
                "relationship": rel,
                "sample_size": n,
                "consistent": consistent,
                "decision_ids": [d for (d, _o, _ok) in verdicts],
                "outcome_ids": [o for (_d, o, _ok) in verdicts],
            }

    if not per_edge:
        return []

    # New graph version: copy edges, apply only the per-edge upgrades.
    version_count = db.query(CausalGraph).filter(CausalGraph.business_id == business_id).count()
    new_graph = CausalGraph(
        business_id=business_id,
        version=f"v{version_count + 1}",
        graph_json=dict(graph.graph_json or {}),
        method=(graph.method or "") + "+outcome_feedback",
        evidence_summary=(
            f"{len(per_edge)} edge(s) lifted ASSUMED->OBSERVATIONAL from per-edge outcome feedback "
            f"(see causal_evidence_updates). {graph.evidence_summary or ''}"
        ).strip(),
    )
    db.add(new_graph)
    db.flush()

    updates: list[CausalEvidenceUpdate] = []
    for (src, tgt), old_edge in edge_rows.items():
        upgrade = per_edge.get((src, tgt))
        db.add(
            CausalEdge(
                causal_graph_id=new_graph.id,
                source_node=old_edge.source_node,
                target_node=old_edge.target_node,
                relationship=old_edge.relationship,
                strength=old_edge.strength,
                confidence=old_edge.confidence,
                evidence_type=OBSERVATIONAL if upgrade else old_edge.evidence_type,
                time_lag=old_edge.time_lag,
            )
        )
        if upgrade:
            rationale = (
                f"{upgrade['consistent']}/{upgrade['sample_size']} recorded interventions moved "
                f"'{src}' and '{tgt}' consistently with the hypothesised '{upgrade['relationship']}' "
                f"relationship (per-edge; threshold {CONSISTENCY_THRESHOLD:.2f}, minimum "
                f"{MIN_OUTCOMES_FOR_OBSERVATIONAL}). Observational support only — not identified "
                "causation, and not the Granger 'data_supported' bar."
            )
            upd = CausalEvidenceUpdate(
                business_id=business_id,
                causal_graph_id=new_graph.id,
                graph_version=new_graph.version,
                source_node=src,
                target_node=tgt,
                previous_evidence=ASSUMED,
                new_evidence=OBSERVATIONAL,
                method=CAUSAL_FEEDBACK_METHOD,
                rationale=rationale,
                supporting_decision_ids_json=upgrade["decision_ids"],
                supporting_outcome_ids_json=upgrade["outcome_ids"],
                sample_size=upgrade["sample_size"],
                consistent_direction_count=upgrade["consistent"],
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
