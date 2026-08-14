from fastapi import APIRouter, Request

from app.schemas.rag import ChatRequest, RAGResponse
from app.services.rag.rag_service import answer_question


router = APIRouter(
    prefix="/api/v1",
    tags=["chat"],
)


@router.post(
    "/chat",
    response_model=RAGResponse,
)
def chat(
    request: ChatRequest,
    http_request: Request,
):
    return answer_question(
        question=request.question,
        request_id=http_request.state.request_id,
    )