"""AI façade: the single entry point the rest of the application uses for model requests.

The only provider is OpenAI (``app/services/openai_client.py``, official SDK). The model classifies text into closed label sets
(analytics questions, goal sentences) and may restate verified facts through a validated explanation step. Free-text generation is
otherwise not used: strategy summaries and agent reviews remain deterministic templates over computed results, so the model is never
the source of a forecast, KPI, score or recommendation. When no key is configured every method has a deterministic fallback.
"""
import re
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.services.openai_client import Choice, DecisionResult, ExplainResult, Noul, OpenAIClient

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
    decision_source: str = "rules"  # "ai" when the AI model classified the objective, "rules" otherwise


_GOAL_OBJECTIVE_OPTIONS = {
    "increase_revenue": "wants to grow total sales / revenue / turnover",
    "increase_profit": "wants to grow profit or margin",
    "increase_sales": "wants more orders or units sold",
    "reduce_churn": "wants to keep customers / lose fewer customers",
    "improve_marketing_roi": "wants better return on marketing or advertising spend",
    "reduce_inventory_risk": "wants fewer stock-outs or less overstock",
    "none": "none of the above, or no business goal at all",
}
_CONSTRAINT_QUESTIONS = {
    "no_price_increase": "Does the owner say prices must NOT be raised?",
    "no_price_decrease": "Does the owner say prices must NOT be lowered or discounted?",
    "no_price_change": "Does the owner say prices must stay exactly as they are?",
    "no_marketing_increase": "Does the owner say the marketing or advertising budget must NOT be increased?",
    "no_marketing_decrease": "Does the owner say the marketing or advertising budget must NOT be cut?",
}
GOAL_MIN_CONFIDENCE = 0.6  # an AI objective is used only at or above this confidence, otherwise the rule-based parse stands
CONSTRAINT_MIN_NOUL = 0.8  # a constraint narrows the action space, so only a clear "yes" is accepted


class LLMService:
    """Thin façade over the AI provider (OpenAI). Every caller only ever sees this class; none talks to a provider directly."""

    def __init__(self):
        self.settings = get_settings()

    @property
    def enabled(self) -> bool:
        return self.settings.llm_enabled

    def _client(self) -> OpenAIClient:
        return OpenAIClient()

    def decide(self, state, questions) -> DecisionResult:
        """One request classifying ``state`` into the closed labels in ``questions``. Reports failures instead of raising or hiding them."""
        if not self.enabled:
            return DecisionResult(False, error="not_configured", attempts=0)
        return self._client().decide(state, questions)

    def explain(self, question: str, facts: list[str], notes: list[str]) -> ExplainResult:
        """Ask the model to restate ALREADY VERIFIED facts. The caller must validate the text before showing it."""
        if not self.enabled:
            return ExplainResult(False, error="not_configured")
        return self._client().explain(question, facts, notes)

    def parse_goal(self, text: str) -> ParsedGoal:
        """Rule-based parse first (target, unit and horizon are always rule-based, never model-extracted). When the AI model is configured it
        classifies the objective and the constraints; a failed or low-confidence decision silently keeps the rule-based result and the
        result says so (``decision_source``)."""
        parsed = self._parse_goal_rule_based(text)
        if not self.enabled:
            return parsed
        questions = {"objective": Choice("Which business objective is the owner describing?", _GOAL_OBJECTIVE_OPTIONS)}
        questions.update({f"c_{k}": Noul(v) for k, v in _CONSTRAINT_QUESTIONS.items()})
        res = self.decide(text, questions)
        if not res.ok:
            parsed.parse_warnings.append(f"AI goal classification unavailable ({res.error}); rules were used.")
            return parsed
        obj = res.choice("objective")
        if obj is not None and obj.value in OBJECTIVE_TO_KPI and (obj.confidence or 0.0) >= GOAL_MIN_CONFIDENCE:
            if parsed.objective != obj.value:
                parsed.objective = obj.value
                parsed.primary_kpi = OBJECTIVE_TO_KPI[obj.value]
                parsed.parse_warnings = [w for w in parsed.parse_warnings if "goal type" not in w]
            parsed.decision_source = "ai"
        extra = [k for k in _CONSTRAINT_QUESTIONS if (res.noul(f"c_{k}") or 0.0) >= CONSTRAINT_MIN_NOUL]
        parsed.constraints = sorted(set(parsed.constraints) | set(extra))
        return parsed

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
        """Deterministic template rendered from structured context (docs/AI_MODULE_SPECIFICATION.md §7: explanations narrate results
        that already exist). Deterministic by design: the model does not write strategy text."""
        parts = [f"Strategy: {context.get('strategy_name', 'Unnamed strategy')}."]
        if "expected_revenue" in context:
            parts.append(f"Expected revenue: {context['expected_revenue']}.")
        if "risk_level" in context:
            parts.append(f"Risk level: {context['risk_level']}.")
        return " ".join(parts)

    def evaluate_agent(self, agent_name: str, evaluation: dict) -> str:
        """One agent's structured evaluation (already computed by app.agents.*) rendered as a sentence list. Template only."""
        label = agent_name.replace("_", " ").title()
        sentences = [f"{label}:"] + list(evaluation.get("key_points", []))
        if evaluation.get("risks"):
            sentences.append("Risks: " + " ".join(evaluation["risks"]))
        return " ".join(sentences)

    def generate_business_response(self, context: dict) -> str:
        """AI Assistant answers (docs/PRD.md §30). ``context`` always contains already-computed real numbers; the wording is the
        deterministic template below."""
        return self._generate_business_response_template(context)

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
            if c.change_pct is not None and c.change_pct >= 0.05:
                parts.append(
                    f"Revenue is up {c.change_pct * 100:.1f}% over the last 30 days — worth finding out which "
                    "products are driving it so you can do more of what is working."
                )
            if not parts:
                if c.change_pct is None:
                    parts.append(
                        "There's no earlier period to compare your recent revenue against yet. Consider setting a "
                        "goal so DecisionGPT can recommend a concrete next step."
                    )
                else:
                    parts.append(
                        "Your revenue hasn't moved much recently. Consider setting a goal so DecisionGPT can "
                        "recommend a concrete next step."
                    )
            return " ".join(parts)

        return "I looked into this using your business data."
