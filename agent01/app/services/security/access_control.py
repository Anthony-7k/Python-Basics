from sqlalchemy.orm import Session

from app.core.exceptions import (
    ConversationNotFoundError,
    KnowledgeBaseNotFoundError,
)
from app.core.security import AuthenticatedUser
from app.models import (
    Conversation,
    KnowledgeBase,
    User,
)
from app.repositories import ConversationRepository


class AccessControlService:
    def __init__(
        self,
        session: Session,
        current_user: AuthenticatedUser,
    ) -> None:
        self.current_user = current_user
        self.repository = (
            ConversationRepository(session)
        )

    def get_or_create_user(self) -> User:
        return self.repository.create_user(
            email=self.current_user.email,
            display_name=(
                self.current_user.display_name
            ),
        )

    def require_knowledge_base_access(
        self,
        knowledge_base_id: str,
    ) -> KnowledgeBase:
        user = self.get_or_create_user()
        knowledge_base = (
            self.repository.get_knowledge_base(
                knowledge_base_id
            )
        )

        if (
            knowledge_base is None
            or knowledge_base.owner_user_id
            != user.id
        ):
            raise KnowledgeBaseNotFoundError(
                "Knowledge base not found"
            )

        return knowledge_base

    def require_conversation_access(
        self,
        conversation_id: str,
    ) -> Conversation:
        user = self.get_or_create_user()
        conversation = (
            self.repository.get_conversation(
                conversation_id
            )
        )

        if (
            conversation is None
            or conversation.user_id != user.id
        ):
            raise ConversationNotFoundError(
                "Conversation not found"
            )

        self.require_knowledge_base_access(
            conversation.knowledge_base_id
        )
        return conversation
