"""Saved reports: generated from the owner's own records, persisted, and re-openable.

A report is a snapshot: its ``payload_json`` is exactly what was calculated when it was created (period, scope, sections, assumptions,
limitations). Re-opening shows that snapshot — it is not recalculated, so a saved report always matches what was saved. Unsaved chat
answers are never reports.

Section kinds the UI renders: facts | table | series | text | list | notice.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.analytics import breakdown_service, forecast_service
from app.core import clock
from app.core.errors import AppError, NotFoundError
from app.models.business import Business
from app.models.customer import Customer
from app.models.decision import Decision, DecisionOutcome
from app.models.goal import Goal
from app.models.platform import DataPrepRun, SavedReport
from app.models.product import Product
from app.models.sale import Sale
from app.services import alert_service, health_service
from app.services import kpi_monitor_service as kms

REPORT_TYPES: dict[str, str] = {
    "performance": "Business Performance Report",
    "sales_products": "Sales & Product Report",
    "kpi": "KPI Report",
    "forecast": "Forecast Report",
    "data_quality": "Data Quality Report",
    "decisions": "Decision & Recommendation Report",
}


class ReportValidationError(AppError):
    code = "REPORT_VALIDATION"
    http_status = 422


def _facts(items: list[tuple[str, Any, str | None]]) -> dict[str, Any]:
    return {"kind": "facts", "items": [{"label": a, "value": b, **({"hint": c} if c else {})} for a, b, c in items]}


def _table(title: str, columns: list[str], rows: list[list[Any]], note: str | None = None) -> dict[str, Any]:
    return {"kind": "table", "title": title, "columns": columns, "rows": rows, **({"note": note} if note else {})}


def _text(title: str, *paras: str) -> dict[str, Any]:
    return {"kind": "text", "title": title, "paragraphs": list(paras)}


def _notice(tone: str, text: str) -> dict[str, Any]:
    return {"kind": "notice", "tone": tone, "text": text}


def _inr(v: float | None) -> str:
    return "Not available" if v is None else f"₹{round(v):,}"


def _scope(db: Session, business: Business) -> dict[str, Any]:
    n = lambda m: db.query(func.count(m.id)).filter(m.business_id == business.id).scalar() or 0  # noqa: E731
    lo, hi = db.query(func.min(Sale.sale_date), func.max(Sale.sale_date)).filter(Sale.business_id == business.id).one()
    return {
        "business": business.name, "business_id": business.id,
        "dataset": {"sales_rows": n(Sale), "products": n(Product), "customers": n(Customer),
                    "sales_from": lo.isoformat() if lo else None, "sales_to": hi.isoformat() if hi else None},
        "demo_data": bool(business.description and business.description.startswith("Synthetic demonstration")) or "(demo)" in business.name.lower(),
    }


def _kpi_sections(listing: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for k in listing["kpis"]:
        v = k["value"]
        shown = "Not available" if v is None else (f"{v:,.1f}%" if k["unit"] == "percent" else (_inr(v) if k["unit"] == "inr" else f"{v:,.0f}"))
        tgt = "—" if not k["target"] else f"{k['target']['value']:g} ({k['target']['direction']} is better, {k['target']['period_days']} days)"
        rows.append([k["name"], shown, "—" if k["change_pct"] is None else f"{k['change_pct'] * 100:+.1f}%", tgt,
                     {"met": "Met", "not_met": "Not met", "no_target": "No target", "no_data": "No data"}[k["status"]], k["data_quality"]["note"]])
    return [_table("KPIs for the period", ["KPI", "Value", "Change vs previous period", "Target", "Status", "Data note"], rows,
                   note=f"Window {listing['period']['start']} to {listing['period']['end']}; compared with {listing['previous_period']['start']} to {listing['previous_period']['end']}. "
                        "Status uses the owner-set target only.")]


def build(db: Session, business: Business, report_type: str, period_days: int = 30, anchor: str = "today") -> dict[str, Any]:
    if report_type not in REPORT_TYPES:
        raise ReportValidationError(f"Unknown report type. Choose one of: {', '.join(REPORT_TYPES)}.")
    if period_days not in kms.ALLOWED_PERIODS:
        raise ReportValidationError(f"period_days must be one of {list(kms.ALLOWED_PERIODS)}.")
    bid = business.id
    end = kms.resolve_end(db, bid, anchor)
    start = end - timedelta(days=period_days)
    sections: list[dict[str, Any]] = []
    assumptions = [f"Period: the {period_days} days ending {end.isoformat()} ({'today' if anchor == 'today' else 'the newest sale in your data'}).",
                   "All figures are calculated from the records in this account at the time the report was created."]
    limitations = ["Descriptive figures show what the records say; they do not explain causes."]
    summary = ""

    if report_type in ("performance", "kpi"):
        listing = kms.list_kpis(db, bid, period_days, anchor)
        sections += _kpi_sections(listing)
        if listing["stale_days"] is not None and listing["stale_days"] > kms.STALE_AFTER_DAYS:
            sections.insert(0, _notice("warning", f"The newest sale is {listing['stale_days']} days old, so recent periods may be empty."))
        rev = next(k for k in listing["kpis"] if k["key"] == "revenue")
        summary = (f"Sales were {_inr(rev['value'])} in the period." if rev["value"] is not None else "There were no sales in the period.")
        if report_type == "performance":
            health = health_service.assess(db, bid, period_days, anchor, save=False)
            comp = health["composite_score"]
            sections.append(_text("Business health", (f"Health score {comp} ({health['level']}) — a heuristic ({health['version']}), not a validated predictor." if comp is not None
                                                      else "No composite health score: " + health["composite_unavailable_reason"])))
            sections.append(_table("Health components", ["Component", "Score", "Weight used", "Detail"],
                                   [[c["name"], c["score"] if c["available"] else "Not available", c["effective_weight"] if c["available"] else "—",
                                     c["detail"] or c["unavailable_reason"]] for c in health["components"]]))
            active = alert_service.list_alerts(db, bid, "active", 10)
            sections.append(_table("Active alerts", ["Severity", "Alert", "What happened"], [[a["severity"], a["title"], a["message"]] for a in active]) if active
                            else _text("Active alerts", "No active alerts at the last check."))
            limitations.append("The health score and alert list are as of report creation; alerts are only re-checked on demand.")
        if report_type == "kpi":
            tr = kms.trend(db, bid, "revenue", period_days, anchor)
            sections.append({"kind": "series", "title": "Daily sales", "unit": "INR", "points": tr["points"], "note": tr["note"]})

    elif report_type == "sales_products":
        cmp_ = kms.revenue_change(db, bid, period_days, end)
        sections.append(_facts([("Sales", _inr(cmp_.current_revenue), None), ("Previous period", _inr(cmp_.previous_revenue), None),
                                ("Change", "n/a" if cmp_.change_pct is None else f"{cmp_.change_pct * 100:+.1f}%", None),
                                ("Orders", f"{cmp_.current_orders:,}", f"previous {cmp_.previous_orders:,}")]))
        tr = kms.trend(db, bid, "revenue", period_days, anchor)
        sections.append({"kind": "series", "title": "Daily sales", "unit": "INR", "points": tr["points"], "note": tr["note"]})
        top = breakdown_service.top_products(db, bid, 10)
        sections.append(_table("Best-selling products (all time)", ["Product", "Units sold", "Sales"], [[p.name, f"{p.units_sold:,}", _inr(p.revenue)] for p in top],
                               note="Product ranking covers all recorded sales, not only this period."))
        summary = f"Sales {_inr(cmp_.current_revenue)} in the period" + ("" if cmp_.change_pct is None else f" ({cmp_.change_pct * 100:+.1f}% vs the previous period).")
        limitations.append("The product table is not limited to the selected period.")

    elif report_type == "forecast":
        try:
            fr = forecast_service.forecast_sales(db, bid, 14)
            total = sum(p.predicted_value for p in fr.points)
            sections.append(_facts([("Expected units, next 14 days", f"{total:,.0f}", "an estimate"), ("Model", f"{fr.model_name} {fr.model_version}", None)]))
            sections.append({"kind": "series", "title": "Forecast (units per day)", "unit": "units",
                             "points": [{"date": str(p.forecast_date), "value": round(p.predicted_value, 1)} for p in fr.points]})
            summary = f"Expected about {total:,.0f} units over the next 14 days (an estimate, not a promise)."
            sections.append(_notice("info", "This forecast is built from this business's own sales history with a simple method chosen by back-testing on that history; it does not use the platform's example-data models."))
            for w in fr.warnings:
                sections.append(_notice("warning", w))
        except AppError as exc:
            sections.append(_notice("warning", f"A forecast could not be produced: {exc.message}"))
            summary = "No forecast: not enough usable data."
        limitations.append("A forecast is an estimate from past patterns; it is not guaranteed and carries uncertainty.")

    elif report_type == "data_quality":
        runs = db.query(DataPrepRun).filter(DataPrepRun.business_id == bid).order_by(DataPrepRun.created_at.desc()).limit(20).all()
        latest_val = next((r for r in runs if r.stage == "validate"), None)
        if latest_val:
            s = latest_val.summary_json or {}
            sections.append(_facts([("Checks passed", s.get("pass", 0), None), ("Warnings", s.get("warn", 0), None), ("Failed", s.get("fail", 0), None),
                                    ("Validated", latest_val.created_at.isoformat()[:19], None)]))
            summary = f"Latest validation: {s.get('pass', 0)} passed, {s.get('warn', 0)} warnings, {s.get('fail', 0)} failed."
        else:
            sections.append(_notice("info", "Data validation has not been run yet."))
            summary = "No validation run on record."
        sections.append(_table("Recent data preparation runs", ["When", "Stage", "Table", "Operation", "Status"],
                               [[r.created_at.isoformat()[:19], r.stage, r.table_type or "—", r.operation or "—", r.status] for r in runs]))
        limitations.append("Source files are not retained; the record is row-level, not complete lineage.")

    elif report_type == "decisions":
        decisions = db.query(Decision).filter(Decision.business_id == bid).order_by(Decision.created_at.desc()).limit(20).all()
        goals = {g.id: g for g in db.query(Goal).filter(Goal.business_id == bid)}
        outcomes = {o.decision_id: o for o in db.query(DecisionOutcome).filter(DecisionOutcome.decision_id.in_([d.id for d in decisions]))} if decisions else {}
        rows = []
        for d in decisions:
            g = goals.get(d.goal_id)
            rows.append([d.created_at.isoformat()[:10], (g.objective.replace("_", " ") if g else "—"), d.risk_level or "—",
                         "Recorded" if d.id in outcomes else "Not recorded", (d.reasoning or "")[:160]])
        sections.append(_table("Recommendations", ["Date", "Goal", "Risk", "Outcome", "Reasoning (start)"], rows) if rows else _notice("info", "No recommendations have been requested yet."))
        summary = f"{len(decisions)} recommendation(s) on record; {sum(1 for d in decisions if d.id in outcomes)} with a recorded outcome."
        limitations += ["Recommendations are suggestions ranked by a simulation; they are not proven optimal.", "Outcomes appear only where the owner recorded them."]

    return {
        "report_type": report_type, "title": REPORT_TYPES[report_type],
        "period": {"start": start.isoformat(), "end": end.isoformat(), "days": period_days, "anchor": anchor},
        "created_on": clock.today().isoformat(), "scope": _scope(db, business), "summary": summary,
        "sections": sections, "assumptions": assumptions, "limitations": limitations,
    }


def create(db: Session, business: Business, report_type: str, period_days: int = 30, anchor: str = "today") -> dict[str, Any]:
    payload = build(db, business, report_type, period_days, anchor)
    row = SavedReport(business_id=business.id, report_type=report_type, title=payload["title"],
                      period_start=date.fromisoformat(payload["period"]["start"]), period_end=date.fromisoformat(payload["period"]["end"]),
                      scope_json=payload["scope"], payload_json=payload)
    db.add(row)
    db.commit()
    return get(db, business.id, row.id)


def _meta(r: SavedReport) -> dict[str, Any]:
    return {"id": r.id, "report_type": r.report_type, "title": r.title, "period_start": r.period_start.isoformat() if r.period_start else None,
            "period_end": r.period_end.isoformat() if r.period_end else None, "created_at": r.created_at.isoformat() if r.created_at else None,
            "summary": (r.payload_json or {}).get("summary", "")}


def list_reports(db: Session, business_id: str, limit: int = 100) -> list[dict[str, Any]]:
    rows = db.query(SavedReport).filter(SavedReport.business_id == business_id).order_by(SavedReport.created_at.desc()).limit(max(1, min(limit, 500))).all()
    return [_meta(r) for r in rows]


def get(db: Session, business_id: str, report_id: str) -> dict[str, Any]:
    r = db.query(SavedReport).filter(SavedReport.id == report_id, SavedReport.business_id == business_id).first()
    if r is None:
        raise NotFoundError("Report not found.")
    return {**_meta(r), "payload": r.payload_json}


def delete(db: Session, business_id: str, report_id: str) -> None:
    n = db.query(SavedReport).filter(SavedReport.id == report_id, SavedReport.business_id == business_id).delete()
    if not n:
        raise NotFoundError("Report not found.")
    db.commit()
