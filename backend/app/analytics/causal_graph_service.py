"""Dynamic Causal Graph — docs/CAUSAL_GRAPH_SPECIFICATION.md.

Builds the domain hypothesis graph (§2) and, for every edge whose two ends
are both things this business actually has daily data for, tries to
upgrade its evidence label using real statistics computed on that
business's own history (ml/causal/granger.py) — see §6 "Methods":
domain-informed graph -> statistical relationship estimation -> one
selected causal method (Granger causality, chosen here because the data is
business time series and the effect is naturally lagged, e.g. this week's
marketing spend affecting next week's orders).

Evidence labels (§3) are deliberately conservative:
- ASSUMED: no test was run, or the test found nothing / the wrong direction.
- OBSERVATIONAL: a significant same-day correlation in the hypothesized direction.
- DATA_SUPPORTED: a significant Granger-causality result (source's past
  significantly improves predicting target) *and* the direction at that
  lag matches the hypothesis.
- CAUSALLY_VALIDATED is never assigned here — Granger causality is
  predictive precedence, not identified causation (unmeasured confounders,
  e.g. a big sale event, can drive both sides). This label is reserved for
  edges checked against real intervention outcomes (docs/RESEARCH_
  SPECIFICATION.md's Digital Twin Evaluation), which is a separate,
  explicit research step — never silently inferred here.

Several hypothesis nodes (website_traffic, conversion_rate,
customer_experience, retention, repeat_purchases, availability) have no
corresponding column anywhere in the business data schema (docs/
DATA_SPECIFICATION.md) — those edges always stay ASSUMED, honestly, rather
than testing a loosely-related proxy and mislabeling it.
"""
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.analytics import forecast_service
from app.core.errors import InsufficientDataError
from app.models.causal import CausalEdge, CausalGraph
from app.models.inventory import InventoryRecord
from app.models.product import Product
from app.models.sale import Sale
from ml.causal.granger import MIN_PAIRED_OBSERVATIONS, best_granger_result, correlation

# node -> the daily-series column that measures it in this business's data.
# "demand" and "sales" both mean the same measured quantity (units sold per
# day) in our schema, so that specific edge is intentionally excluded from
# testing below (it isn't two independent things to correlate).
NODE_COLUMNS = {
    "marketing_spend": "marketing_spend",
    "price": "price",
    "demand": "units_sold",
    "sales": "units_sold",
    "orders": "orders",
    "revenue": "revenue",
    "profit": "profit",
    "inventory": "inventory",
}

# (source, target, hypothesized direction) — docs/CAUSAL_GRAPH_SPECIFICATION.md §2.
HYPOTHESIS_EDGES = [
    ("marketing_spend", "website_traffic", "positive"),
    ("website_traffic", "conversion_rate", "positive"),
    ("conversion_rate", "orders", "positive"),
    ("orders", "revenue", "positive"),
    ("revenue", "profit", "positive"),
    ("price", "demand", "negative"),
    ("demand", "sales", "positive"),
    ("sales", "revenue", "positive"),
    ("customer_experience", "retention", "positive"),
    ("retention", "repeat_purchases", "positive"),
    ("repeat_purchases", "revenue", "positive"),
    ("inventory", "availability", "positive"),
    ("availability", "sales", "positive"),
]

MAX_GRANGER_LAG = 3


@dataclass
class EdgeResult:
    source_node: str
    target_node: str
    relationship: str
    strength: float | None
    confidence: float | None
    evidence_type: str
    time_lag: int | None
    note: str


@dataclass
class CausalGraphResult:
    id: str
    business_id: str
    version: str
    method: str
    evidence_summary: str
    created_at: datetime | None
    edges: list[EdgeResult] = field(default_factory=list)


def _daily_orders(db: Session, business_id: str) -> pd.DataFrame:
    rows = (
        db.query(Sale.sale_date, func.count(Sale.id))
        .filter(Sale.business_id == business_id)
        .group_by(Sale.sale_date)
        .all()
    )
    df = pd.DataFrame(rows, columns=["date", "orders"])
    df["date"] = pd.to_datetime(df["date"])
    return df


def _daily_profit(db: Session, business_id: str) -> pd.DataFrame | None:
    costs = {
        p.id: float(p.unit_cost)
        for p in db.query(Product).filter(Product.business_id == business_id).all()
        if p.unit_cost is not None
    }
    if not costs:
        return None
    sales = (
        db.query(Sale)
        .filter(Sale.business_id == business_id, Sale.product_id.in_(costs.keys()))
        .all()
    )
    if not sales:
        return None
    rows = [
        {"date": s.sale_date, "profit": float(s.revenue) - costs[s.product_id] * s.quantity}
        for s in sales
    ]
    df = pd.DataFrame(rows).groupby("date", as_index=False)["profit"].sum()
    df["date"] = pd.to_datetime(df["date"])
    return df


def _daily_inventory(db: Session, business_id: str) -> pd.DataFrame | None:
    rows = (
        db.query(InventoryRecord.date, func.sum(InventoryRecord.stock_level))
        .filter(InventoryRecord.business_id == business_id)
        .group_by(InventoryRecord.date)
        .all()
    )
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["date", "inventory"])
    df["date"] = pd.to_datetime(df["date"])
    return df


def _build_node_series(db: Session, business_id: str) -> pd.DataFrame:
    daily = forecast_service.build_daily_series(db, business_id)
    if daily.empty:
        return daily

    merged = daily.copy()
    merged["date"] = pd.to_datetime(merged["date"])
    merged["revenue"] = merged["price"] * merged["units_sold"]
    merged = merged.merge(_daily_orders(db, business_id), on="date", how="left")

    profit = _daily_profit(db, business_id)
    merged = merged.merge(profit, on="date", how="left") if profit is not None else merged.assign(profit=np.nan)

    inventory = _daily_inventory(db, business_id)
    merged = (
        merged.merge(inventory, on="date", how="left") if inventory is not None else merged.assign(inventory=np.nan)
    )

    return merged


def _evaluate_edge(series: pd.DataFrame, source: str, target: str, expected_direction: str) -> EdgeResult:
    source_col = NODE_COLUMNS.get(source)
    target_col = NODE_COLUMNS.get(target)

    if source_col is None or target_col is None:
        missing = source if source_col is None else target
        return EdgeResult(
            source, target, expected_direction, None, None, "assumed",
            None, f"'{missing}' isn't a metric collected in the business data schema — untested domain hypothesis.",
        )
    if source_col == target_col:
        return EdgeResult(
            source, target, expected_direction, None, None, "assumed",
            None, f"'{source}' and '{target}' are measured by the same underlying value in your data — not "
            "independently testable.",
        )

    pair = series[["date", source_col, target_col]].dropna()
    if len(pair) < MIN_PAIRED_OBSERVATIONS:
        return EdgeResult(
            source, target, expected_direction, None, None, "assumed",
            None, f"Only {len(pair)} overlapping days of data for both metrics — at least "
            f"{MIN_PAIRED_OBSERVATIONS} are needed to test this statistically.",
        )

    source_arr = pair[source_col].to_numpy(dtype=float)
    target_arr = pair[target_col].to_numpy(dtype=float)

    granger = best_granger_result(source_arr, target_arr, max_lag=MAX_GRANGER_LAG)
    if granger is not None:
        lag, granger_p = granger
        lag_corr = (
            correlation(source_arr[:-lag], target_arr[lag:]) if lag > 0 else correlation(source_arr, target_arr)
        )
        if granger_p < 0.05 and lag_corr is not None:
            r, _ = lag_corr
            direction = "positive" if r > 0 else "negative"
            if direction == expected_direction:
                return EdgeResult(
                    source, target, direction, round(r, 4), round(1 - granger_p, 4), "data_supported", lag,
                    f"'{source}' at t-{lag} significantly improves predicting '{target}' beyond its own history "
                    f"(Granger p={granger_p:.4g}), direction matches the hypothesis.",
                )
            return EdgeResult(
                source, target, expected_direction, round(r, 4), None, "assumed", lag,
                f"A significant lagged relationship exists (Granger p={granger_p:.4g}) but its direction "
                f"('{direction}') contradicts the hypothesized '{expected_direction}' relationship.",
            )

    same_day = correlation(source_arr, target_arr)
    if same_day is not None:
        r, p = same_day
        if p < 0.05:
            direction = "positive" if r > 0 else "negative"
            if direction == expected_direction:
                return EdgeResult(
                    source, target, direction, round(r, 4), round(1 - p, 4), "observational", 0,
                    f"Same-day correlation r={r:.2f} (p={p:.4g}) matches the hypothesized direction.",
                )
            return EdgeResult(
                source, target, expected_direction, round(r, 4), None, "assumed", None,
                f"Same-day correlation (r={r:.2f}, p={p:.4g}) contradicts the hypothesized "
                f"'{expected_direction}' relationship.",
            )
        return EdgeResult(
            source, target, expected_direction, None, None, "assumed", None,
            f"No statistically significant relationship found in your data (p={p:.4g}).",
        )

    return EdgeResult(
        source, target, expected_direction, None, None, "assumed", None,
        "Not enough variation in your data to test this relationship.",
    )


def build_causal_graph(db: Session, business_id: str) -> CausalGraphResult:
    sufficient, reason = forecast_service.check_forecast_sufficiency(db, business_id)
    if not sufficient:
        raise InsufficientDataError(reason or "Not enough sales history to build a causal graph.")

    series = _build_node_series(db, business_id)

    edges = [_evaluate_edge(series, source, target, direction) for source, target, direction in HYPOTHESIS_EDGES]

    tested = sum(1 for e in edges if e.evidence_type != "assumed")
    evidence_summary = (
        f"{tested}/{len(edges)} edges upgraded beyond 'assumed' from this business's own data "
        f"({len(series)} days of history). The rest remain domain hypotheses — either the metric "
        "isn't collected, or no statistically significant relationship was found."
    )

    version_count = db.query(CausalGraph).filter(CausalGraph.business_id == business_id).count()
    graph_row = CausalGraph(
        business_id=business_id,
        version=f"v{version_count + 1}",
        graph_json={"nodes": sorted({n for e in HYPOTHESIS_EDGES for n in (e[0], e[1])})},
        method="domain_hypothesis+pearson_correlation+granger_causality",
        evidence_summary=evidence_summary,
    )
    db.add(graph_row)
    db.flush()

    edge_rows = [
        CausalEdge(
            causal_graph_id=graph_row.id,
            source_node=e.source_node,
            target_node=e.target_node,
            relationship=e.relationship,
            strength=e.strength,
            confidence=e.confidence,
            evidence_type=e.evidence_type,
            time_lag=e.time_lag,
        )
        for e in edges
    ]
    db.add_all(edge_rows)
    db.commit()
    db.refresh(graph_row)

    return CausalGraphResult(
        id=graph_row.id,
        business_id=business_id,
        version=graph_row.version,
        method=graph_row.method,
        evidence_summary=evidence_summary,
        created_at=graph_row.created_at,
        edges=edges,
    )


def get_latest_causal_graph(db: Session, business_id: str) -> CausalGraphResult:
    graph_row = (
        db.query(CausalGraph)
        .filter(CausalGraph.business_id == business_id)
        .order_by(CausalGraph.created_at.desc())
        .first()
    )
    if graph_row is None:
        raise InsufficientDataError(
            "No causal graph has been built yet for this business — "
            "call POST /causal-graph/build first."
        )
    edge_rows = db.query(CausalEdge).filter(CausalEdge.causal_graph_id == graph_row.id).all()
    edges = [
        EdgeResult(
            source_node=e.source_node,
            target_node=e.target_node,
            relationship=e.relationship,
            strength=float(e.strength) if e.strength is not None else None,
            confidence=float(e.confidence) if e.confidence is not None else None,
            evidence_type=e.evidence_type,
            time_lag=e.time_lag,
            note="",
        )
        for e in edge_rows
    ]
    return CausalGraphResult(
        id=graph_row.id,
        business_id=business_id,
        version=graph_row.version,
        method=graph_row.method,
        evidence_summary=graph_row.evidence_summary or "",
        created_at=graph_row.created_at,
        edges=edges,
    )
