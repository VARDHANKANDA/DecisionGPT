from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AnalyzeGoalRequest(BaseModel):
    goal_id: str = Field(min_length=1)


class AlternativeStrategyOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    strategy_id: str
    strategy_name: str
    actions: list[dict]
    strategy_score: float
    risk_level: str
    expected_revenue: float
    rationale: str | None = None
    confidence: float | None = None
    conflicts: list[dict] = Field(default_factory=list)


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
    memory_insights: list[str]
    causal_context: dict = Field(default_factory=dict)
    debate: dict = Field(default_factory=dict)
    strategy_generation: dict = Field(default_factory=dict)
    trace: dict = Field(default_factory=dict)


class FeatureContributionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    feature: str
    label: str
    contribution: float
    direction: str


class ExplanationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_name: str
    model_version: str
    shap_available: bool
    unavailable_reason: str | None
    local_factors: list[FeatureContributionOut]
    global_importance: list[FeatureContributionOut]


class DecisionExplanationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decision_id: str
    explanation: ExplanationOut
    reasoning: str
    agent_reviews: dict[str, str]
    counterfactual: dict
    uncertainty: dict
    assumptions: list[str]
    causal_context: dict = Field(default_factory=dict)


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


class DecisionTraceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decision_id: str
    business_id: str
    goal_id: str
    created_at: datetime
    business_state_version: str | None
    business_state: dict | None
    selected_strategy: dict
    candidate_strategy_ids: list[str]
    simulation_ids: list[str]
    agent_run_ids: list[str]
    agent_runs: list[dict]
    model_versions: dict
    causal_graph_version: str | None
    causal_context: dict
    debate: dict
    strategy_generation: dict
    assumptions: list[str]
    uncertainty: dict
    expected_outcome: dict
    reasoning: str | None
    confidence: float | None
    prompt_version: str | None
    reproducible: dict
