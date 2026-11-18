"""Business Health assessment — a transparent, versioned, heuristic indicator (``health-v1``).

This is NOT a validated predictor of business success. Each component is a simple, disclosed rule over the owner's own records;
the composite is a weighted average over the components that CAN be calculated. A component with missing inputs is reported as
unavailable and is left out (its weight is redistributed) — missing information is never scored as poor performance. If too little
is available, no composite is produced and only the component assessment is returned.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.analytics import kpi_service
from app.core import clock
from app.models.customer import Customer
from app.models.inventory import InventoryRecord
from app.models.platform import HealthSnapshot
from app.services import kpi_monitor_service as kms

VERSION = "health-v1"
MIN_COMPONENTS = 3
MIN_AVAILABLE_WEIGHT = 0.5
LEVELS = ((75.0, "Good"), (50.0, "Fair"), (0.0, "Needs attention"))  # disclosed thresholds on the 0-100 composite

COMPONENTS = {
    "sales_trend": {
        "name": "Sales trend", "weight": 0.30,
        "rule": "Change in sales versus the previous equal period. -20% or worse = 0, no change = 60, +20% or better = 100 (linear in between).",
    },
    "data_freshness": {
        "name": "Data freshness", "weight": 0.15,
        "rule": "Days since the newest sale (measured to today). 7 days or fewer = 100, 60 days or more = 0 (linear in between).",
    },
    "profit_margin": {
        "name": "Profit margin", "weight": 0.20,
        "rule": "Profit ÷ sales over sales with a recorded product cost. 0% or less = 0, 30% or more = 100 (linear in between).",
    },
    "stock_health": {
        "name": "Stock health", "weight": 0.15,
        "rule": "Share of products with a reorder level whose latest stock is above it, × 100.",
    },
    "customer_activity": {
        "name": "Customer activity", "weight": 0.20,
        "rule": "Share of customers (with a last-purchase date) who bought in the 90 days before the period end, × 100. Needs at least 10 customers.",
    },
}


def _clamp(x: float) -> float:
    return max(0.0, min(100.0, x))


def _level(score: float) -> str:
    return next(label for floor, label in LEVELS if score >= floor)


def _components(db: Session, business_id: str, period_days: int, end: date) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}

    def put(key: str, score: float | None, detail: str, evidence: dict[str, Any] | None = None, reason: str | None = None) -> None:
        c = COMPONENTS[key]
        out[key] = {
            "key": key, "name": c["name"], "weight": c["weight"], "rule": c["rule"],
            "available": score is not None, "score": None if score is None else round(score, 1),
            "detail": detail, "evidence": evidence or {}, "unavailable_reason": reason,
        }

    cur = kpi_service.compute_kpis(db, business_id, period_days, end=end)
    cmp_ = kms.revenue_change(db, business_id, period_days, end)

    # sales trend
    if cmp_.change_pct is None or cur.orders == 0:
        put("sales_trend", None, "", reason="Needs sales in both this period and the one before it.")
    else:
        ch = cmp_.change_pct
        score = max(0.0, 60 * (1 + ch / 0.20)) if ch < 0 else 60 + 40 * min(ch / 0.20, 1.0)
        put("sales_trend", score, f"Sales changed {ch * 100:+.1f}% versus the previous {period_days} days.",
            {"current_sales": cmp_.current_revenue, "previous_sales": cmp_.previous_revenue})

    # freshness
    latest = kms.latest_sale_date(db, business_id)
    if latest is None:
        put("data_freshness", None, "", reason="No sales have been recorded.")
    else:
        days = (clock.today() - latest).days
        put("data_freshness", _clamp(100 * (60 - days) / 53) if days > 7 else 100.0,
            f"The newest sale is {days} days old.", {"latest_sale": latest.isoformat(), "days_old": days})

    # margin
    if cur.profit is None or cur.revenue <= 0:
        put("profit_margin", None, "", reason="Needs product costs and sales in the period.")
    else:
        costed_note = next((n for n in cur.notes if n.startswith("Profit computed from")), None)
        margin = cur.profit / cur.revenue
        put("profit_margin", _clamp(100 * margin / 0.30), f"Profit is {margin * 100:.1f}% of sales.",
            {"profit": cur.profit, "sales": cur.revenue, **({"coverage_note": costed_note} if costed_note else {})})

    # stock
    latest_by_product: dict[str, InventoryRecord] = {}
    for rec in db.query(InventoryRecord).filter(InventoryRecord.business_id == business_id).order_by(InventoryRecord.product_id, InventoryRecord.date):
        latest_by_product[rec.product_id] = rec
    tracked = [r for r in latest_by_product.values() if r.reorder_level is not None]
    if not tracked:
        put("stock_health", None, "", reason="Needs stock records with a reorder level.")
    else:
        ok = sum(1 for r in tracked if r.stock_level > r.reorder_level)
        put("stock_health", 100 * ok / len(tracked), f"{ok} of {len(tracked)} tracked products are above their reorder level.",
            {"tracked_products": len(tracked), "above_reorder_level": ok})

    # customers
    rows = db.query(Customer.last_purchase_date).filter(Customer.business_id == business_id, Customer.last_purchase_date.isnot(None)).all()
    if len(rows) < 10:
        put("customer_activity", None, "", reason="Needs at least 10 customers with a last-purchase date.")
    else:
        recent = sum(1 for (d,) in rows if (end - d).days <= 90 and d <= end)
        put("customer_activity", 100 * recent / len(rows), f"{recent} of {len(rows)} customers bought in the 90 days before {end.isoformat()}.",
            {"customers": len(rows), "bought_recently": recent})
    return out


def assess(db: Session, business_id: str, period_days: int = 30, anchor: str = "today", save: bool = True) -> dict[str, Any]:
    if period_days not in kms.ALLOWED_PERIODS:
        raise kms.KpiValidationError(f"period_days must be one of {list(kms.ALLOWED_PERIODS)}.")
    end = kms.resolve_end(db, business_id, anchor)
    comps = _components(db, business_id, period_days, end)
    avail = [c for c in comps.values() if c["available"]]
    nominal = sum(c["weight"] for c in comps.values())
    avail_w = sum(c["weight"] for c in avail)
    composite = None
    reason = None
    if len(avail) >= MIN_COMPONENTS and avail_w / nominal >= MIN_AVAILABLE_WEIGHT:
        composite = round(sum(c["weight"] * c["score"] for c in avail) / avail_w, 1)
    else:
        reason = (
            f"A composite needs at least {MIN_COMPONENTS} calculable components covering at least {int(MIN_AVAILABLE_WEIGHT * 100)}% of the weight; "
            f"only {len(avail)} component(s) ({avail_w / nominal * 100:.0f}% of the weight) can be calculated from your data."
        )
    for c in comps.values():
        c["effective_weight"] = round(c["weight"] / avail_w, 3) if c["available"] and avail_w else None
        c["contribution"] = round(c["effective_weight"] * c["score"], 1) if c["available"] and avail_w else None
    result = {
        "version": VERSION,
        "period": {"days": period_days, "end": end.isoformat(), "anchor": anchor},
        "calculated_at": clock.today().isoformat(),
        "composite_score": composite,
        "level": _level(composite) if composite is not None else None,
        "level_thresholds": [{"min": f, "label": label} for f, label in LEVELS],
        "composite_unavailable_reason": reason,
        "available_weight_share": round(avail_w / nominal, 3),
        "components": list(comps.values()),
        "limitations": [
            "A heuristic summary of a few indicators in your own records. It has not been validated as a predictor of business success.",
            "Components whose data is missing are left out, not scored as poor; the remaining weights are rescaled to 100%.",
            "Weights and thresholds are fixed in this version and shown above; they are not tuned to your business.",
        ],
    }
    if save:
        db.add(HealthSnapshot(business_id=business_id, version=VERSION, score=composite, period_days=period_days,
                              available_weight=avail_w / nominal, payload_json=result))
        db.commit()
    return result


def history(db: Session, business_id: str, limit: int = 30) -> list[dict[str, Any]]:
    rows = (db.query(HealthSnapshot).filter(HealthSnapshot.business_id == business_id)
            .order_by(HealthSnapshot.created_at.desc()).limit(max(1, min(limit, 200))).all())
    return [{"id": r.id, "version": r.version, "score": r.score, "period_days": r.period_days,
             "available_weight": r.available_weight, "created_at": r.created_at.isoformat() if r.created_at else None} for r in rows]
