from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RecordOutcomeRequest(BaseModel):
    actual_outcome: dict = Field(min_length=1)
    recorded_at: datetime | None = None


class DecisionOutcomeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    decision_id: str
    actual_outcome_json: dict
    goal_achieved: bool | None
    goal_achievement_score: float | None
    recorded_at: datetime


class BusinessMemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_id: str
    memory_type: str
    content: str
    metadata_json: dict
    created_at: datetime
