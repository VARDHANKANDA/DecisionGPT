from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class ChatResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    answer: str
    intent: str
    sources: list[str]
    sufficient_evidence: bool
