from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.conversations import (
    ConversationService,
)
from app.services.documents import (
    DocumentService,
)

def get_conversation_service(
    db: Session = Depends(get_db),
) -> ConversationService:
    return ConversationService(db)


def get_document_service(
    db: Session = Depends(get_db),
) -> DocumentService:
    return DocumentService(db)