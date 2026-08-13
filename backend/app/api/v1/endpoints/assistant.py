from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.assistant import ChatRequest, ChatResponseOut
from app.services import assistant_service

router = APIRouter()


@router.post("/businesses/{business_id}/chat", response_model=ChatResponseOut)
def chat(business_id: str, payload: ChatRequest, db: Session = Depends(get_db)):
    return assistant_service.answer_question(db, business_id, payload.message)
