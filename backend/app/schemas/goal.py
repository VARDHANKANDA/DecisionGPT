from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GoalCreateRequest(BaseModel):
    text: str


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_id: str
    objective: str
    target_value: float
    target_unit: str
    primary_kpi: str
    time_horizon: int | None
    constraints_json: list
    status: str
    created_at: datetime
    updated_at: datetime
