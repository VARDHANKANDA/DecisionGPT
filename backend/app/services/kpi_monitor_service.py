"""KPI Monitoring: defined KPIs, owner-configured targets, trends and rule-based status.

Values come from ``kpi_service.compute_kpis`` (the one implementation of each business calculation); this module adds the
definitions, the persisted targets, the window selection and the status rule. Nothing here is hard-coded per business: a KPI
has a target only if the owner configured one, and a status is shown only from the disclosed rule below.

STATUS RULE (disclosed to the user): with a target T and direction "higher": met when value >= T, otherwise not met; direction
"lower": met when value <= T. No target -> no status. No data in the window -> "no data" (never red or green).
STALE RULE: the newest sale in the account is more than STALE_AFTER_DAYS days before today.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.analytics import kpi_service
from app.core import clock
from app.core.errors import AppError, NotFoundError
from app.models.marketing import MarketingCampaign
from app.models.platform import KpiTarget
from app.models.sale import Sale

STALE_AFTER_DAYS = 14
ALLOWED_PERIODS = (7, 30, 90, 365)


class KpiValidationError(AppError):
    code = "KPI_VALIDATION"
    http_status = 422


@dataclass(frozen=True)
class KpiDef:
    key: str
    name: str
    unit: str  # inr | count | percent
    definition: str
    source: str
    higher_is_better: bool = True


KPI_DEFS: dict[str, KpiDef] = {
    d.key: d
    for d in (
        KpiDef("revenue", "Sales", "inr", "Total value of sales recorded in the period.", "Sales records: sum of the total amount of each sale"),
        KpiDef("orders", "Orders", "count", "Number of sales records in the period.", "Sales records: count of rows"),
        KpiDef("customers", "Customers who bought", "count", "Different customers with at least one sale in the period.", "Sales records: distinct customer on each sale"),
        KpiDef("average_order_value", "Average order", "inr", "Sales divided by orders.", "Sales ÷ orders (undefined when there are no orders)"),
        KpiDef("profit", "Profit", "inr", "Sales minus recorded product cost, for sales whose product has a cost.", "Sales records and product cost each"),
        KpiDef("marketing_spend", "Marketing spend", "inr", "Money spent on campaigns dated in the period.", "Marketing records: sum of spend", higher_is_better=False),
        KpiDef("marketing_roi", "Return on marketing", "percent", "(Recorded campaign sales − spend) ÷ spend, over campaigns with recorded results.", "Marketing records with recorded results"),
    )
}


def _kpi_def(key: str) -> KpiDef:
    if key not in KPI_DEFS:
        raise NotFoundError(f"Unknown KPI '{key}'.")
    return KPI_DEFS[key]


def latest_sale_date(db: Session, business_id: str) -> date | None:
    return db.query(func.max(Sale.sale_date)).filter(Sale.business_id == business_id).scalar()


def resolve_end(db: Session, business_id: str, anchor: str) -> date:
    """'today' = the clock's today; 'latest' = the newest sale date (falls back to today when there are no sales)."""
    if anchor not in ("today", "latest"):
        raise KpiValidationError("anchor must be 'today' or 'latest'.")
    if anchor == "latest":
        return latest_sale_date(db, business_id) or clock.today()
    return clock.today()


def _value(snap: kpi_service.KPISnapshot, key: str) -> float | None:
    v = {
        "revenue": snap.revenue if snap.orders else None,
        "orders": float(snap.orders) if snap.orders else None,
        "customers": float(snap.customers) if snap.orders else None,
        "average_order_value": snap.average_order_value,
        "profit": snap.profit,
        "marketing_spend": snap.marketing_spend if snap.marketing_spend else None,
        "marketing_roi": None if snap.marketing_roi is None else snap.marketing_roi * 100,
    }[key]
    return None if v is None else float(v)


@dataclass(frozen=True)
class RevenueChange:
    current_revenue: float
    previous_revenue: float
    change_pct: float | None
    current_orders: int
    previous_orders: int
    current_start: date
    previous_start: date
    previous_end: date


def revenue_change(db: Session, business_id: str, period_days: int, end: date) -> RevenueChange:
    """Sales in the window ending ``end`` versus the immediately preceding window of the SAME length (both inclusive of ``period_days``+1 days).

    New features use this instead of ``kpi_service.period_over_period``, whose current window is one day longer than its previous one."""
    cur = kpi_service.compute_kpis(db, business_id, period_days, end=end)
    start = end - timedelta(days=period_days)
    prev_end = start - timedelta(days=1)
    prev = kpi_service.compute_kpis(db, business_id, period_days, end=prev_end)
    ch = None if prev.revenue <= 0 else round((cur.revenue - prev.revenue) / prev.revenue, 4)
    return RevenueChange(cur.revenue, prev.revenue, ch, cur.orders, prev.orders, start, prev_end - timedelta(days=period_days), prev_end)


def get_targets(db: Session, business_id: str) -> dict[str, KpiTarget]:
    return {t.kpi_key: t for t in db.query(KpiTarget).filter(KpiTarget.business_id == business_id).all()}


def set_target(db: Session, business_id: str, key: str, value: float, direction: str | None, period_days: int) -> KpiTarget:
    d = _kpi_def(key)
    direction = direction or ("higher" if d.higher_is_better else "lower")
    if direction not in ("higher", "lower"):
        raise KpiValidationError("direction must be 'higher' or 'lower'.")
    if period_days not in ALLOWED_PERIODS:
        raise KpiValidationError(f"period_days must be one of {list(ALLOWED_PERIODS)}.")
    if not (value == value) or abs(value) > 1e12:
        raise KpiValidationError("target must be a finite number.")
    row = db.query(KpiTarget).filter(KpiTarget.business_id == business_id, KpiTarget.kpi_key == key).first()
    if row is None:
        row = KpiTarget(business_id=business_id, kpi_key=key, target_value=value, direction=direction, period_days=period_days)
        db.add(row)
    else:
        row.target_value, row.direction, row.period_days = value, direction, period_days
    db.commit()
    return row


def delete_target(db: Session, business_id: str, key: str) -> None:
    _kpi_def(key)
    db.query(KpiTarget).filter(KpiTarget.business_id == business_id, KpiTarget.kpi_key == key).delete()
    db.commit()


def status_for(value: float | None, target: KpiTarget | None) -> tuple[str, str]:
    """(status, plain-language rule). Status is one of met | not_met | no_target | no_data."""
    if target is None:
        return "no_target", "No target is set, so no status is shown."
    rule = f"Met when the value is {'at least' if target.direction == 'higher' else 'at most'} the target ({target.target_value:g})."
    if value is None:
        return "no_data", rule
    ok = value >= target.target_value if target.direction == "higher" else value <= target.target_value
    return ("met" if ok else "not_met"), rule


def _quality(snap: kpi_service.KPISnapshot, key: str, stale_days: int | None) -> dict[str, str]:
    if snap.orders == 0 and key in ("revenue", "orders", "customers", "average_order_value", "profit"):
        return {"status": "no_data", "note": "No sales in this period."}
    if key == "profit" and snap.profit is None:
        return {"status": "unavailable", "note": "Needs product costs."}
    if key == "marketing_roi" and snap.marketing_roi is None:
        return {"status": "unavailable", "note": "Needs campaigns with recorded results."}
    if key == "marketing_spend" and not snap.marketing_spend:
        return {"status": "no_data", "note": "No marketing spend recorded in this period."}
    if stale_days is not None and stale_days > STALE_AFTER_DAYS:
        return {"status": "stale", "note": f"The newest sale is {stale_days} days old."}
    partial = next((n for n in snap.notes if n.startswith("Profit computed from")), None)
    if key == "profit" and partial:
        return {"status": "partial", "note": partial}
    return {"status": "ok", "note": "Calculated from your recorded data."}


def list_kpis(db: Session, business_id: str, period_days: int = 30, anchor: str = "today") -> dict[str, Any]:
    if period_days not in ALLOWED_PERIODS:
        raise KpiValidationError(f"period_days must be one of {list(ALLOWED_PERIODS)}.")
    end = resolve_end(db, business_id, anchor)
    start = end - timedelta(days=period_days)
    cur = kpi_service.compute_kpis(db, business_id, period_days, end=end)
    prev_end = start - timedelta(days=1)
    prev = kpi_service.compute_kpis(db, business_id, period_days, end=prev_end)
    latest = latest_sale_date(db, business_id)
    stale_days = (clock.today() - latest).days if latest else None
    targets = get_targets(db, business_id)
    out = []
    for d in KPI_DEFS.values():
        value, pv = _value(cur, d.key), _value(prev, d.key)
        change = None if value is None or pv is None or pv == 0 else round((value - pv) / abs(pv), 4)
        t = targets.get(d.key)
        # a target is judged on its own window; when it differs from the page window it is evaluated for that window
        tv = value
        if t is not None and t.period_days != period_days:
            tv = _value(kpi_service.compute_kpis(db, business_id, t.period_days, end=end), d.key)
        st, rule = status_for(tv, t)
        out.append(
            {
                "key": d.key, "name": d.name, "unit": d.unit, "definition": d.definition, "source": d.source,
                "value": None if value is None else round(value, 2),
                "previous_value": None if pv is None else round(pv, 2),
                "change_pct": change,
                "target": None if t is None else {"value": t.target_value, "direction": t.direction, "period_days": t.period_days},
                "target_period_value": None if tv is None else round(tv, 2),
                "status": st, "status_rule": rule,
                "data_quality": _quality(cur, d.key, stale_days),
            }
        )
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat(), "days": period_days, "anchor": anchor},
        "previous_period": {"start": (prev_end - timedelta(days=period_days)).isoformat(), "end": prev_end.isoformat()},
        "latest_sale_date": latest.isoformat() if latest else None,
        "stale_days": stale_days,
        "stale_rule": f"Data is flagged stale when the newest sale is more than {STALE_AFTER_DAYS} days before today.",
        "calculated_at": clock.today().isoformat(),
        "kpis": out,
    }


def trend(db: Session, business_id: str, key: str, period_days: int = 90, anchor: str = "today") -> dict[str, Any]:
    """Daily series for one KPI over the window. Only days with records appear (gaps are real gaps, not zeros)."""
    d = _kpi_def(key)
    if key in ("profit", "marketing_roi"):
        raise KpiValidationError(f"A daily trend is not available for {d.name}.")
    end = resolve_end(db, business_id, anchor)
    start = end - timedelta(days=period_days)
    points: list[dict[str, Any]] = []
    if key == "marketing_spend":
        rows = (
            db.query(MarketingCampaign.campaign_date, func.sum(MarketingCampaign.spend))
            .filter(MarketingCampaign.business_id == business_id, MarketingCampaign.campaign_date >= start, MarketingCampaign.campaign_date <= end)
            .group_by(MarketingCampaign.campaign_date).order_by(MarketingCampaign.campaign_date).all()
        )
        points = [{"date": r[0].isoformat(), "value": float(r[1] or 0)} for r in rows]
    else:
        rows = (
            db.query(Sale.sale_date, func.sum(Sale.revenue), func.count(Sale.id), func.count(func.distinct(Sale.customer_id)))
            .filter(Sale.business_id == business_id, Sale.sale_date >= start, Sale.sale_date <= end)
            .group_by(Sale.sale_date).order_by(Sale.sale_date).all()
        )
        for day, rev, n, cust in rows:
            rev = float(rev or 0)
            v = {"revenue": rev, "orders": float(n), "customers": float(cust), "average_order_value": rev / n if n else None}[key]
            if v is not None:
                points.append({"date": day.isoformat(), "value": round(v, 2)})
    t = get_targets(db, business_id).get(key)
    return {
        "key": key, "name": d.name, "unit": d.unit, "period": {"start": start.isoformat(), "end": end.isoformat()},
        "points": points, "n_points": len(points),
        "target": None if t is None else {"value": t.target_value, "direction": t.direction, "period_days": t.period_days},
        "note": "Only days with at least one record are shown; missing days are not counted as zero.",
    }
