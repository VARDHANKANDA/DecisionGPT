from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class ChatResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    answer: str
    intent: str
    sources: list[str]
    sufficient_evidence: bool
    answer_type: str = "known"
    details: dict[str, Any] = {}
    # "llm_analytics" (LLM-interpreted question, deterministic calculation) or "legacy_router" (fixed-intent router).
    path: str = "legacy_router"
    notice: str | None = None
