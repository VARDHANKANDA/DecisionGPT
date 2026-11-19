"""AI façade: the single entry point the rest of the application uses for model requests.

The only provider is OpenAI (``app/services/openai_client.py``, official SDK). The model classifies text into closed label sets
(analytics questions, goal sentences) and may restate verified facts through a validated explanation step. Free-text generation is
otherwise not used: strategy summaries and agent reviews remain deterministic templates over computed results, so the model is never
the source of a forecast, KPI, score or recommendation. When no key is configured every method has a deterministic fallback.
"""
import re
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.services.openai_client import (
    Choice,
    DecisionResult,
    ExplainResult,
    GenerationResult,
    Noul,
    OpenAIClient,
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

    def __init__(self, settings=None):
        self.settings = settings or get_settings()

    @property
    def enabled(self) -> bool:
        return self.settings.llm_enabled and bool(self.settings.openai_api_key)

    def _client(self) -> OpenAIClient:
        return OpenAIClient()

    def generate(
        self,
        instructions: str,
        input_text: str,
        json_schema: dict | None = None,
        max_output_tokens: int | None = None,
    ) -> GenerationResult:
        if not self.enabled:
            return GenerationResult(ok=False, error="not_configured", attempts=0)
        return self._client().generate(instructions, input_text, json_schema, max_output_tokens)

    def generate_response(self, prompt: str) -> str | None:
        """General text generation utility with OpenAI GPT-5 mini."""
        res = self.generate(
            instructions="You are DecisionGPT, an intelligent business decision-support assistant. Answer accurately based on facts.",
            input_text=prompt,
        )
        return res.text if res.ok else None

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
        """Strategy narrative explaining results that already exist. If OpenAI is available, uses GPT-5 mini; otherwise falls back to template."""
        if not self.enabled:
            return self._default_strategy_explanation(context)

        prompt = (
            f"Explain the following evaluated business strategy concisely (1-2 sentences) for an executive:\n"
            f"- Strategy Name: {context.get('strategy_name', 'Unnamed')}\n"
            f"- Expected Revenue: {context.get('expected_revenue', 'N/A')}\n"
            f"- Risk Level: {context.get('risk_level', 'N/A')}\n"
            f"Rule: State verified expected outcomes clearly without fabricating extra numbers."
        )
        res = self.generate(
            instructions="You are DecisionGPT's Strategy Synthesis Engine. Provide concise, grounded executive strategy explanations.",
            input_text=prompt,
            max_output_tokens=300,
        )
        if res.ok and res.text:
            return res.text
        return self._default_strategy_explanation(context)

    def _default_strategy_explanation(self, context: dict) -> str:
        parts = [f"Strategy: {context.get('strategy_name', 'Unnamed strategy')}."]
        if "expected_revenue" in context:
            parts.append(f"Expected revenue: {context['expected_revenue']}.")
        if "risk_level" in context:
            parts.append(f"Risk level: {context['risk_level']}.")
        return " ".join(parts)

    def evaluate_agent(self, agent_name: str, evaluation: dict) -> str:
        """One agent's structured evaluation synthesized. Uses GPT-5 mini when configured, otherwise deterministic template."""
        if not self.enabled:
            return self._default_evaluate_agent(agent_name, evaluation)

        label = agent_name.replace("_", " ").title()
        prompt = (
            f"Synthesize the following specialist evaluation into a concise executive finding (1-2 sentences):\n"
            f"Specialist: {label}\n"
            f"Key Points: {json.dumps(evaluation.get('key_points', []))}\n"
            f"Risks: {json.dumps(evaluation.get('risks', []))}\n"
            f"Assumptions: {json.dumps(evaluation.get('assumptions', []))}\n"
        )
        res = self.generate(
            instructions="You are DecisionGPT's Agent Review Synthesizer. Synthesize findings faithfully without hallucinating new data.",
            input_text=prompt,
            max_output_tokens=350,
        )
        if res.ok and res.text:
            return res.text
        return self._default_evaluate_agent(agent_name, evaluation)

    def _default_evaluate_agent(self, agent_name: str, evaluation: dict) -> str:
        label = agent_name.replace("_", " ").title()
        sentences = [f"{label}:"] + list(evaluation.get("key_points", []))
        if evaluation.get("risks"):
            sentences.append("Risks: " + " ".join(evaluation["risks"]))
        return " ".join(sentences)

    def consult_agent(
        self,
        agent_key: str,
        agent_name: str,
        agent_role: str,
        agent_purpose: str,
        task: str,
        evidence_items: list[dict],
    ) -> dict | None:
        """Call GPT-5 mini for an individual specialist agent consultation with strict structured output."""
        if not self.enabled:
            return None

        schema = {
            "type": "object",
            "required": [
                "executive_summary",
                "key_findings",
                "business_implications",
                "recommended_actions",
                "assumptions_and_limitations",
            ],
            "additionalProperties": False,
            "properties": {
                "executive_summary": {"type": "string", "description": "2-3 sentences summarizing the analysis"},
                "key_findings": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "2-4 factual findings derived from verified evidence",
                },
                "business_implications": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "2-3 business impact points",
                },
                "recommended_actions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "2-3 concrete actionable recommendations",
                },
                "assumptions_and_limitations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "2 stated assumptions or boundaries",
                },
            },
        }

        instructions = (
            f"You are the {agent_name} ({agent_role}) in DecisionGPT.\n"
            f"Your domain purpose: {agent_purpose}\n"
            f"Analyze the user's task strictly using the verified evidence provided.\n"
            f"Never invent new numbers, revenues, or percentages. Cite or interpret only the verified evidence provided."
        )

        input_text = (
            f"TASK: {task}\n\n"
            f"VERIFIED EVIDENCE:\n"
            + "\n".join(f"- [{e.get('id', 'F')}] {e.get('text')} (Source: {e.get('source')})" for e in evidence_items)
        )

        res = self.generate(
            instructions=instructions,
            input_text=input_text,
            json_schema=schema,
            max_output_tokens=1500,
        )

        if res.ok and isinstance(res.parsed, dict):
            out = dict(res.parsed)
            out["_llm_metadata"] = {
                "model": res.model,
                "response_model": res.response_model,
                "usage": res.usage,
                "latency_s": round(res.latency_s, 3),
                "estimated_cost_usd": res.estimated_cost_usd,
            }
            return out
        return None

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
