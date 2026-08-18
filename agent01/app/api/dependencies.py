from fastapi import Depends
from sqlalchemy.orm import Session

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

def get_conversation_service(
    db: Session = Depends(get_db),
) -> ConversationService:
    return ConversationService(db)


def get_document_service(
    db: Session = Depends(get_db),
) -> DocumentService:
    return DocumentService(db)


def get_knowledge_base_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseService:
    return KnowledgeBaseService(db)
