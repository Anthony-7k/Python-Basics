from sqlalchemy.orm import Session

from app.core.exceptions import (
    ConversationKnowledgeBaseMismatchError,
    ConversationNotFoundError,
    KnowledgeBaseNotFoundError,
)
from app.core.settings import (
    DEFAULT_KNOWLEDGE_BASE_NAME,
    DEFAULT_USER_EMAIL,
)
from app.models import (
    Conversation,
    Message,
    MessageRole,
)
from app.repositories import (
    ConversationRepository,
)


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