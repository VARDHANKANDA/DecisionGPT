"""Explainable AI: show how an output was produced, from what is actually recorded.

* KPI explanations come from the KPI definitions and the rows in the window (a deterministic calculation, not a model).
* Answer explanations come from the audit stored with the chat answer: the structured request that was executed, the resolved period,
  the tool, and whether the answer came from the LLM analytics path or the fixed-intent router.
* Recommendation explanations come from the stored decision (see the decisions endpoints); SHAP-style attributions are shown only when the
  stored explanation says they are available. Nothing here relabels plain text as an explanation method.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.marketing import MarketingCampaign
from app.models.memory import BusinessMemory
from app.models.sale import Sale
from app.services import kpi_monitor_service as kms


def explain_kpi(db: Session, business_id: str, key: str, period_days: int = 30, anchor: str = "today") -> dict[str, Any]:
    d = kms._kpi_def(key)  # noqa: SLF001
    listing = kms.list_kpis(db, business_id, period_days, anchor)
    k = next(x for x in listing["kpis"] if x["key"] == key)
    start, end = listing["period"]["start"], listing["period"]["end"]       # ISO text for the response ...
    d_start, d_end = date.fromisoformat(str(start)), date.fromisoformat(str(end))   # ... real dates for the query (PostgreSQL does not compare a date with text)
    n_sales = (db.query(func.count(Sale.id)).filter(Sale.business_id == business_id, Sale.sale_date >= d_start, Sale.sale_date <= d_end).scalar() or 0)
    n_mkt = (db.query(func.count(MarketingCampaign.id)).filter(MarketingCampaign.business_id == business_id, MarketingCampaign.campaign_date >= d_start,
                                                              MarketingCampaign.campaign_date <= d_end).scalar() or 0)
    return {
        "kind": "kpi", "method": "Deterministic calculation over stored rows (no model, no language model).",
        "question": f"What was {d.name} in the {period_days} days ending {end}?", "definition": d.definition, "source": d.source,
        "period": listing["period"], "rows_used": {"sales_rows": n_sales, "marketing_rows": n_mkt}, "filters": ["Only this business's records", f"Sale dates from {start} to {end} inclusive"],
        "result": {"value": k["value"], "unit": k["unit"], "previous_period_value": k["previous_value"], "change": k["change_pct"]},
        "assumptions": ["Each recorded row is counted once as stored.", "Missing values are not filled in."], "limitations": [k["data_quality"]["note"]],
        "technical_detail": {"implementation": "app.analytics.kpi_service.compute_kpis", "status_rule": k["status_rule"]},
    }


def explain_answer(db: Session, business_id: str, memory_id: str) -> dict[str, Any]:
    m = db.query(BusinessMemory).filter(BusinessMemory.id == memory_id, BusinessMemory.business_id == business_id, BusinessMemory.memory_type == "chat").first()
    if m is None:
        raise NotFoundError("Answer not found.")
    md = m.metadata_json or {}
    audit = md.get("analytics_audit") or {}
    path = md.get("path") or "legacy_router"
    out: dict[str, Any] = {"kind": "chat_answer", "question": md.get("question"), "answer": md.get("answer"), "path": path, "answer_type": md.get("answer_type"),
                           "sources": md.get("sources") or [], "sufficient_evidence": md.get("sufficient_evidence")}
    if path == "llm_analytics" and audit:
        sr = (audit.get("structured_request") or {}).get("query") or {}
        out.update(method="An AI model turned your question into a structured request; a fixed calculation engine computed every number; the model may add wording that is checked against the facts.",
                   structured_request=sr, resolved_period=(audit.get("verified_result") or {}).get("period"), assumptions=(audit.get("verified_result") or {}).get("assumptions", []),
                   tool=audit.get("tool"), explanation_source=audit.get("explanation_source"), checks=[{"check": "Request validated against a strict schema", "passed": bool((audit.get("validation") or {}).get("ok"))}],
                   limitations=["The AI model chose how to read your question; if the structured request above is not what you meant, ask again with more detail."])
    else:
        out.update(method="A fixed set of rules matched your question to a built-in analysis; the numbers come from that analysis. No AI model wrote or checked this answer."
                   if path == "legacy_router" else "See sources.", intent=md.get("intent"),
                   limitations=["The standard assistant only recognises a few kinds of question and uses fixed windows such as 'the last 30 days'."])
    return out
