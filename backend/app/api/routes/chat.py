from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_chat_service
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str


@router.post("")
def chat(
    request: ChatRequest, service: ChatService = Depends(get_chat_service)
) -> dict:
    """정량 데이터(Supabase)만 근거로 답하는 AI Analyst 챗봇."""
    return {"answer": service.ask(request.question)}
