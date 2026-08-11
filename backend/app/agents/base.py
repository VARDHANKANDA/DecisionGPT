"""Shared agent contract — docs/MULTI_AGENT_SPECIFICATION.md §5.

Every agent in app/agents/*.py is a pure function: `evaluate(output, goal)
-> AgentEvaluationResult`, reading only from a real, already-computed
digital_twin_service.SimulationOutput and the Goal. No agent calls an LLM,
a model, or invents a number (§6 "Numerical Integrity") — they interpret
numbers that already exist. Narration (turning this into readable prose)
is a separate, later step via LLMService.evaluate_agent.
"""
from dataclasses import dataclass, field


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass
class AgentEvaluationResult:
    agent: str
    score: float
    key_points: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
