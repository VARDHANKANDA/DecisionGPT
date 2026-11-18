"""AI Assistant — docs/PRD.md §30, docs/API_SPECIFICATION.md §10.

A deliberately narrow, rule-based intent router — not a general chatbot.
Each recognized intent maps to a *real* analytical call (KPI comparison, a
Digital Twin simulation, a stored Decision's own reasoning); the LLM
(LLMService.generate_business_response, template-only in demo mode) only
narrates numbers that already exist. Anything the router doesn't recognize,
or recognizes but can't back with real data, gets the same honest refusal
docs/PRD.md §30 asks for: "I don't have enough data to answer that
reliably" — never a guess.

Every response also carries `sources`: what was actually queried to answer
it (docs/API_SPECIFICATION.md §10 "must cite the internal data/context
used").
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core import clock
from app.analytics import churn_service, digital_twin_service, forecast_service, kpi_service
from app.analytics.digital_twin_service import Action
from app.core.errors import AppError
from app.models.customer import Customer
from app.models.decision import Decision
from app.models.goal import Goal
from app.models.product import Product
from app.models.sale import Sale
from app.services import analytics_chat_service, analytics_interpreter_service, evaluation_chat_service, memory_service
from app.services.llm_service import LLMService

INSUFFICIENT_EVIDENCE_MESSAGE = "I don't have enough data to answer that reliably."


@dataclass
class AssistantResponse:
    answer: str
    intent: str
    sources: list[str] = field(default_factory=list)
    sufficient_evidence: bool = True
    # How the answer should be read: "known" (counted from the user's own records),
    # "estimate" (a model/simulation projection), "suggestion" (advice), "none".
    answer_type: str = "known"
    # Real numbers behind the answer, for the "Show the numbers" view.
    details: dict[str, Any] = field(default_factory=dict)
    # Which path produced the answer: "llm_analytics" (LLM-interpreted, deterministically calculated) or "legacy_router"
    # (fixed-intent router + templates). A legacy answer is never presented as an LLM answer.
    path: str = "legacy_router"
    # Plain-language note for the user (e.g. the AI assistant was unavailable and the standard assistant answered).
    notice: str | None = None
    # Reproducibility record of the LLM analytics path (stored with the chat memory; not returned to the client).
    audit: dict[str, Any] | None = None


def classify_intent(text: str) -> str:
    lowered = text.lower()
    has_why = "why" in lowered
    has_decline = any(w in lowered for w in ["fall", "fell", "drop", "declin", "down", "decreas", "wrong"])
    has_kpi_word = any(w in lowered for w in ["sales", "revenue", "profit", "order"])
    has_price = "price" in lowered
    has_marketing = any(w in lowered for w in ["marketing", "ads", "advertising", "ad spend"])
    has_directional = any(
        w in lowered for w in ["should", "what if", "increase", "raise", "lower", "decrease", "reduce", "cut"]
    )
    has_focus = any(w in lowered for w in ["focus", "priorit", "what should i do", "next step"])
    has_recommend = any(
        w in lowered for w in ["recommend", "suggestion", "why did you", "reach this decision", "reach that decision"]
    )

    if has_recommend:
        return "why_recommend"
    if has_why and has_decline and has_kpi_word:
        return "why_kpi_fell"
    if has_price and has_directional:
        return "price_change_advice"
    if has_marketing and has_directional:
        return "marketing_change_advice"
    if has_focus:
        return "what_focus"
    if any(w in lowered for w in ["stop buying", "churn", "leave", "lose customer", "losing customer", "at risk"]):
        return "customer_churn"
    if any(w in lowered for w in ["forecast", "next month", "next week", "predict", "look like", "will my sales", "might my sales"]):
        return "sales_forecast"
    if "customer" in lowered and any(w in lowered for w in ["valuable", "best", "top", "biggest", "most"]):
        return "valuable_customers"
    if any(w in lowered for w in ["improving", "getting worse", "losing sales", "declining", "trend", "performing", "performance"]):
        return "improving_worsening"
    if "product" in lowered and any(
        w in lowered for w in ["sold the most", "selling best", "best sell", "best-sell", "top", "most sold", "sell the most", "selling the most"]
    ):
        return "top_products"
    return "unrecognized"


def _why_kpi_fell(db: Session, business_id: str) -> AssistantResponse:
    comparison = kpi_service.period_over_period(db, business_id, days=30)
    if comparison.change_pct is None:
        return AssistantResponse(
            f"{INSUFFICIENT_EVIDENCE_MESSAGE} There's no revenue recorded in the 30 days before your current "
            "period to compare against.",
            "why_kpi_fell",
            sufficient_evidence=False,
        )
    answer = LLMService().generate_business_response({"type": "why_kpi_fell", "comparison": comparison})
    return AssistantResponse(
        answer, "why_kpi_fell", sources=["Revenue: last 30 days vs. the 30 days before that"]
    )


_DECREASE_WORDS = ("lower", "decrease", "reduce", "cut", "drop", "less", "discount", "slash")


def _requested_change(question: str, default: float) -> float:
    """The percentage the owner named ('raise my price by 10%'), signed by the direction words; the default only when none was named."""
    import re

    lowered = question.lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent|per cent)", lowered)
    if not m:
        return default
    value = float(m.group(1))
    return -value if any(w in lowered for w in _DECREASE_WORDS) else value


def _simulation_advice(db: Session, business_id: str, action_type: str, value: float) -> AssistantResponse:
    intent = "price_change_advice" if action_type == "price_change" else "marketing_change_advice"
    try:
        simulation = digital_twin_service.simulate_strategy(db, business_id, [Action(type=action_type, value=value)])
        simulation = digital_twin_service.api_view(db, business_id, simulation, 14)
    except AppError as exc:
        return AssistantResponse(f"{INSUFFICIENT_EVIDENCE_MESSAGE} {exc.message}", intent, sufficient_evidence=False)
    pr = simulation.output.price_response or {}
    if pr.get("withheld") or simulation.output.expected_revenue is None:
        return AssistantResponse(
            f"{INSUFFICIENT_EVIDENCE_MESSAGE} I can't tell you what a {abs(value):g}% price "
            f"{'increase' if value >= 0 else 'decrease'} would do to your sales: {pr.get('message', 'the effect is not available.')} "
            "To evaluate price changes you would need: " + "; ".join(pr.get("needed", [])) + ".",
            intent,
            sufficient_evidence=False,
            details={"price_response": pr},
        )
    if action_type == "marketing_change" and any("marketing spend is" in a and "no effect" in a for a in simulation.output.assumptions):
        return AssistantResponse(
            f"{INSUFFICIENT_EVIDENCE_MESSAGE} Your data has no recorded marketing spend, so a {abs(value):g}% change in it has nothing to "
            "act on. Upload your marketing campaign spend to evaluate this.",
            intent, sufficient_evidence=False,
        )
    answer = LLMService().generate_business_response(
        {"type": "simulation_advice", "action_type": action_type, "value": value, "output": simulation.output}
    )
    answer += (" This comes from a general model that has not been checked against your own business, so treat it as an illustration "
               "of direction, not a forecast.")
    return AssistantResponse(
        answer, intent, sources=[f"Digital Twin simulation: {action_type} {value:+g}% (simulation {simulation.id})"]
    )


def _why_recommend(db: Session, business_id: str) -> AssistantResponse:
    decision = (
        db.query(Decision)
        .filter(Decision.business_id == business_id)
        .order_by(Decision.created_at.desc())
        .first()
    )
    if decision is None:
        return AssistantResponse(
            f"{INSUFFICIENT_EVIDENCE_MESSAGE} You haven't run a decision analysis yet.",
            "why_recommend",
            sufficient_evidence=False,
        )
    answer = decision.reasoning or "No reasoning was recorded for that decision."
    return AssistantResponse(answer, "why_recommend", sources=[f"Decision {decision.id}"])


def _what_focus(db: Session, business_id: str) -> AssistantResponse:
    comparison = kpi_service.period_over_period(db, business_id, days=30)
    goal = (
        db.query(Goal)
        .filter(Goal.business_id == business_id, Goal.status == "active")
        .order_by(Goal.created_at.desc())
        .first()
    )
    answer = LLMService().generate_business_response({"type": "what_focus", "comparison": comparison, "goal": goal})
    sources = ["Revenue: last 30 days vs. the 30 days before that"]
    if goal is not None:
        sources.append(f"Active goal {goal.id}")
    return AssistantResponse(answer, "what_focus", sources=sources)


def _inr(value: float) -> str:
    """₹ with Indian digit grouping (12,34,567)."""
    n = int(round(abs(value)))
    s = str(n)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts: list[str] = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return f"{'-' if value < 0 else ''}₹{s}"


def _product_revenue(db: Session, business_id: str, start: date, end: date) -> dict[str, dict]:
    rows = (
        db.query(Product.id, Product.name, func.sum(Sale.quantity), func.sum(Sale.revenue))
        .join(Sale, Sale.product_id == Product.id)
        .filter(Sale.business_id == business_id, Sale.sale_date >= start, Sale.sale_date <= end)
        .group_by(Product.id, Product.name)
        .all()
    )
    return {r[0]: {"name": r[1], "units": int(r[2] or 0), "revenue": float(r[3] or 0)} for r in rows}


def _top_products(db: Session, business_id: str) -> AssistantResponse:
    today = clock.today()
    cur = _product_revenue(db, business_id, today - timedelta(days=30), today)
    prev = _product_revenue(db, business_id, today - timedelta(days=60), today - timedelta(days=31))
    period = "in the last 30 days"
    if not cur:
        cur = _product_revenue(db, business_id, date(2000, 1, 1), today)
        prev = {}
        period = "across all the sales you've added"
    if not cur:
        return AssistantResponse(
            f"{INSUFFICIENT_EVIDENCE_MESSAGE} There are no sales linked to products yet.",
            "top_products",
            sufficient_evidence=False,
        )
    ranked = sorted(cur.items(), key=lambda kv: kv[1]["revenue"], reverse=True)
    top_id, top = ranked[0]
    text = f"{top['name']} brought in the most money {period}: {_inr(top['revenue'])} from {top['units']:,} units sold."
    if len(ranked) > 1:
        runners = ", ".join(f"{v['name']} ({_inr(v['revenue'])})" for _, v in ranked[1:3])
        text += f" Next were {runners}."
    if top_id in prev and prev[top_id]["revenue"] > 0:
        chg = (top["revenue"] - prev[top_id]["revenue"]) / prev[top_id]["revenue"] * 100
        text += (
            f" Compared with the 30 days before, {top['name']} sales were about "
            f"{abs(chg):.0f}% {'higher' if chg >= 0 else 'lower'}."
        )
    rows = [{"product": v["name"], "units_sold": v["units"], "revenue": round(v["revenue"], 2)} for _, v in ranked[:10]]
    return AssistantResponse(
        text, "top_products", sources=[f"Sales {period}, grouped by product"], details={"table": rows}
    )


def _improving_worsening(db: Session, business_id: str) -> AssistantResponse:
    comparison = kpi_service.period_over_period(db, business_id, days=30)
    today = clock.today()
    cur = _product_revenue(db, business_id, today - timedelta(days=30), today)
    prev = _product_revenue(db, business_id, today - timedelta(days=60), today - timedelta(days=31))
    if comparison.change_pct is None and not (cur and prev):
        return AssistantResponse(
            f"{INSUFFICIENT_EVIDENCE_MESSAGE} There's no sales history from before the last 30 days to compare against.",
            "improving_worsening",
            sufficient_evidence=False,
        )
    parts: list[str] = []
    if comparison.change_pct is not None:
        direction = "up" if comparison.change_absolute >= 0 else "down"
        parts.append(
            f"Your total sales are {direction} about {abs(comparison.change_pct) * 100:.0f}% "
            f"({_inr(comparison.previous_revenue)} → {_inr(comparison.current_revenue)}) compared with the 30 days before."
        )
    changes = []
    for pid in set(cur) | set(prev):
        c, p = cur.get(pid, {}), prev.get(pid, {})
        name = (c or p)["name"]
        changes.append((name, c.get("revenue", 0.0) - p.get("revenue", 0.0), p.get("revenue", 0.0), c.get("revenue", 0.0)))
    changes.sort(key=lambda x: x[1])
    gains = [c for c in reversed(changes) if c[1] > 0][:2]
    drops = [c for c in changes if c[1] < 0][:2]
    if gains:
        parts.append("Improving: " + "; ".join(f"{n} ({_inr(a)} → {_inr(b)})" for n, _, a, b in gains) + ".")
    if drops:
        parts.append("Getting worse: " + "; ".join(f"{n} ({_inr(a)} → {_inr(b)})" for n, _, a, b in drops) + ".")
    if not gains and not drops:
        parts.append("No product changed noticeably between the two periods.")
    table = [
        {"product": n, "previous_30_days": round(a, 2), "last_30_days": round(b, 2), "change": round(d, 2)}
        for n, d, a, b in sorted(changes, key=lambda x: x[1], reverse=True)
    ]
    return AssistantResponse(
        " ".join(parts),
        "improving_worsening",
        sources=["Sales: last 30 days vs. the 30 days before that, by product"],
        details={"table": table},
    )


def _forecast_horizon(question: str) -> int:
    import re

    lowered = question.lower()
    m = re.search(r"next\s+(\d{1,2})\s+days?", lowered)
    if m:
        return max(1, min(forecast_service.MAX_HORIZON_DAYS, int(m.group(1))))
    if "next week" in lowered or "coming week" in lowered:
        return 7
    return 30


def _sales_forecast(db: Session, business_id: str, question: str = "") -> AssistantResponse:
    days = _forecast_horizon(question)
    try:
        result = forecast_service.forecast_sales(db, business_id, days)
    except AppError as exc:
        return AssistantResponse(
            f"{INSUFFICIENT_EVIDENCE_MESSAGE} {exc.message}", "sales_forecast", sufficient_evidence=False
        )
    pts = result.points
    total = sum(p.predicted_value for p in pts)
    low, high = sum(p.lower_bound for p in pts), sum(p.upper_bound for p in pts)
    today = clock.today()
    last_n = (
        db.query(func.coalesce(func.sum(Sale.quantity), 0))
        .filter(Sale.business_id == business_id, Sale.sale_date > today - timedelta(days=days), Sale.sale_date <= today)
        .scalar()
    )
    text = f"We estimate you could sell about {total:,.0f} units over the next {days} days."
    if last_n:
        text += f" In the last {days} days you sold {int(last_n):,} units."
    if result.forecast_basis == "limited_estimate":
        text += (" This is a limited estimate (your recent average held flat): there is too little history to check it against your own "
                 "past sales.")
    elif result.interval_reliable:
        text += (f" Based on how this method did on your own past weeks, the total is likely between about {low:,.0f} and {high:,.0f} units "
                 "(an 80% range, approximate).")
    else:
        text += (" Its uncertainty range could not be confirmed on your own history, so treat the estimate as indicative.")
    text += f" Based on your sales up to {result.data_as_of:%d %b %Y}; not a certain outcome."
    stale = [w for w in result.warnings if "days ago" in w]
    if stale:
        text += " Note: " + stale[0]
    return AssistantResponse(
        text,
        "sales_forecast",
        sources=[f"Your own sales history ({result.forecast_basis.replace('_', ' ')}; method: {result.model_name.split(':')[-1].replace('_', ' ')})"],
        details={
            "horizon_days": days,
            "estimate_units": round(total, 1),
            "last_period_units_actual": int(last_n or 0),
            "model": f"{result.model_name} {result.model_version}",
            "forecast_basis": result.forecast_basis,
            "interval_reliable": result.interval_reliable,
            "data_as_of": str(result.data_as_of),
            "warnings": result.warnings,
        },
    )


def _customer_churn(db: Session, business_id: str) -> AssistantResponse:
    try:
        preds, model_row = churn_service.predict_churn(db, business_id)
    except AppError as exc:
        return AssistantResponse(
            f"{INSUFFICIENT_EVIDENCE_MESSAGE} {exc.message}", "customer_churn", sufficient_evidence=False
        )
    info = churn_service.describe_scores(model_row)
    synthetic = info["label_provenance"].startswith("synthetic")
    ranked = sorted(preds, key=lambda p: p.churn_probability, reverse=True)
    top = [p for p in ranked if p.churn_probability >= 0.5][:3]
    # A score is never worded as a percentage chance: it ranks customers, it has not been checked against outcomes of this business.
    if not top:
        text = f"Out of {len(preds):,} customers assessed, none score high on the stop-buying pattern right now."
    else:
        names = ", ".join(f"{p.external_customer_id or 'a customer'} (score {p.churn_probability:.2f} of 1)" for p in top)
        text = (f"{len([p for p in ranked if p.churn_probability >= 0.5]):,} of {len(preds):,} customers have a high stop-buying score. "
                f"The highest are {names}.")
    text += (" These scores rank customers by how closely their recent buying resembles customers who stopped in a "
             + ("synthetic (computer-generated) training dataset" if synthetic else "training dataset")
             + "; they are not the probability that a customer will leave, and they have not been checked against your own customers.")
    stale = churn_service.data_age_warning(db, business_id)
    if stale:
        text += " Note: " + stale
    return AssistantResponse(
        text,
        "customer_churn",
        sources=[f"Customer scoring model {model_row.model_name} {model_row.version} on {len(preds):,} customers (not validated on this business)"],
        details={
            "score_meaning": info["score_meaning"],
            "label_provenance": info["label_provenance"],
            "table": [{"customer": p.external_customer_id, "risk_score": round(p.churn_probability, 2)} for p in ranked[:10] if p.churn_probability >= 0.5],
        },
    )


def _valuable_customers(db: Session, business_id: str) -> AssistantResponse:
    rows = (
        db.query(Customer)
        .filter(Customer.business_id == business_id, Customer.monetary_value.isnot(None))
        .order_by(Customer.monetary_value.desc())
        .limit(5)
        .all()
    )
    if not rows:
        return AssistantResponse(
            f"{INSUFFICIENT_EVIDENCE_MESSAGE} There's no 'total spent' recorded for your customers.",
            "valuable_customers",
            sufficient_evidence=False,
        )
    names = ", ".join(f"{c.external_customer_id} ({_inr(float(c.monetary_value))})" for c in rows[:3])
    return AssistantResponse(
        f"Your customers who have spent the most are {names}.",
        "valuable_customers",
        sources=["Customer records: total spent"],
        details={"table": [{"customer": c.external_customer_id, "total_spent": float(c.monetary_value)} for c in rows]},
    )


def _legacy_answer(db: Session, business_id: str, question: str) -> AssistantResponse:
    # Same capability policy as the AI path, without a model: a question about data the records do not hold (GST, region, stock ...)
    # gets one honest statement of what is missing, never a nearby figure or a clarification that cannot help.
    missing = analytics_interpreter_service.detect_unavailable_attribute(question, analytics_chat_service._product_names(db, business_id))
    if missing:
        return AssistantResponse(
            analytics_chat_service.missing_data_message(analytics_interpreter_service.MISSING_ITEM_LABEL[missing]),
            "analytics_unsupported",
            sufficient_evidence=False,
        )
    intent = classify_intent(question)

    if intent == "why_kpi_fell":
        response = _why_kpi_fell(db, business_id)
    elif intent == "price_change_advice":
        response = _simulation_advice(db, business_id, "price_change", _requested_change(question, 5))
    elif intent == "marketing_change_advice":
        response = _simulation_advice(db, business_id, "marketing_change", _requested_change(question, 10))
    elif intent == "why_recommend":
        response = _why_recommend(db, business_id)
    elif intent == "what_focus":
        response = _what_focus(db, business_id)
    elif intent == "top_products":
        response = _top_products(db, business_id)
    elif intent == "improving_worsening":
        response = _improving_worsening(db, business_id)
    elif intent == "sales_forecast":
        response = _sales_forecast(db, business_id, question)
    elif intent == "customer_churn":
        response = _customer_churn(db, business_id)
    elif intent == "valuable_customers":
        response = _valuable_customers(db, business_id)
    else:
        response = AssistantResponse(
            f"{INSUFFICIENT_EVIDENCE_MESSAGE} Try asking why a number changed, whether to change price or "
            "marketing spend, what to focus on, or why a specific recommendation was made.",
            "unrecognized",
            sufficient_evidence=False,
        )
    return response


def _evaluation_answer(db: Session, business_id: str, question: str, research_access: bool) -> AssistantResponse | None:
    """An evaluation question (metrics, accuracy, baselines, horizons, benchmarks, validation) is answered from the recorded evaluation results.

    No language model is involved at any step: the question is recognised by rules and every number is a card from the evaluation service. Returns
    None when the question is about something else."""
    query = evaluation_chat_service.detect(question)
    if query is None:
        return None
    result = evaluation_chat_service.answer(db, business_id, query, research_access=research_access)
    return AssistantResponse(
        result.text, "evaluation_results", sources=result.sources, sufficient_evidence=result.sufficient, answer_type="evaluation",
        details=evaluation_chat_service.sanitize_for_json(result.details), path="evaluation_service",
        audit={"evaluation_query": query.describe(), "research_access": research_access, "llm_used": False},
    )


def answer_question(db: Session, business_id: str, question: str, research_access: bool = False) -> AssistantResponse:
    """Evaluation questions first (deterministic, no model), then the LLM analytics path (when a provider is configured and healthy), then the
    legacy deterministic router.

    ``business_id`` has already been authorised by the route guard; every path filters every query by it. ``research_access`` says whether the caller
    may also see research-level evaluation results (registered models and benchmarks); it defaults to False so a caller that forgets it sees less.
    """
    evaluation = _evaluation_answer(db, business_id, question, research_access)
    outcome = None if evaluation is not None else analytics_chat_service.try_answer(db, business_id, question)
    if evaluation is not None:
        response = evaluation
    elif outcome.response is not None:
        response = outcome.response
    else:
        response = _legacy_answer(db, business_id, question)
        response.path = "legacy_router"
        response.notice = outcome.notice
        if response.notice is None and response.intent == "unrecognized" and outcome.fallback_reason in ("not_configured", "disabled"):
            response.notice = analytics_chat_service.NOT_ACTIVE_NOTICE
        response.audit = {"fallback_reason": outcome.fallback_reason, **outcome.audit} if outcome.fallback_reason else None

    if not response.sufficient_evidence:
        response.answer_type = "none"
    elif response.intent in {"price_change_advice", "marketing_change_advice", "sales_forecast", "customer_churn"}:
        response.answer_type = "estimate"
    elif response.intent == "what_focus":
        response.answer_type = "suggestion"

    memory_service.log_memory(
        db,
        business_id,
        "chat",
        f"Q: {question}\nA: {response.answer}",
        metadata={
            "intent": response.intent,
            "question": question,
            "answer": response.answer,
            "sufficient_evidence": response.sufficient_evidence,
            "answer_type": response.answer_type,
            "sources": response.sources,
            "path": response.path,
            **({"analytics_audit": response.audit} if response.audit else {}),
        },
    )
    db.commit()

    return response
