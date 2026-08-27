from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_chat_service
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    question: str
    history: list[ChatHistoryMessage] = []


@router.post("")
def chat(
    request: ChatRequest, service: ChatService = Depends(get_chat_service)
) -> dict:
    """정량 데이터(Supabase)만 근거로 답하는 AI Analyst 챗봇.

    history는 같은 대화창 내 이전 turn들(질문/답변)만 전달받는다 - 새 대화창을
    시작하면 프론트에서 빈 배열로 초기화되므로 대화창 간 기억은 유지되지 않는다.
    """
    history = [{"role": m.role, "content": m.content} for m in request.history]
    return service.ask(request.question, history)
