"""LLMService — the single abstraction every LLM-touching feature goes
through (docs/LLM_ARCHITECTURE, AGENTS.md "LLM boundary").

No LLM vendor is imported directly anywhere else in the codebase. When no
LLM_API_KEY is configured, every method falls back to a deterministic,
rule-based implementation so the product still works end-to-end in demo
mode — see docs/AI_MODULE_SPECIFICATION.md §8 and §13 "No Fabrication":
the LLM is never the source of truth for numbers, so a missing LLM key
degrades explanation *quality*, not correctness.
"""
import re
from dataclasses import dataclass, field

from app.core.config import get_settings

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
    (OpenAI/Anthropic/etc, chosen via LLM_PROVIDER) without touching any
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

    def _parse_goal_via_llm(self, text: str) -> ParsedGoal:  # pragma: no cover - no provider wired up yet
        raise NotImplementedError("No LLM provider is wired up yet; falling back to rule-based parsing.")

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

    def _generate_strategy_explanation_via_llm(self, context: dict) -> str:  # pragma: no cover
        raise NotImplementedError("No LLM provider is wired up yet.")

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

    def _evaluate_agent_via_llm(self, agent_name: str, evaluation: dict) -> str:  # pragma: no cover
        raise NotImplementedError("No LLM provider is wired up yet.")

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

    def _generate_business_response_via_llm(self, context: dict) -> str:  # pragma: no cover
        raise NotImplementedError("No LLM provider is wired up yet.")

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
