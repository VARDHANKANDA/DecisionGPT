"""Research Console — Causal Graph Evaluation (docs Phase 4/5,
docs/CAUSAL_GRAPH_SPECIFICATION.md §3, §9).

Three honest sections:

1. Graph overview — real stored CausalGraph / CausalEdge data across
   businesses: versions, node/edge counts, evidence-level counts.
2. Method validation — the latest synthetic causal-recovery experiment
   (Granger vs a KNOWN ground-truth structure). This validates the
   *method*, never a business's graph. Clearly labelled as such.
3. Outcome-feedback log — every conservative ASSUMED->OBSERVATIONAL edge
   change made from real decision outcomes (causal_feedback_service).

There is no registered ground-truth causal graph for any real business, so
quantitative business-graph recovery accuracy is NOT reported — the page
says so rather than inventing a number.
"""
from collections import Counter

from sqlalchemy.orm import Session

from app.models.causal import CausalEdge, CausalGraph
from app.models.experiment import ExperimentRun
from app.services import causal_feedback_service

EVIDENCE_LEVELS = ["assumed", "observational", "data_supported", "causally_validated"]


def _graph_summary(db: Session, graph: CausalGraph) -> dict:
    edges = db.query(CausalEdge).filter(CausalEdge.causal_graph_id == graph.id).all()
    counts = Counter(e.evidence_type for e in edges)
    nodes = set()
    for e in edges:
        nodes.add(e.source_node)
        nodes.add(e.target_node)
    return {
        "graph_id": graph.id,
        "business_id": graph.business_id,
        "version": graph.version,
        "method": graph.method,
        "created_at": graph.created_at.isoformat() if graph.created_at else None,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "evidence_counts": {lvl: counts.get(lvl, 0) for lvl in EVIDENCE_LEVELS},
        "edges": [
            {
                "source": e.source_node,
                "target": e.target_node,
                "relationship": e.relationship,
                "evidence_type": e.evidence_type,
                "strength": float(e.strength) if e.strength is not None else None,
                "confidence": float(e.confidence) if e.confidence is not None else None,
                "time_lag": e.time_lag,
            }
            for e in edges
        ],
    }


def _latest_per_business(graphs: list[CausalGraph]) -> list[CausalGraph]:
    latest: dict[str, CausalGraph] = {}
    for g in sorted(graphs, key=lambda x: x.created_at or 0):
        latest[g.business_id] = g
    return list(latest.values())


def _method_validation(db: Session) -> dict | None:
    run = (
        db.query(ExperimentRun)
        .filter(ExperimentRun.experiment_type == "causal", ExperimentRun.status == "completed")
        .order_by(ExperimentRun.created_at.desc())
        .first()
    )
    if run is None:
        return None
    m = run.metrics_json or {}
    gt = {tuple(e) for e in m.get("ground_truth_edges", [])}
    pred = {tuple(e) for e in m.get("predicted_edges", [])}
    p = m.get("precision")
    r = m.get("recall")
    f1 = (2 * p * r / (p + r)) if isinstance(p, (int, float)) and isinstance(r, (int, float)) and (p + r) else None
    return {
        "experiment_id": run.id,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "seed": run.random_seed,
        "label": "SYNTHETIC_METHOD_VALIDATION",
        "precision": p,
        "recall": r,
        "f1": round(f1, 4) if f1 is not None else None,
        "structural_hamming_distance": m.get("structural_hamming_distance"),
        "recovered_edges": [list(e) for e in sorted(gt & pred)],
        "missing_edges": [list(e) for e in sorted(gt - pred)],
        "extra_edges": [list(e) for e in sorted(pred - gt)],
        "notes": m.get("notes", []),
    }


def get_causal_graph_evaluation(db: Session) -> dict:
    all_graphs = db.query(CausalGraph).all()
    latest_graphs = _latest_per_business(all_graphs)

    total_evidence = Counter()
    for g in latest_graphs:
        s = _graph_summary(db, g)
        for lvl, c in s["evidence_counts"].items():
            total_evidence[lvl] += c

    empty_state = None
    if not all_graphs:
        empty_state = (
            "No causal graph has been built for any business yet. A causal graph is built the first "
            "time a decision is analysed, or via POST /businesses/{id}/causal-graph/build."
        )

    return {
        "overview": {
            "total_graph_versions": len(all_graphs),
            "businesses_with_a_graph": len({g.business_id for g in all_graphs}),
            "evidence_counts_latest_per_business": {lvl: total_evidence.get(lvl, 0) for lvl in EVIDENCE_LEVELS},
        },
        "graphs": [_graph_summary(db, g) for g in sorted(latest_graphs, key=lambda x: x.created_at or 0, reverse=True)],
        "method_validation": _method_validation(db),
        "ground_truth_comparison": {
            "available": False,
            "message": (
                "No ground-truth causal graph is registered for quantitative graph-recovery evaluation "
                "against a real business. The synthetic method-validation experiment above is the only "
                "quantitative causal-recovery result available."
            ),
        },
        "evidence_feedback_log": causal_feedback_service.get_feedback_log(db),
        "empty_state": empty_state,
    }
