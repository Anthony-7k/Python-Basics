from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.exceptions import (
    ConversationKnowledgeBaseMismatchError,
    ConversationNotFoundError,
    KnowledgeBaseNotFoundError,
)
from app.core.settings import (
    CONVERSATION_HISTORY_MAX_TURNS,
    CONVERSATION_HISTORY_TOKEN_BUDGET,
    DEFAULT_KNOWLEDGE_BASE_NAME,
    DEFAULT_USER_EMAIL,
)
from app.core.logging_config import get_logger
from app.models import (
    Conversation,
    Message,
    MessageRole,
)
from app.repositories import (
    ConversationRepository,
)
from app.services.conversations.query_rewriter import (
    estimate_text_tokens,
    fit_summary_messages_to_budget,
    format_history,
    summarize_conversation,
)


SUMMARY_BATCH_MESSAGE_LIMIT = 20
logger = get_logger(__name__)


@dataclass(frozen=True)
class ConversationContext:
    summary: str | None
    history: list[dict[str, object]]
    estimated_tokens: int


class ConversationService:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

        self.repository = (
            ConversationRepository(
                session
            )
        )

    def get_or_create_conversation(
        self,
        conversation_id: str | None = None,
        knowledge_base_id: str | None = None,
    ) -> Conversation:
        try:
            if conversation_id is not None:
                conversation = (
                    self.repository
                    .get_conversation(
                        conversation_id
                    )
                )

                if conversation is None:
                    raise (
                        ConversationNotFoundError(
                            "Conversation not found"
                        )
                    )

                if (
                    knowledge_base_id
                    is not None
                    and conversation
                    .knowledge_base_id
                    != knowledge_base_id
                ):
                    raise (
                        ConversationKnowledgeBaseMismatchError(
                            "Conversation does not "
                            "belong to the requested "
                            "knowledge base"
                        )
                    )

                return conversation

            if knowledge_base_id is not None:
                knowledge_base = (
                    self.repository
                    .get_knowledge_base(
                        knowledge_base_id
                    )
                )

                if knowledge_base is None:
                    raise (
                        KnowledgeBaseNotFoundError(
                            "Knowledge base not found"
                        )
                    )

                user_id = (
                    knowledge_base.owner_user_id
                )

            else:
                user = (
                    self.repository.create_user(
                        email=DEFAULT_USER_EMAIL,
                        display_name=(
                            "Local Development User"
                        ),
                    )
                )

                knowledge_base = (
                    self.repository
                    .get_or_create_knowledge_base(
                        owner_user_id=user.id,
                        name=(
                            DEFAULT_KNOWLEDGE_BASE_NAME
                        ),
                    )
                )

                user_id = user.id

            conversation = (
                self.repository
                .create_conversation(
                    user_id=user_id,
                    knowledge_base_id=(
                        knowledge_base.id
                    ),
                    title=None,
                )
            )

            self.session.commit()

            return conversation

        except Exception:
            self.session.rollback()
            raise

    def get_messages(
        self,
        conversation_id: str,
    ) -> list[Message]:
        conversation = (
            self.repository
            .get_conversation(
                conversation_id
            )
        )

        if conversation is None:
            raise ConversationNotFoundError(
                "Conversation not found"
            )

        return self.repository.list_messages(
            conversation_id
        )

    @staticmethod
    def _message_to_history_item(
        message: Message,
    ) -> dict[str, object]:
        return {
            "sequence_number": (
                message.sequence_number
            ),
            "role": message.role.value,
            "content": message.content,
            "source_summary": (
                message.source_summary
            ),
        }

    def prepare_context(
        self,
        conversation_id: str,
        max_turns: int = (
            CONVERSATION_HISTORY_MAX_TURNS
        ),
        token_budget: int = (
            CONVERSATION_HISTORY_TOKEN_BUDGET
        ),
    ) -> ConversationContext:
        conversation = (
            self.repository.get_conversation(
                conversation_id
            )
        )

        if conversation is None:
            raise ConversationNotFoundError(
                "Conversation not found"
            )

        recent_messages = (
            self.repository
            .list_recent_messages(
                conversation_id=(
                    conversation_id
                ),
                limit=max_turns * 2,
            )
        )
        summary_cutoff = (
            recent_messages[0]
            .sequence_number
            - 1
            if recent_messages
            else 0
        )

        while (
            conversation
            .summary_through_sequence_number
            < summary_cutoff
        ):
            pending_messages = (
                self.repository
                .list_messages_for_summary(
                    conversation_id=(
                        conversation_id
                    ),
                    after_sequence_number=(
                        conversation
                        .summary_through_sequence_number
                    ),
                    through_sequence_number=(
                        summary_cutoff
                    ),
                    limit=(
                        SUMMARY_BATCH_MESSAGE_LIMIT
                    ),
                )
            )

            if not pending_messages:
                break

            pending_history = [
                self._message_to_history_item(
                    message
                )
                for message in pending_messages
            ]
            summary_batch = (
                fit_summary_messages_to_budget(
                    messages=pending_history,
                    existing_summary=(
                        conversation.summary
                    ),
                    token_budget=token_budget,
                )
            )

            if not summary_batch:
                break

            through_sequence_number = int(
                summary_batch[-1][
                    "sequence_number"
                ]
            )

            try:
                updated_summary = (
                    summarize_conversation(
                        existing_summary=(
                            conversation.summary
                        ),
                        messages=summary_batch,
                        token_budget=token_budget,
                    )
                )

                if not updated_summary:
                    break

                self.repository.update_summary(
                    conversation=conversation,
                    summary=updated_summary,
                    through_sequence_number=(
                        through_sequence_number
                    ),
                )
                self.session.commit()
            except Exception:
                self.session.rollback()
                logger.warning(
                    "conversation summary update failed "
                    "conversation_id=%s; using recent history only",
                    conversation_id,
                    exc_info=True,
                )
                break

        history = [
            self._message_to_history_item(
                message
            )
            for message in recent_messages
        ]
        context_text = format_history(
            history
        )

        if conversation.summary:
            context_text = (
                conversation.summary
                + "\n\n"
                + context_text
            )

        return ConversationContext(
            summary=conversation.summary,
            history=history,
            estimated_tokens=(
                estimate_text_tokens(
                    context_text
                )
            ),
        )

    def save_exchange(
        self,
        conversation_id: str,
        user_content: str,
        assistant_content: str,
        source_summary: dict | None = None,
    ) -> None:
        try:
            self.repository.add_message(
                conversation_id=(
                    conversation_id
                ),
                role=MessageRole.USER,
                content=user_content,
            )

            self.repository.add_message(
                conversation_id=(
                    conversation_id
                ),
                role=MessageRole.ASSISTANT,
                content=assistant_content,
                source_summary=source_summary,
            )

            self.session.commit()

        except Exception:
            self.session.rollback()
            raise
