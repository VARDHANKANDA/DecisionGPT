"""Causal context for the decision pipeline — docs/CAUSAL_GRAPH_SPECIFICATION.md §7 / §8.

Turns "here is a strategy" into "here are the causal pathways this strategy
acts on, and how well-evidenced each link is", so the Digital Twin,
the agents, and the final explanation can all reason about *why* an action
is expected to move revenue — not just that the forecasting model's output
changed.

Every edge keeps its evidence metadata verbatim from the stored causal
graph (ASSUMED / OBSERVATIONAL / DATA_SUPPORTED / CAUSALLY_VALIDATED).
Nothing here upgrades an evidence label or invents an edge — it only reads
and traverses what causal_graph_service already computed and stored
(AGENTS.md "the LLM / any module must not invent causal relationships").
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.analytics import causal_graph_service
from app.analytics.causal_graph_service import HYPOTHESIS_EDGES
from app.core.errors import AppError

# Which causal-graph node a supported Digital Twin action operates on.
ACTION_START_NODE = {
    "marketing_change": "marketing_spend",
    "price_change": "price",
    "inventory_change": "inventory",
}

SINK_NODES = ("revenue", "profit")

# Ordered strongest -> weakest, for "what's the best evidence on this path".
EVIDENCE_RANK = ["assumed", "observational", "data_supported", "causally_validated"]


@dataclass
class CausalLink:
    source: str
    target: str
    relationship: str
    evidence_type: str
    strength: float | None
    confidence: float | None
    time_lag: int | None


@dataclass
class CausalPathway:
    start_node: str
    nodes: list[str]
    links: list[CausalLink]
    weakest_evidence: str  # the path is only as strong as its weakest link


@dataclass
class CausalContext:
    graph_id: str | None
    graph_version: str | None
    method: str | None
    built: bool
    pathways: list[CausalPathway] = field(default_factory=list)
    strongest_pathway_evidence: str = "assumed"
    summary: str = ""
    caveats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "graph_id": self.graph_id,
            "graph_version": self.graph_version,
            "method": self.method,
            "built": self.built,
            "strongest_pathway_evidence": self.strongest_pathway_evidence,
            "summary": self.summary,
            "caveats": self.caveats,
            "pathways": [
                {
                    "start_node": p.start_node,
                    "nodes": p.nodes,
                    "weakest_evidence": p.weakest_evidence,
                    "links": [
                        {
                            "source": l.source,
                            "target": l.target,
                            "relationship": l.relationship,
                            "evidence_type": l.evidence_type,
                            "strength": l.strength,
                            "confidence": l.confidence,
                            "time_lag": l.time_lag,
                        }
                        for l in p.links
                    ],
                }
                for p in self.pathways
            ],
        }


def disabled_context() -> CausalContext:
    """A causal context for an ablation run where the Dynamic Causal Graph
    is switched off entirely. ``built=False`` so agents skip all
    causal-evidence logic and confidence is not causally adjusted."""
    return CausalContext(
        graph_id=None,
        graph_version=None,
        method="disabled",
        built=False,
        summary="Dynamic Causal Graph disabled for this run (ablation).",
        caveats=["Causal graph disabled — no causal pathways were consulted."],
    )


def _forward_adjacency() -> dict[str, list[str]]:
    adj: dict[str, list[str]] = {}
    for source, target, _direction in HYPOTHESIS_EDGES:
        adj.setdefault(source, []).append(target)
    return adj


def _paths_to_sinks(start: str, adjacency: dict[str, list[str]], max_depth: int = 6) -> list[list[str]]:
    """All simple forward paths from ``start`` to any SINK node."""
    results: list[list[str]] = []

    def walk(node: str, path: list[str]) -> None:
        if len(path) > max_depth:
            return
        if node in SINK_NODES and len(path) > 1:
            results.append(list(path))
            # keep walking: revenue -> profit is itself an edge
        for nxt in adjacency.get(node, []):
            if nxt in path:  # no cycles
                continue
            walk(nxt, path + [nxt])

    walk(start, [start])
    return results


def _rank(evidence: str) -> int:
    try:
        return EVIDENCE_RANK.index(evidence)
    except ValueError:
        return 0


def get_causal_context(
    db: Session,
    business_id: str,
    action_types: list[str],
    extra_targets: list[str] | None = None,
    auto_build: bool = True,
) -> CausalContext:
    """Build the causal context for a strategy defined by ``action_types``.

    If no causal graph exists yet and ``auto_build`` is set, one is built
    from the business's own data first (same call the /causal-graph/build
    endpoint makes). If it still can't be built (insufficient history), an
    honest "assumed-only" context is returned rather than raising.
    """
    graph = None
    try:
        graph = causal_graph_service.get_latest_causal_graph(db, business_id)
    except AppError:
        if auto_build:
            try:
                graph = causal_graph_service.build_causal_graph(db, business_id)
            except AppError:
                graph = None

    start_nodes = [ACTION_START_NODE[a] for a in action_types if a in ACTION_START_NODE]
    # ``extra_targets`` (the candidate strategy's declared target nodes) are
    # kept as roots only when the actions themselves map to nothing in the
    # graph — otherwise pathways always start from the real action lever.
    if not start_nodes:
        start_nodes = [t for t in (extra_targets or []) if t in _forward_adjacency()]

    if graph is None:
        return CausalContext(
            graph_id=None, graph_version=None, method=None, built=False,
            summary=(
                "No causal graph could be built for this business yet (not enough history). "
                "Strategy pathways are treated as unvalidated domain assumptions."
            ),
            caveats=["Causal graph unavailable — all pathways ASSUMED."],
        )

    # Map stored edges by (source, target) for evidence lookup.
    edge_lookup: dict[tuple[str, str], object] = {
        (e.source_node, e.target_node): e for e in graph.edges
    }
    adjacency = _forward_adjacency()

    pathways: list[CausalPathway] = []
    for start in start_nodes:
        for node_path in _paths_to_sinks(start, adjacency):
            links: list[CausalLink] = []
            weakest = "causally_validated"
            for a, b in zip(node_path, node_path[1:]):
                e = edge_lookup.get((a, b))
                ev = e.evidence_type if e is not None else "assumed"
                if _rank(ev) < _rank(weakest):
                    weakest = ev
                links.append(
                    CausalLink(
                        source=a,
                        target=b,
                        relationship=(e.relationship if e is not None else "positive"),
                        evidence_type=ev,
                        strength=(float(e.strength) if e is not None and e.strength is not None else None),
                        confidence=(float(e.confidence) if e is not None and e.confidence is not None else None),
                        time_lag=(e.time_lag if e is not None else None),
                    )
                )
            if links:
                pathways.append(
                    CausalPathway(
                        start_node=start, nodes=node_path, links=links, weakest_evidence=weakest
                    )
                )

    # Deduplicate identical node paths, keep the shortest per (start, sink).
    seen: set = set()
    unique: list[CausalPathway] = []
    for p in sorted(pathways, key=lambda x: len(x.nodes)):
        key = (p.nodes[0], p.nodes[-1])
        sig = tuple(p.nodes)
        if sig in seen:
            continue
        seen.add(sig)
        unique.append(p)

    strongest = "assumed"
    for p in unique:
        if _rank(p.weakest_evidence) > _rank(strongest):
            strongest = p.weakest_evidence

    if unique:
        parts = []
        for p in unique[:4]:
            chain = " -> ".join(p.nodes)
            parts.append(f"{chain} (weakest link: {p.weakest_evidence.replace('_', ' ')})")
        summary = "Causal pathways this strategy acts on: " + "; ".join(parts) + "."
    else:
        summary = "No causal pathway from this strategy's levers to revenue/profit is present in the graph."

    caveats: list[str] = []
    if strongest == "assumed":
        caveats.append(
            "No pathway for this strategy has above-ASSUMED evidence in this business's data — "
            "the projected effect is a domain hypothesis, not a data-supported causal claim."
        )
    data_supported = [p for p in unique if _rank(p.weakest_evidence) >= _rank("data_supported")]
    if data_supported:
        caveats.append(
            f"{len(data_supported)} pathway(s) are DATA_SUPPORTED end-to-end (significant lagged "
            "relationships in this business's own history)."
        )
    caveats.append(
        "DATA_SUPPORTED means predictive precedence (Granger), not identified causation — "
        "unmeasured confounders are still possible."
    )

    return CausalContext(
        graph_id=graph.id,
        graph_version=graph.version,
        method=graph.method,
        built=True,
        pathways=unique,
        strongest_pathway_evidence=strongest,
        summary=summary,
        caveats=caveats,
    )


def evidence_confidence_factor(context: CausalContext) -> float:
    """A multiplier in [0.6, 1.0] applied to the decision's confidence,
    reflecting how well-evidenced the causal story behind the chosen
    strategy is. Documented, not arbitrary:

    - assumed only        -> 0.6
    - observational       -> 0.75
    - data_supported      -> 0.9
    - causally_validated  -> 1.0

    When the causal layer was not built/consulted at all (``built=False``),
    there is nothing to down-weight for, so this returns 1.0.
    """
    if not context.built:
        return 1.0
    return {
        "assumed": 0.6,
        "observational": 0.75,
        "data_supported": 0.9,
        "causally_validated": 1.0,
    }.get(context.strongest_pathway_evidence, 0.6)
