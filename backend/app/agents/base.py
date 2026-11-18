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
    meta: dict = field(default_factory=dict)  # internal, not persisted

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "score": self.score,
            "key_points": list(self.key_points),
            "risks": list(self.risks),
            "assumptions": list(self.assumptions),
        }


@dataclass
class PeerReview:
    """Round-2 output: one agent's reaction to its peers' round-1
    assessments of the same strategy (docs/MULTI_AGENT_SPECIFICATION.md §4
    "structured peer information"). Deterministic — an agent only ever
    reacts to numbers already produced in round 1, never invents new ones.
    """

    agent: str
    concurs: bool = True
    challenges: list[str] = field(default_factory=list)
    adjusted_score: float | None = None  # None => no change from round 1
    rationale: str = ""
    round: int = 2

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "round": self.round,
            "concurs": self.concurs,
            "challenges": list(self.challenges),
            "adjusted_score": self.adjusted_score,
            "rationale": self.rationale,
        }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
