import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.core.security import AuthenticatedUser
from app.models import IngestionJobStatus
from app.services.documents import DocumentService
from app.services.knowledge_bases import (
    KnowledgeBaseService,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(
        engine,
        expire_on_commit=False,
    ) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_knowledge_base_version_tracks_document_lifecycle(
    db_session: Session,
):
    current_user = AuthenticatedUser(
        email="cache-test@example.com"
    )
    knowledge_base = KnowledgeBaseService(
        db_session,
        current_user=current_user,
    ).create("HR Policies")
    service = DocumentService(
        db_session,
        vector_delete=lambda _kb, _doc: None,
        current_user=current_user,
    )
    document, job, created = (
        service.create_or_get_upload(
            content_hash="a" * 64,
            file_name="policy.txt",
            knowledge_base_id=(
                knowledge_base.id
            ),
        )
    )

    assert created is True
    assert knowledge_base.version == 1

    service.update_ingestion_status(
        job.id,
        IngestionJobStatus.RUNNING,
    )
    service.update_ingestion_status(
        job.id,
        IngestionJobStatus.SUCCEEDED,
    )
    db_session.refresh(knowledge_base)
    assert knowledge_base.version == 2

    service.update_ingestion_status(
        job.id,
        IngestionJobStatus.SUCCEEDED,
    )
    db_session.refresh(knowledge_base)
    assert knowledge_base.version == 2

    reindex_result = service.request_reindex(
        knowledge_base_id=knowledge_base.id,
        document_id=document.id,
    )
    assert reindex_result is not None
    _, reindex_job, reindex_created = (
        reindex_result
    )
    assert reindex_created is True
    db_session.refresh(knowledge_base)
    assert knowledge_base.version == 3

    service.update_ingestion_status(
        reindex_job.id,
        IngestionJobStatus.SUCCEEDED,
    )
    db_session.refresh(knowledge_base)
    assert knowledge_base.version == 4

    service.delete_document(
        knowledge_base_id=knowledge_base.id,
        document_id=document.id,
    )
    db_session.refresh(knowledge_base)
    assert knowledge_base.version == 5
