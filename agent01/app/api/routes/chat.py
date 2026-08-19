from time import perf_counter

from fastapi import (
    APIRouter,
    Depends,
    Request,
)

from app.api.dependencies import (
    get_conversation_service,
)
from app.schemas.rag import (
    ChatRequest,
    RAGResponse,
)
from app.services.conversations import (
    ConversationService,
    condense_question,
)
from app.services.rag.rag_service import (
    answer_question,
)


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
    conversation_service: (
        ConversationService
    ) = Depends(
        get_conversation_service
    ),
):
    started_at = perf_counter()

    conversation = (
        conversation_service
        .get_or_create_conversation(
            conversation_id=(
                request.conversation_id
            ),
            knowledge_base_id=(
                request.knowledge_base_id
            ),
        )
    )

    conversation_context = (
        conversation_service.prepare_context(
            conversation.id
        )
    )
    standalone_question = condense_question(
        history=(
            conversation_context.history
        ),
        current_question=request.question,
        conversation_summary=(
            conversation_context.summary
        ),
    )

    knowledge_base = getattr(
        conversation,
        "knowledge_base",
        None,
    )
    knowledge_base_version = getattr(
        knowledge_base,
        "version",
        1,
    )

    rag_result = answer_question(
        knowledge_base_id=(
            conversation.knowledge_base_id
        ),
        knowledge_base_version=(
            knowledge_base_version
        ),
        original_question=(
            request.question
        ),
        standalone_question=(
            standalone_question
        ),
        request_id=(
            http_request.state.request_id
        ),
    )

    response = RAGResponse.model_validate(
        rag_result
    )

    response.conversation_id = (
        conversation.id
    )

    response.latency_ms = round(
        (
            perf_counter()
            - started_at
        )
        * 1000,
        2,
    )

    source_summary = {
        "sources": [
            {
                "source_id": (
                    source.source_id
                ),
                "chunk_id": (
                    source.chunk_id
                ),
                "file_name": (
                    source.file_name
                ),
                "page": source.page,
            }
            for source in response.sources
        ]
    }

    conversation_service.save_exchange(
        conversation_id=conversation.id,
        user_content=request.question,
        assistant_content=response.answer,
        source_summary=source_summary,
    )

    return response
