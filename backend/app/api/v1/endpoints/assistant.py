from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, research_access_granted
from app.db.session import get_db
from app.models.user import User
from app.schemas.assistant import ChatRequest, ChatResponseOut
from app.services import agent_consult_service, assistant_service

router = APIRouter()


class AgentConsultIn(BaseModel):
    task: str = Field(min_length=1, max_length=1000)


@router.post("/businesses/{business_id}/chat", response_model=ChatResponseOut)
def chat(
    business_id: str,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
    x_research_token: str | None = Header(default=None),
):
    # ``business_id`` was authorised by the route guard. Whether this caller may also see research-level evaluation results (registered models and
    # benchmarks on research datasets) is decided here with the Research Console's own rule and passed down; the service never decides it itself.
    return assistant_service.answer_question(db, business_id, payload.message, research_access=research_access_granted(user, x_research_token))


@router.post("/businesses/{business_id}/agents/{agent_id}/consult")
def consult_individual_agent(
    business_id: str,
    agent_id: str,
    payload: AgentConsultIn,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """Executes dedicated domain analysis for one of the specialized DecisionGPT agents."""
    return agent_consult_service.consult_agent(db, business_id, agent_id, payload.task)
