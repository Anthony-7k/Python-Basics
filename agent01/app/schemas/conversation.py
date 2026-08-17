from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
)


class ConversationMessageResponse(
    BaseModel
):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: str
    sequence_number: int
    role: str
    content: str
    source_summary: dict | None
    created_at: datetime


class ConversationMessagesResponse(
    BaseModel
):
    conversation_id: str

    messages: list[
        ConversationMessageResponse
    ]