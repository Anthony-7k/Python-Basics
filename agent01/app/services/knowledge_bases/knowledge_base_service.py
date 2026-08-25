from sqlalchemy.orm import Session

from app.core.security import AuthenticatedUser
from app.models import KnowledgeBase
from app.repositories import (
    ConversationRepository,
)
from app.services.security import (
    AccessControlService,
)


class KnowledgeBaseService:
    def __init__(
        self,
        session: Session,
        current_user: AuthenticatedUser,
    ) -> None:
        self.session = session
        self.repository = (
            ConversationRepository(session)
        )
        self.access_control = (
            AccessControlService(
                session,
                current_user,
            )
        )

    def create(
        self,
        name: str,
        description: str | None = None,
    ) -> KnowledgeBase:
        try:
            user = (
                self.access_control
                .get_or_create_user()
            )
            knowledge_base = (
                self.repository
                .create_knowledge_base(
                    owner_user_id=user.id,
                    name=name.strip(),
                    description=(
                        description.strip()
                        if description is not None
                        else None
                    ),
                )
            )
            self.session.commit()
            return knowledge_base
        except Exception:
            self.session.rollback()
            raise

    def list(self) -> list[KnowledgeBase]:
        user = (
            self.access_control
            .get_or_create_user()
        )
        self.session.commit()
        return self.repository.list_knowledge_bases(
            owner_user_id=user.id
        )

    def get(
        self,
        knowledge_base_id: str,
    ) -> KnowledgeBase:
        knowledge_base = (
            self.access_control
            .require_knowledge_base_access(
                knowledge_base_id
            )
        )

        self.session.commit()
        return knowledge_base
