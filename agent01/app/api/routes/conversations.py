from fastapi import (
    APIRouter,
    Depends,
)

from app.api.dependencies import (
    get_conversation_service,
)
from app.schemas.conversation import (
    ConversationMessagesResponse,
)
from app.services.conversations import (
    ConversationService,
)


router = APIRouter(
    prefix="/api/v1",
    tags=["conversations"],
)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=(
        ConversationMessagesResponse
    ),
)
def get_conversation_messages(
    conversation_id: str,
    conversation_service: (
        ConversationService
    ) = Depends(
        get_conversation_service
    ),
):
    messages = (
        conversation_service.get_messages(
            conversation_id
        )
    )

    return ConversationMessagesResponse(
        conversation_id=conversation_id,
        messages=messages,
    )   