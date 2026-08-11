from pydantic import BaseModel, ConfigDict, Field


class ActionIn(BaseModel):
    type: str
    value: float


class SimulateRequest(BaseModel):
    goal_id: str | None = None
    actions: list[ActionIn] = Field(min_length=1)
    horizon_days: int = Field(default=14, ge=1, le=90)


class SimulationOutputOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    expected_units_sold: float
    baseline_units_sold: float
    expected_revenue: float
    baseline_revenue: float
    expected_profit: float | None
    baseline_profit: float | None
    profit_note: str | None
    customer_impact: int | None
    inventory_constrained: bool
    risk_level: str
    risk_score: float
    revenue_lower_bound: float
    revenue_upper_bound: float
    model_name: str
    model_version: str
    assumptions: list[str]


class SimulationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_id: str
    goal_id: str | None
    input_state: dict
    actions: list[dict]
    output: SimulationOutputOut
