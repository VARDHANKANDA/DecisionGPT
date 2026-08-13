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

from sqlalchemy.orm import Session

from app.analytics import digital_twin_service, kpi_service
from app.analytics.digital_twin_service import Action
from app.core.errors import AppError
from app.models.decision import Decision
from app.models.goal import Goal
from app.services import memory_service
from app.services.llm_service import LLMService

INSUFFICIENT_EVIDENCE_MESSAGE = "I don't have enough data to answer that reliably."


@dataclass
class AssistantResponse:
    answer: str
    intent: str
    sources: list[str] = field(default_factory=list)
    sufficient_evidence: bool = True


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


def _simulation_advice(db: Session, business_id: str, action_type: str, value: float) -> AssistantResponse:
    try:
        simulation = digital_twin_service.simulate_strategy(db, business_id, [Action(type=action_type, value=value)])
    except AppError as exc:
        return AssistantResponse(
            f"{INSUFFICIENT_EVIDENCE_MESSAGE} {exc.message}",
            "price_change_advice" if action_type == "price_change" else "marketing_change_advice",
            sufficient_evidence=False,
        )
    answer = LLMService().generate_business_response(
        {"type": "simulation_advice", "action_type": action_type, "value": value, "output": simulation.output}
    )
    intent = "price_change_advice" if action_type == "price_change" else "marketing_change_advice"
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


def answer_question(db: Session, business_id: str, question: str) -> AssistantResponse:
    intent = classify_intent(question)

    if intent == "why_kpi_fell":
        response = _why_kpi_fell(db, business_id)
    elif intent == "price_change_advice":
        response = _simulation_advice(db, business_id, "price_change", 5)
    elif intent == "marketing_change_advice":
        response = _simulation_advice(db, business_id, "marketing_change", 10)
    elif intent == "why_recommend":
        response = _why_recommend(db, business_id)
    elif intent == "what_focus":
        response = _what_focus(db, business_id)
    else:
        response = AssistantResponse(
            f"{INSUFFICIENT_EVIDENCE_MESSAGE} Try asking why a number changed, whether to change price or "
            "marketing spend, what to focus on, or why a specific recommendation was made.",
            "unrecognized",
            sufficient_evidence=False,
        )

    memory_service.log_memory(
        db, business_id, "chat", f"Q: {question}\nA: {response.answer}", metadata={"intent": response.intent}
    )
    db.commit()

    return response
