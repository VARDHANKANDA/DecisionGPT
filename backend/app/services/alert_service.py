"""Smart Alerts — rule-based alerts over the owner's own records, evaluated on demand.

HONEST SCOPE: there is no background scheduler. Rules are evaluated when ``evaluate`` is called (when the owner opens Smart Alerts or
the Overview, or presses "Check now"). Alerts are stored, so history persists; nothing is generated at random.

DEDUPLICATION / COOLDOWN: each condition has a stable ``dedupe_key``. While an alert for a key is open or read, re-evaluation only
refreshes it (no new row). When its condition stops being true it is marked ``cleared``. If the owner marks it ``resolved`` it is not
raised again for COOLDOWN_HOURS even if the condition persists.

SEVERITY is set by the rules listed in ``RULES`` (disclosed to the user), never by a model.
"""
from __future__ import annotations

import threading
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import AppError, NotFoundError
from app.models.customer import Customer  # noqa: F401  (kept for symmetry with other services)
from app.models.inventory import InventoryRecord
from app.models.platform import Alert, AlertRule, DataPrepRun
from app.models.product import Product
from app.models.sale import Sale
from app.services import kpi_monitor_service as kms

COOLDOWN_HOURS = 24
MIN_PRODUCT_SHARE = 0.05


class AlertValidationError(AppError):
    code = "ALERT_VALIDATION"
    http_status = 422


RULES: dict[str, dict[str, Any]] = {
    "sales_drop": {
        "name": "Sales drop", "default_threshold": 0.15, "unit": "fraction",
        "description": "Sales in the last 30 days fell by at least the threshold versus the 30 days before.",
        "severity_rule": "Medium at the threshold; high at twice the threshold.",
    },
    "kpi_target_missed": {
        "name": "KPI target missed", "default_threshold": None, "unit": None,
        "description": "A KPI you set a target for does not meet it in its period.",
        "severity_rule": "Medium; high when the value is more than 25% away from the target.",
    },
    "stale_data": {
        "name": "Data is out of date", "default_threshold": 14, "unit": "days",
        "description": "The newest sale is older than the threshold (days before today).",
        "severity_rule": "Medium past the threshold; high past 30 days.",
    },
    "validation_failed": {
        "name": "Data checks failed", "default_threshold": None, "unit": None,
        "description": "The latest data validation run found failures or warnings.",
        "severity_rule": "High when any check failed; low when only warnings.",
    },
    "low_stock": {
        "name": "Low stock", "default_threshold": None, "unit": None,
        "description": "Products whose latest stock is at or below their reorder level.",
        "severity_rule": "Medium; high when 5 or more products are low or any has zero stock.",
    },
    "product_decline": {
        "name": "Product sales drop", "default_threshold": 0.30, "unit": "fraction",
        "description": "A product that made at least 5% of the previous period's sales fell by at least the threshold.",
        "severity_rule": "Medium at the threshold; high at twice the threshold.",
    },
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def rule_settings(db: Session, business_id: str) -> list[dict[str, Any]]:
    overrides = {r.rule_key: r for r in db.query(AlertRule).filter(AlertRule.business_id == business_id).all()}
    out = []
    for key, r in RULES.items():
        o = overrides.get(key)
        out.append({
            "rule_key": key, "name": r["name"], "description": r["description"], "severity_rule": r["severity_rule"], "unit": r["unit"],
            "enabled": True if o is None else o.enabled,
            "threshold": r["default_threshold"] if o is None or o.threshold is None else o.threshold,
            "default_threshold": r["default_threshold"], "is_default": o is None,
        })
    return out


def set_rule(db: Session, business_id: str, key: str, enabled: bool, threshold: float | None) -> dict[str, Any]:
    if key not in RULES:
        raise NotFoundError(f"Unknown alert rule '{key}'.")
    if threshold is not None:
        if RULES[key]["default_threshold"] is None:
            raise AlertValidationError("This rule has no threshold to configure.")
        if not (threshold == threshold) or threshold <= 0 or (RULES[key]["unit"] == "fraction" and threshold >= 1):
            raise AlertValidationError("Threshold must be positive (and below 1 for a percentage rule).")
    row = db.query(AlertRule).filter(AlertRule.business_id == business_id, AlertRule.rule_key == key).first()
    if row is None:
        row = AlertRule(business_id=business_id, rule_key=key, enabled=enabled, threshold=threshold)
        db.add(row)
    else:
        row.enabled, row.threshold = enabled, threshold
    db.commit()
    return next(r for r in rule_settings(db, business_id) if r["rule_key"] == key)


def _product_revenue(db: Session, business_id: str, start: date, end: date) -> dict[str, tuple[str, float]]:
    rows = (db.query(Product.id, Product.name, func.sum(Sale.revenue))
            .join(Sale, Sale.product_id == Product.id)
            .filter(Sale.business_id == business_id, Sale.sale_date >= start, Sale.sale_date <= end)
            .group_by(Product.id, Product.name).all())
    return {r[0]: (r[1], float(r[2] or 0)) for r in rows}


def _candidates(db: Session, business_id: str, rules: dict[str, dict[str, Any]], anchor: str, period_days: int = 30) -> dict[str, list[dict[str, Any]]]:
    """Conditions currently true, per rule. A rule that is disabled is absent from the result (its open alerts are left alone)."""
    end = kms.resolve_end(db, business_id, anchor)
    start = end - timedelta(days=period_days)
    out: dict[str, list[dict[str, Any]]] = {}

    if rules["sales_drop"]["enabled"] or rules["product_decline"]["enabled"]:
        cmp_ = kms.revenue_change(db, business_id, period_days, end)
    if rules["sales_drop"]["enabled"]:
        th = rules["sales_drop"]["threshold"]
        c = []
        if cmp_.change_pct is not None and cmp_.change_pct <= -th:
            sev = "high" if cmp_.change_pct <= -2 * th else "medium"
            c.append({
                "dedupe_key": "sales_drop", "severity": sev, "title": "Sales are down",
                "message": f"Sales fell {abs(cmp_.change_pct) * 100:.1f}% in the last {period_days} days ({cmp_.previous_revenue:,.0f} → {cmp_.current_revenue:,.0f}).",
                "metric_value": round(cmp_.change_pct, 4), "threshold": -th, "period": (start, end),
                "evidence": {"current_sales": cmp_.current_revenue, "previous_sales": cmp_.previous_revenue, "current_orders": cmp_.current_orders, "previous_orders": cmp_.previous_orders},
                "suggested_action": "Open Business Analytics to see which products changed. This shows that sales fell, not why.",
            })
        out["sales_drop"] = c

    if rules["kpi_target_missed"]["enabled"]:
        c = []
        targets = kms.get_targets(db, business_id)
        if targets:
            listing = kms.list_kpis(db, business_id, 30, anchor)
            for k in listing["kpis"]:
                if k["target"] and k["status"] == "not_met":
                    t = k["target"]["value"]
                    v = k["target_period_value"]
                    gap = abs(v - t) / abs(t) if t else 0
                    c.append({
                        "dedupe_key": f"kpi:{k['key']}", "severity": "high" if gap > 0.25 else "medium", "title": f"{k['name']} target missed",
                        "message": f"{k['name']} is {v:,.2f} against a target of {t:,.2f} ({'at least' if k['target']['direction'] == 'higher' else 'at most'}) over {k['target']['period_days']} days.",
                        "metric_value": v, "threshold": t, "period": (start, end),
                        "evidence": {"kpi": k["key"], "direction": k["target"]["direction"], "period_days": k["target"]["period_days"]},
                        "suggested_action": "Review the KPI on the KPI Monitoring page, or adjust the target if it no longer fits.",
                    })
        out["kpi_target_missed"] = c

    if rules["stale_data"]["enabled"]:
        th = rules["stale_data"]["threshold"]
        latest = kms.latest_sale_date(db, business_id)
        c = []
        if latest is not None and (clock.today() - latest).days > th:
            days = (clock.today() - latest).days
            c.append({
                "dedupe_key": "stale_data", "severity": "high" if days > 30 else "medium", "title": "Sales data is out of date",
                "message": f"The newest sale is dated {latest.isoformat()}, {days} days ago (threshold {th:g} days).",
                "metric_value": float(days), "threshold": float(th), "period": (latest, latest),
                "evidence": {"latest_sale": latest.isoformat()},
                "suggested_action": "Add your recent sales so figures about 'the last 30 days' are meaningful.",
            })
        out["stale_data"] = c

    if rules["validation_failed"]["enabled"]:
        run = (db.query(DataPrepRun).filter(DataPrepRun.business_id == business_id, DataPrepRun.stage == "validate")
               .order_by(DataPrepRun.created_at.desc()).first())
        c = []
        if run is not None:
            s = run.summary_json or {}
            fails, warns = int(s.get("fail", 0)), int(s.get("warn", 0))
            if fails or warns:
                c.append({
                    "dedupe_key": "validation_failed", "severity": "high" if fails else "low", "title": "Data checks need attention",
                    "message": f"The latest validation run found {fails} failed and {warns} warning checks.",
                    "metric_value": float(fails), "threshold": 0.0, "period": None,
                    "evidence": {"run_id": run.id, "fail": fails, "warn": warns},
                    "suggested_action": "Open Data Validation to see the affected rows and fix them, then re-run the checks.",
                })
        out["validation_failed"] = c

    if rules["low_stock"]["enabled"]:
        latest_by: dict[str, InventoryRecord] = {}
        for rec in db.query(InventoryRecord).filter(InventoryRecord.business_id == business_id).order_by(InventoryRecord.product_id, InventoryRecord.date):
            latest_by[rec.product_id] = rec
        names = {p.id: p.name for p in db.query(Product).filter(Product.business_id == business_id)}
        low = [(names.get(pid, "Unknown product"), r.stock_level, r.reorder_level) for pid, r in latest_by.items()
               if r.reorder_level is not None and r.stock_level <= r.reorder_level]
        c = []
        if low:
            sev = "high" if len(low) >= 5 or any(s == 0 for _, s, _ in low) else "medium"
            c.append({
                "dedupe_key": "low_stock", "severity": sev, "title": f"{len(low)} product{'s' if len(low) != 1 else ''} low on stock",
                "message": "At or below the reorder level: " + ", ".join(f"{n} ({s} left, reorder at {r})" for n, s, r in low[:6]) + ("…" if len(low) > 6 else "."),
                "metric_value": float(len(low)), "threshold": 1.0, "period": None,
                "evidence": {"products": [{"name": n, "stock": s, "reorder_level": r} for n, s, r in low]},
                "suggested_action": "Check these products on the Risk Manager page and reorder where needed.",
            })
        out["low_stock"] = c

    if rules["product_decline"]["enabled"]:
        th = rules["product_decline"]["threshold"]
        cur = _product_revenue(db, business_id, start, end)
        prev_end = start - timedelta(days=1)
        prev = _product_revenue(db, business_id, prev_end - timedelta(days=period_days), prev_end)
        prev_total = sum(v for _, v in prev.values())
        c = []
        for pid, (name, pv) in prev.items():
            if prev_total <= 0 or pv / prev_total < MIN_PRODUCT_SHARE or pv <= 0:
                continue
            cv = cur.get(pid, (name, 0.0))[1]
            change = (cv - pv) / pv
            if change <= -th:
                c.append({
                    "dedupe_key": f"product:{pid}", "severity": "high" if change <= -2 * th else "medium", "title": f"{name}: sales down",
                    "message": f"{name} sales fell {abs(change) * 100:.1f}% ({pv:,.0f} → {cv:,.0f}) versus the previous {period_days} days.",
                    "metric_value": round(change, 4), "threshold": -th, "period": (start, end),
                    "evidence": {"product": name, "current": cv, "previous": pv, "previous_share_of_sales": round(pv / prev_total, 3)},
                    "suggested_action": "Look at this product in Business Analytics. A fall in sales does not by itself show the cause.",
                })
        out["product_decline"] = c
    return out


_EVAL_LOCKS: dict[str, threading.Lock] = {}
_EVAL_LOCKS_GUARD = threading.Lock()


def evaluate(db: Session, business_id: str, anchor: str = "today", now: datetime | None = None) -> dict[str, Any]:
    """Check the rules once. Concurrent checks for one business (e.g. two tabs, or a double-fired page effect) are serialised so the same
    condition can never create two alerts; a partial unique index on active alerts enforces the same rule in the database."""
    with _EVAL_LOCKS_GUARD:
        lock = _EVAL_LOCKS.setdefault(business_id, threading.Lock())
    with lock:
        try:
            return _evaluate(db, business_id, anchor, now)
        except IntegrityError:  # another process inserted the same active alert first; re-read and refresh instead
            db.rollback()
            return _evaluate(db, business_id, anchor, now)


def _evaluate(db: Session, business_id: str, anchor: str = "today", now: datetime | None = None) -> dict[str, Any]:
    now = now or _utcnow()
    settings = {r["rule_key"]: r for r in rule_settings(db, business_id)}
    cands = _candidates(db, business_id, settings, anchor)
    created = refreshed = cleared = suppressed = 0
    existing = db.query(Alert).filter(Alert.business_id == business_id).all()
    by_key: dict[str, list[Alert]] = {}
    for a in existing:
        by_key.setdefault(a.dedupe_key, []).append(a)

    seen: set[str] = set()
    for rule_key, items in cands.items():
        for c in items:
            seen.add(c["dedupe_key"])
            live = [a for a in by_key.get(c["dedupe_key"], []) if a.status in ("open", "read")]
            period = c.get("period")
            fields = dict(severity=c["severity"], title=c["title"], message=c["message"], metric_value=c["metric_value"], threshold=c["threshold"],
                          period_start=period[0] if period else None, period_end=period[1] if period else None,
                          evidence_json=c["evidence"], suggested_action=c["suggested_action"])
            if live:
                a = live[0]
                for k, v in fields.items():
                    setattr(a, k, v)
                a.last_seen = now
                refreshed += 1
                continue
            recent_resolved = [a for a in by_key.get(c["dedupe_key"], [])
                               if a.status == "resolved" and a.resolved_at and (now - _aware(a.resolved_at)) < timedelta(hours=COOLDOWN_HOURS)]
            if recent_resolved:
                suppressed += 1
                continue
            db.add(Alert(business_id=business_id, rule_key=rule_key, dedupe_key=c["dedupe_key"], status="open", first_seen=now, last_seen=now, **fields))
            created += 1
    # conditions that stopped being true (only for rules that were evaluated this time)
    for key, rows in by_key.items():
        for a in rows:
            if a.status in ("open", "read") and a.rule_key in cands and key not in seen:
                a.status, a.resolved_at, a.last_seen = "cleared", now, now
                cleared += 1
    db.commit()
    return {
        "evaluated_at": now.isoformat(), "anchor": anchor, "created": created, "refreshed": refreshed, "cleared": cleared, "suppressed_by_cooldown": suppressed,
        "monitoring_note": "Checked now. DecisionGPT does not monitor continuously: alerts are re-checked when you open this page, the Overview, or press 'Check now'.",
        "cooldown_hours": COOLDOWN_HOURS,
    }


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def serialize(a: Alert) -> dict[str, Any]:
    return {
        "id": a.id, "rule_key": a.rule_key, "rule_name": RULES.get(a.rule_key, {}).get("name", a.rule_key), "severity": a.severity, "status": a.status,
        "title": a.title, "message": a.message, "metric_value": a.metric_value, "threshold": a.threshold,
        "period_start": a.period_start.isoformat() if a.period_start else None, "period_end": a.period_end.isoformat() if a.period_end else None,
        "evidence": a.evidence_json or {}, "suggested_action": a.suggested_action,
        "severity_rule": RULES.get(a.rule_key, {}).get("severity_rule"),
        "first_seen": a.first_seen.isoformat() if a.first_seen else None, "last_seen": a.last_seen.isoformat() if a.last_seen else None,
        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
    }


def list_alerts(db: Session, business_id: str, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    q = db.query(Alert).filter(Alert.business_id == business_id)
    if status == "active":
        q = q.filter(Alert.status.in_(("open", "read")))
    elif status:
        q = q.filter(Alert.status == status)
    order = {"high": 0, "medium": 1, "low": 2}
    rows = q.order_by(Alert.last_seen.desc()).limit(max(1, min(limit, 500))).all()
    rows.sort(key=lambda a: (order.get(a.severity, 3), -(a.last_seen.timestamp() if a.last_seen else 0)))
    return [serialize(a) for a in rows]


def set_status(db: Session, business_id: str, alert_id: str, status: str, now: datetime | None = None) -> dict[str, Any]:
    if status not in ("read", "resolved"):
        raise AlertValidationError("status must be 'read' or 'resolved'.")
    a = db.query(Alert).filter(Alert.id == alert_id, Alert.business_id == business_id).first()
    if a is None:
        raise NotFoundError("Alert not found.")
    a.status = status
    if status == "resolved":
        a.resolved_at = now or _utcnow()
    db.commit()
    return serialize(a)
