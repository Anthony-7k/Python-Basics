from sqlalchemy.orm import Session

from app.core.exceptions import (
    KnowledgeBaseNotFoundError,
)
from app.core.settings import (
    DEFAULT_USER_EMAIL,
)
from app.models import KnowledgeBase, User
from app.repositories import (
    ConversationRepository,
)


class KnowledgeBaseService:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session
        self.repository = (
            ConversationRepository(session)
        )

    def create(
        self,
        name: str,
        description: str | None = None,
    ) -> KnowledgeBase:
        try:
            user = self._get_default_user()
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
        user = self._get_default_user()
        self.session.commit()
        return self.repository.list_knowledge_bases(
            owner_user_id=user.id
        )

    def get(
        self,
        knowledge_base_id: str,
    ) -> KnowledgeBase:
        user = self._get_default_user()
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

        self.session.commit()
        return knowledge_base

    def _get_default_user(self) -> User:
        return self.repository.create_user(
            email=DEFAULT_USER_EMAIL,
            display_name=(
                "Local Development User"
            ),
        )
