from time import perf_counter

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
    started_at = perf_counter()

    result = answer_question(
        question=request.question,
        request_id=http_request.state.request_id,
    )

    result["latency_ms"] = round(
        (perf_counter() - started_at) * 1000,
        2,
    )

    return result