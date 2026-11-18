"""The AI analytics path of the business chat (OpenAI).

    question -> model classification (+ deterministic value extraction) -> strict structured request -> validation
             -> deterministic query engine -> verified result -> deterministic FACT text -> answer

"The model decides what kind of question this is; the deterministic DecisionGPT data layer determines what the data says."

The model only receives the question text, and only returns schema-constrained labels; it never receives rows or product names, never writes SQL
or code, never supplies a number and never sees another business's data: ``business_id`` comes from the authenticated route
(``verify_business_access``) and is applied by the query engine on every query. If the path is off, unconfigured, or the model fails,
``try_answer`` returns no response and the caller uses the legacy deterministic router — which is then labelled as such
(``path``). There is no other provider to fall back to.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.analytics import query_engine, query_presenter
from app.core import clock
from app.core.config import get_settings
from app.models.product import Product
from app.models.sale import Sale
from app.services import analytics_answer_service, analytics_interpreter_service
from app.services.llm_service import LLMService

logger = logging.getLogger("decisiongpt.analytics_llm")

PATH_LLM = "llm_analytics"
PATH_LEGACY = "legacy_router"
FALLBACK_NOTICE = "Advanced question understanding is temporarily unavailable, so this answer comes from the standard assistant."
LOW_CONFIDENCE_NOTICE = "I wasn't confident enough about what you meant to calculate it, so this answer comes from the standard assistant."
NOT_ACTIVE_NOTICE = "Free-form questions about your sales need the AI question interpreter, which isn't turned on yet. The standard assistant answered instead."

_UNSUPPORTED_MESSAGES = {
    "causal_attribution": (
        "I can show you what changed in your sales, but your data alone can't tell me why it changed. "
        "If it helps, ask me to compare two periods or to show which products moved the most."
    ),
    "out_of_scope": (
        "I can only answer questions about the sales data you've added — for example totals, units, top products, "
        "best days, and comparisons between periods."
    ),
}


def missing_data_message(item: str | None) -> str:
    """The one refusal wording for a question that needs data this business's records do not hold (GST, region, stock ...). Fixed
    template: no model text, no figure, and an explicit statement that the value is not estimated."""
    what = _safe_phrase(item) or "that information"
    return (
        f"I can calculate sales, units, orders and product performance from your current data, but it doesn't contain {what}, "
        "so I can't work this out and I won't estimate it."
    )


def get_llm() -> Any:
    """Factory seam: tests substitute a mocked LLM here; production returns the configured LLMService."""
    return LLMService()


@dataclass
class AnalyticsOutcome:
    response: Any | None = None  # AssistantResponse, or None -> use the legacy router
    audit: dict[str, Any] = field(default_factory=dict)
    fallback_reason: str | None = None
    notice: str | None = None


def is_active() -> bool:
    return get_settings().analytics_llm_active


def _optional_fields(db: Session, business_id: str) -> dict[str, bool]:
    return {
        "product_costs": db.query(Product.id).filter(Product.business_id == business_id, Product.unit_cost.isnot(None)).first() is not None,
        "product_categories": db.query(Product.id).filter(Product.business_id == business_id, Product.category.isnot(None)).first() is not None,
        "customers_on_sales": db.query(Sale.id).filter(Sale.business_id == business_id, Sale.customer_id.isnot(None)).first() is not None,
    }


def _product_names(db: Session, business_id: str) -> list[str]:
    """This business's own product names. Used locally to match names in the question; never sent to the model."""
    return [n for (n,) in db.query(Product.name).filter(Product.business_id == business_id).all() if n]


def _response(**kw):
    from app.services.assistant_service import AssistantResponse  # local: assistant_service imports this module

    return AssistantResponse(**kw)


def _safe_phrase(text: str | None, limit: int = 120) -> str:
    t = " ".join((text or "").split())[:limit]
    return "".join(ch for ch in t if ch.isalnum() or ch in " -_/&%.,'()")


def _log(audit: dict[str, Any], business_id: str) -> None:
    keep = {k: audit.get(k) for k in ("request_id", "route", "tool", "outcome", "fallback_reason", "explanation_source", "total_latency_s")}
    logger.info("analytics_llm %s", json.dumps(keep, default=str), extra={"request_id": audit.get("request_id"), "business_id": business_id})


def try_answer(db: Session, business_id: str, question: str, *, llm: Any | None = None) -> AnalyticsOutcome:
    settings = get_settings()
    if not settings.analytics_llm_enabled:
        return AnalyticsOutcome(fallback_reason="disabled")
    llm = llm if llm is not None else get_llm()
    if not getattr(llm, "enabled", False):
        return AnalyticsOutcome(fallback_reason="not_configured")

    t0 = time.perf_counter()
    audit: dict[str, Any] = {
        "request_id": uuid.uuid4().hex,
        "business_id": business_id,
        "reference_date": clock.today().isoformat(),
        "clock_pinned": clock.is_pinned(),
    }
    q = analytics_interpreter_service.clean_question(question)
    if len(q) > analytics_interpreter_service.MAX_QUESTION_CHARS:
        audit.update(outcome="skipped", fallback_reason="question_too_long")
        return AnalyticsOutcome(audit=audit, fallback_reason="question_too_long")

    coverage = query_engine.data_coverage(db, business_id)
    interp = analytics_interpreter_service.interpret(
        llm, q, clock.today(), coverage, _optional_fields(db, business_id), _product_names(db, business_id)
    )
    audit["interpreter_call"] = interp.call
    audit["interpreter_decisions"] = interp.decisions
    audit["validation"] = {"ok": interp.interpretation is not None, "errors": interp.validation_errors, "returned_fields": interp.raw_keys}

    if interp.interpretation is None:
        audit.update(outcome="fallback", fallback_reason=interp.error, total_latency_s=round(time.perf_counter() - t0, 3))
        _log(audit, business_id)
        notice = LOW_CONFIDENCE_NOTICE if interp.error == "low_confidence" else FALLBACK_NOTICE
        return AnalyticsOutcome(audit=audit, fallback_reason=interp.error, notice=notice)

    it = interp.interpretation
    audit["route"] = it.route
    audit["structured_request"] = it.model_dump(mode="json")

    if it.route == "legacy":
        audit.update(outcome="routed_to_legacy", fallback_reason="interpreter_routed_legacy", total_latency_s=round(time.perf_counter() - t0, 3))
        _log(audit, business_id)
        return AnalyticsOutcome(audit=audit, fallback_reason="interpreter_routed_legacy")

    if it.route == "clarification":
        text = it.clarification_question or "Could you tell me a little more about what you'd like to know?"  # a fixed template, never model text
        resp = _response(
            answer=text, intent="analytics_clarification", sources=[], sufficient_evidence=True, answer_type="clarification",
            path=PATH_LLM, details={}, audit=audit,
        )
        audit.update(outcome="clarification", total_latency_s=round(time.perf_counter() - t0, 3))
        _log(audit, business_id)
        return AnalyticsOutcome(resp, audit)

    if it.route == "unsupported":
        reason = it.unsupported_reason or "out_of_scope"
        if reason == "missing_field":
            text = missing_data_message(it.unsupported_item)
        else:
            text = _UNSUPPORTED_MESSAGES.get(reason, _UNSUPPORTED_MESSAGES["out_of_scope"])
        resp = _response(
            answer=text, intent="analytics_unsupported", sources=[], sufficient_evidence=False, answer_type="none",
            path=PATH_LLM, details={"missing_data": _safe_phrase(it.unsupported_item)} if reason == "missing_field" else {}, audit=audit,
        )
        audit.update(outcome="unsupported", unsupported_reason=reason, total_latency_s=round(time.perf_counter() - t0, 3))
        _log(audit, business_id)
        return AnalyticsOutcome(resp, audit)

    # ---- analytics_query: deterministic execution (business_id enforced inside the engine) ----
    audit["tool"] = "query_engine.run_query"
    t1 = time.perf_counter()
    try:
        result = query_engine.run_query(db, business_id, it.query)  # type: ignore[arg-type]
    except query_engine.QueryError as exc:
        audit.update(outcome="query_error", query_error=exc.code, total_latency_s=round(time.perf_counter() - t0, 3))
        _log(audit, business_id)
        if exc.code == "product_ambiguous":
            options = ", ".join(exc.candidates)
            text = f"{exc.message} Which one did you mean — {options}?"
            return AnalyticsOutcome(
                _response(answer=text, intent="analytics_clarification", sources=[], sufficient_evidence=True, answer_type="clarification", path=PATH_LLM, details={}, audit=audit),
                audit,
            )
        return AnalyticsOutcome(
            _response(answer=exc.message, intent="analytics_unsupported", sources=[], sufficient_evidence=False, answer_type="none", path=PATH_LLM, details={}, audit=audit),
            audit,
        )
    audit["tool_latency_s"] = round(time.perf_counter() - t1, 3)
    audit["verified_result"] = {
        "period": {"start": result.period.start.isoformat(), "end": result.period.end.isoformat(), "label": result.period.label},
        "n_records": result.n_records,
        "no_data": result.no_data,
        "coverage_status": result.coverage_status,
        "assumptions": result.assumptions,
    }

    facts = query_presenter.facts(result)
    notes = query_presenter.notes(result)
    rows = query_presenter.table(result)
    audit["explanation_source"] = "template"
    exp = None
    explain = getattr(llm, "explain", None)
    if not get_settings().analytics_explain_enabled:
        audit["explanation_skipped"] = "disabled"  # no request: the deterministic text is the whole answer
    elif explain is None:
        audit["explanation_skipped"] = "unavailable"
    elif not analytics_answer_service.explanation_needed(facts, notes, no_data=result.no_data, n_rows=len(rows)):
        audit["explanation_skipped"] = "answer_already_clear"  # one short verified sentence: a restatement could only repeat it
    else:
        # The model restates ALREADY VERIFIED facts. Its text is shown only if it passes the deterministic guard
        # (no repetition, no new number / causal claim / advice / unsupported term; see analytics_answer_service).
        try:
            er = explain(q, facts, notes)
        except Exception:  # a misbehaving provider layer must never cost the user the verified answer
            logger.warning("analytics_llm explanation raised; deterministic answer used", extra={"business_id": business_id})
            er = None
            audit["explanation_error"] = "exception"
        if er is not None:
            audit["explanation_call"] = {"ok": er.ok, "error": er.error, "latency_s": round(er.latency_s, 3), "usage": er.usage, "model": er.response_model or er.model}
            if er.ok:
                ok, why = analytics_answer_service.validate_explanation(er.text, facts, notes, q)
                if ok:
                    exp = analytics_answer_service.Explanation(interpretation=er.text, source="openai")
                else:
                    audit["explanation_rejected"] = why
            else:
                audit["explanation_error"] = er.error

    answer = analytics_answer_service.assemble(facts, notes, exp)
    if exp is not None and not analytics_answer_service.preserves_verified_text(answer, facts, notes):
        exp, answer = None, analytics_answer_service.assemble(facts, notes, None)  # defensive: never let a restatement displace a caveat
        audit["explanation_rejected"] = "would_drop_verified_text"
    if exp is not None:
        audit["explanation_source"] = "openai"
    details: dict[str, Any] = dict(query_presenter.scalar_details(result))
    if rows:
        details["table"] = rows
    details["sections"] = {"fact": facts[0], "interpretation": exp.interpretation if exp else None, "suggestion": None}
    sources = [f"Your sales records for {result.period.label} ({result.n_records:,} records)"] if not result.no_data else []
    audit.update(outcome="answered", total_latency_s=round(time.perf_counter() - t0, 3))
    _log(audit, business_id)
    resp = _response(
        answer=answer,
        intent="analytics_query",
        sources=sources,
        sufficient_evidence=not result.no_data,
        answer_type="known" if not result.no_data else "none",
        path=PATH_LLM,
        details=details,
        audit=audit,
    )
    return AnalyticsOutcome(resp, audit)
