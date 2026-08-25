from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.authentication import (
    get_current_user,
)
from app.core.security import AuthenticatedUser
from app.db.session import get_db
from app.services.conversations import (
    ConversationService,
)
from app.services.documents import (
    DocumentService,
)
from app.services.knowledge_bases import (
    KnowledgeBaseService,
)
from app.services.agent import BoundedAgentService


def get_conversation_service(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
) -> ConversationService:
    return ConversationService(
        db,
        current_user=current_user,
    )


def get_document_service(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
) -> DocumentService:
    return DocumentService(
        db,
        current_user=current_user,
    )


def get_knowledge_base_service(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
) -> KnowledgeBaseService:
    return KnowledgeBaseService(
        db,
        current_user=current_user,
    )


def get_agent_service(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
) -> BoundedAgentService:
    return BoundedAgentService(
        db,
        current_user=current_user,
    )
