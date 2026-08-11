from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AnalyzeGoalRequest(BaseModel):
    goal_id: str = Field(min_length=1)


class AlternativeStrategyOut(BaseModel):
    strategy_id: str
    strategy_name: str
    actions: list[dict]
    strategy_score: float
    risk_level: str
    expected_revenue: float


class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_id: str
    goal_id: str
    selected_strategy_id: str
    selected_strategy_name: str
    selected_strategy_score: float
    expected_outcome: dict
    risk_level: str
    confidence: float
    reasoning: str
    causal_graph_version: str | None
    agent_reviews: dict[str, str]
    alternatives: list[AlternativeStrategyOut]
    skipped_strategies: list[str]


class DecisionSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_id: str
    goal_id: str
    selected_strategy_id: str | None
    expected_outcome_json: dict
    risk_level: str
    confidence: float | None
    reasoning: str | None
    causal_graph_version: str | None
    created_at: datetime
