from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CausalEdgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_node: str
    target_node: str
    relationship: str
    strength: float | None
    confidence: float | None
    evidence_type: str
    time_lag: int | None
    note: str


class CausalGraphOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_id: str
    version: str
    method: str
    evidence_summary: str
    created_at: datetime | None
    edges: list[CausalEdgeOut]
