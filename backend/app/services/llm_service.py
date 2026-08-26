"""LLMService — the single abstraction every LLM-touching feature goes
through (docs/LLM_ARCHITECTURE, AGENTS.md "LLM boundary").

No LLM vendor is imported directly anywhere else in the codebase. When no
LLM_API_KEY is configured, every method falls back to a deterministic,
rule-based implementation so the product still works end-to-end in demo
mode — see docs/AI_MODULE_SPECIFICATION.md §8 and §13 "No Fabrication":
the LLM is never the source of truth for numbers, so a missing LLM key
degrades explanation *quality*, not correctness.
"""
import json
import re
from dataclasses import dataclass, field

from app.core.config import get_settings

_NARRATION_SYSTEM = (
    "You are a business analytics writing assistant for DecisionGPT. You are given "
    "structured, already-computed results (numbers, scores, model outputs). Your ONLY job "
    "is to phrase them clearly and concisely for an SME owner. You must NEVER invent, "
    "estimate, or alter any number, forecast, score, probability, or causal claim. If a "
    "value is not in the input, do not mention it. 2-4 sentences, plain English."
)

# Constraint tokens strategy_generation_service understands.
_CONSTRAINT_PATTERNS = {
    "no_price_increase": [r"without raising price", r"don'?t raise price", r"no price increase", r"keep price", r"not increase price"],
    "no_price_decrease": [r"without (?:cutting|lowering|dropping) price", r"no discount", r"don'?t discount", r"no price cut"],
    "no_price_change": [r"without changing price", r"keep prices the same", r"hold price"],
    "no_marketing_increase": [r"without (?:increasing|raising) (?:marketing|ad) (?:budget|spend)", r"keep (?:the )?(?:marketing|ad) budget", r"same marketing budget", r"no extra (?:marketing|ad) spend"],
    "no_marketing_decrease": [r"without (?:cutting|reducing) (?:marketing|ad) (?:budget|spend)"],
}


def extract_constraints(text: str) -> list[str]:
    lowered = text.lower()
    found = []
    for token, patterns in _CONSTRAINT_PATTERNS.items():
        if any(re.search(p, lowered) for p in patterns):
            found.append(token)
    return found

OBJECTIVE_KEYWORDS: dict[str, list[str]] = {
    "increase_profit": ["profit", "margin"],
    "increase_revenue": ["revenue", "sales revenue", "turnover"],
    "increase_sales": ["sales", "orders", "units sold"],
    "reduce_churn": ["churn", "retention", "customer loss"],
    "improve_marketing_roi": ["marketing roi", "marketing return", "ad roi", "ad spend efficiency"],
    "reduce_inventory_risk": ["inventory risk", "stockout", "overstock", "inventory"],
}

OBJECTIVE_TO_KPI = {
    "increase_profit": "profit",
    "increase_revenue": "revenue",
    "increase_sales": "orders",
    "reduce_churn": "churn_rate",
    "improve_marketing_roi": "marketing_roi",
    "reduce_inventory_risk": "inventory_risk",
}

_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%|\b(\d+(?:\.\d+)?)\s*percent\b", re.IGNORECASE)
_MONTHS_RE = re.compile(r"(\d+)\s*month", re.IGNORECASE)
_WEEKS_RE = re.compile(r"(\d+)\s*week", re.IGNORECASE)


@dataclass
class ParsedGoal:
    objective: str | None
    target_value: float | None
    target_unit: str | None
    primary_kpi: str | None
    time_horizon_months: int | None
    constraints: list[str] = field(default_factory=list)
    source_text: str = ""
    parse_warnings: list[str] = field(default_factory=list)


class LLMService:
    """Thin façade. Swap `_parse_goal_via_llm` for a real provider call
    (OpenAI/etc, chosen via LLM_PROVIDER) without touching any
    caller — every caller only ever sees this class."""

    def __init__(self):
        self.settings = get_settings()

    @property
    def enabled(self) -> bool:
        return self.settings.llm_enabled

    def parse_goal(self, text: str) -> ParsedGoal:
        if self.enabled:
            try:
                return self._parse_goal_via_llm(text)
            except Exception:
                pass  # fall through to deterministic parsing rather than fail the request
        return self._parse_goal_rule_based(text)

    def _client(self):
        from app.services.llm_provider import LLMClient

        return LLMClient()

    def _parse_goal_via_llm(self, text: str) -> ParsedGoal:
        """Ask the LLM only to *structure* the sentence. Every field is then
        re-validated by goal_service against real data — the LLM never gets
        to assert a KPI value or that enough data exists."""
        system = (
            "Extract a structured business goal from the user's sentence. Respond with a JSON object "
            "with keys: objective (one of: increase_revenue, increase_profit, increase_sales, "
            "reduce_churn, improve_marketing_roi, reduce_inventory_risk, or null), target_value "
            "(number or null), target_unit ('percent' or null), time_horizon_months (integer or null), "
            "constraints (array of any of: no_price_increase, no_price_decrease, no_price_change, "
            "no_marketing_increase, no_marketing_decrease). Do not guess values that are not stated."
        )
        data = self._client().complete_json(system, text, max_tokens=250)
        objective = data.get("objective")
        if objective not in OBJECTIVE_TO_KPI:
            objective = None
        tv = data.get("target_value")
        target_value = float(tv) if isinstance(tv, (int, float)) else None
        unit = data.get("target_unit")
        target_unit = "percent" if unit == "percent" and target_value is not None else None
        th = data.get("time_horizon_months")
        time_horizon = int(th) if isinstance(th, (int, float)) and th else None
        constraints = [c for c in (data.get("constraints") or []) if c in _CONSTRAINT_PATTERNS]
        if not constraints:
            constraints = extract_constraints(text)

        warnings: list[str] = []
        if objective is None:
            warnings.append("LLM could not map the text to a supported goal type.")
        if target_value is None:
            warnings.append("LLM found no measurable target.")

        return ParsedGoal(
            objective=objective,
            target_value=target_value,
            target_unit=target_unit,
            primary_kpi=OBJECTIVE_TO_KPI.get(objective) if objective else None,
            time_horizon_months=time_horizon,
            constraints=constraints,
            source_text=text,
            parse_warnings=warnings,
        )

    def _parse_goal_rule_based(self, text: str) -> ParsedGoal:
        lowered = text.lower()
        warnings: list[str] = []

        objective = None
        for obj, keywords in OBJECTIVE_KEYWORDS.items():
            if any(kw in lowered for kw in keywords):
                objective = obj
                break
        if objective is None:
            warnings.append(
                "Could not identify a supported goal type from the text. "
                f"Supported goals: {', '.join(OBJECTIVE_KEYWORDS)}."
            )

        target_value = None
        target_unit = None
        percent_match = _PERCENT_RE.search(lowered)
        if percent_match:
            target_value = float(percent_match.group(1) or percent_match.group(2))
            target_unit = "percent"
        else:
            warnings.append("Could not find a measurable target (e.g. '15%') in the text.")

        time_horizon_months = None
        months_match = _MONTHS_RE.search(lowered)
        weeks_match = _WEEKS_RE.search(lowered)
        if months_match:
            time_horizon_months = int(months_match.group(1))
        elif weeks_match:
            time_horizon_months = max(1, round(int(weeks_match.group(1)) / 4))

        return ParsedGoal(
            objective=objective,
            target_value=target_value,
            target_unit=target_unit,
            primary_kpi=OBJECTIVE_TO_KPI.get(objective) if objective else None,
            time_horizon_months=time_horizon_months,
            constraints=extract_constraints(text),
            source_text=text,
            parse_warnings=warnings,
        )

    def generate_strategy_explanation(self, context: dict) -> str:
        """Deterministic fallback: render a template from structured
        context. See docs/AI_MODULE_SPECIFICATION.md §7 — explanations
        narrate results that already exist; they never compute them."""
        if self.enabled:
            try:
                return self._generate_strategy_explanation_via_llm(context)
            except Exception:
                pass
        return self._generate_strategy_explanation_template(context)

    def _generate_strategy_explanation_via_llm(self, context: dict) -> str:
        return self._client().complete(
            _NARRATION_SYSTEM,
            "Write a short recommendation summary from this structured result (narrate only, "
            "invent nothing):\n" + json.dumps(context, default=str),
            max_tokens=250,
        )

    def _generate_strategy_explanation_template(self, context: dict) -> str:
        parts = [f"Strategy: {context.get('strategy_name', 'Unnamed strategy')}."]
        if "expected_revenue" in context:
            parts.append(f"Expected revenue: {context['expected_revenue']}.")
        if "risk_level" in context:
            parts.append(f"Risk level: {context['risk_level']}.")
        return " ".join(parts)

    def evaluate_agent(self, agent_name: str, evaluation: dict) -> str:
        """Turns one agent's structured evaluation (score/key_points/risks —
        already computed by app.agents.*, never by this method) into a
        one-paragraph narrative for the "AI Business Review" (docs/PRD.md
        §27) — narration only, per docs/AI_MODULE_SPECIFICATION.md §7 "the
        LLM narrates results that already exist; it never computes them."
        """
        if self.enabled:
            try:
                return self._evaluate_agent_via_llm(agent_name, evaluation)
            except Exception:
                pass
        return self._evaluate_agent_template(agent_name, evaluation)

    def _evaluate_agent_via_llm(self, agent_name: str, evaluation: dict) -> str:
        return self._client().complete(
            _NARRATION_SYSTEM,
            f"Agent: {agent_name}. Turn this agent's structured evaluation into one short "
            "paragraph for an 'AI Business Review' (narrate only, invent no numbers):\n"
            + json.dumps(evaluation, default=str),
            max_tokens=200,
        )

    def _evaluate_agent_template(self, agent_name: str, evaluation: dict) -> str:
        label = agent_name.replace("_", " ").title()
        sentences = [f"{label}:"] + list(evaluation.get("key_points", []))
        if evaluation.get("risks"):
            sentences.append("Risks: " + " ".join(evaluation["risks"]))
        return " ".join(sentences)

    def generate_business_response(self, context: dict) -> str:
        """AI Assistant answers (docs/PRD.md §30). `context` always contains
        already-computed real numbers (KPI comparisons, a Digital Twin
        simulation output, a stored Decision) — this method only ever
        narrates them; app.services.assistant_service decides *what* to
        say, this decides how to phrase it.
        """
        if self.enabled:
            try:
                return self._generate_business_response_via_llm(context)
            except Exception:
                pass
        return self._generate_business_response_template(context)

    def _generate_business_response_via_llm(self, context: dict) -> str:
        # The deterministic template already knows how to phrase each intent
        # from real numbers; the LLM just makes it more natural. Give it the
        # template answer as the ground truth to rephrase, so it cannot
        # drift from the computed figures.
        grounded = self._generate_business_response_template(context)
        return self._client().complete(
            _NARRATION_SYSTEM,
            "Rephrase this answer to sound natural and helpful. Keep every number and figure "
            "EXACTLY as written — do not add, remove, or change any number:\n" + grounded,
            max_tokens=250,
        )

    def _generate_business_response_template(self, context: dict) -> str:
        kind = context.get("type")

        if kind == "why_kpi_fell":
            c = context["comparison"]
            direction = "grew" if c.change_pct >= 0 else "fell"
            return (
                f"Your revenue {direction} {abs(c.change_pct) * 100:.1f}% over the last 30 days "
                f"(₹{c.previous_revenue:,.0f} → ₹{c.current_revenue:,.0f})."
            )

        if kind == "simulation_advice":
            o = context["output"]
            change = o.expected_revenue - o.baseline_revenue
            verb = "increase" if context["value"] >= 0 else "decrease"
            label = "price" if context["action_type"] == "price_change" else "marketing spend"
            direction = "improve" if change >= 0 else "reduce"
            return (
                f"Simulating a {abs(context['value'])}% {verb} in {label}: expected revenue would {direction} by "
                f"₹{abs(change):,.0f} (to ₹{o.expected_revenue:,.0f}), with {o.risk_level.lower()} risk."
            )

        if kind == "what_focus":
            c = context["comparison"]
            goal = context.get("goal")
            parts = []
            if c.change_pct is not None and c.change_pct < 0:
                parts.append(
                    f"Revenue is down {abs(c.change_pct) * 100:.1f}% over the last 30 days — that's worth "
                    "investigating first."
                )
            if goal is not None:
                unit = "%" if goal.target_unit == "percent" else f" {goal.target_unit}"
                parts.append(
                    f"You have an active goal to {goal.objective.replace('_', ' ')} by {goal.target_value}{unit} "
                    "— run a decision analysis to get a concrete recommendation."
                )
            if not parts:
                parts.append(
                    "Your revenue hasn't moved much recently. Consider setting a goal so DecisionGPT can "
                    "recommend a concrete next step."
                )
            return " ".join(parts)

        return "I looked into this using your business data."
