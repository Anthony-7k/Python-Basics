import pytest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import (
    DocumentStatus,
    IngestionJobStatus,
)
from app.repositories import (
    ConversationRepository,
    DocumentRepository,
)
from app.services.documents import (
    DocumentService,
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

    @event.listens_for(
        engine,
        "connect",
    )
    def enable_foreign_keys(
        dbapi_connection,
        connection_record,
    ):
        cursor = dbapi_connection.cursor()

        cursor.execute(
            "PRAGMA foreign_keys=ON"
        )

        cursor.close()

    Base.metadata.create_all(engine)

    with Session(
        engine,
        expire_on_commit=False,
    ) as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


def create_knowledge_base(
    session: Session,
):
    repository = ConversationRepository(
        session
    )

    user = repository.create_user(
        email="document-test@example.com",
        display_name="Document Test",
    )

    knowledge_base = (
        repository.create_knowledge_base(
            owner_user_id=user.id,
            name="Document Test KB",
        )
    )

    session.commit()

    return knowledge_base


def test_create_document_and_ingestion_job(
    db_session: Session,
):
    knowledge_base = create_knowledge_base(
        db_session
    )

    repository = DocumentRepository(
        db_session
    )

    document_id = "a" * 64

    document = repository.create_document(
        document_id=document_id,
        knowledge_base_id=(
            knowledge_base.id
        ),
        file_name="employee.txt",
        content_hash=document_id,
    )

    job = repository.create_ingestion_job(
        document_id=document.id
    )

    db_session.commit()

    saved_document = (
        repository.get_document(
            document_id
        )
    )

    saved_job = (
        repository.get_ingestion_job(
            job.id
        )
    )

    assert saved_document is not None
    assert saved_job is not None

    assert (
        saved_document.status
        == DocumentStatus.PENDING
    )

    assert (
        saved_job.status
        == IngestionJobStatus.PENDING
    )


def test_document_content_is_idempotent(
    db_session: Session,
):
    knowledge_base = create_knowledge_base(
        db_session
    )

    repository = DocumentRepository(
        db_session
    )

    document_id = "b" * 64

    document = repository.create_document(
        document_id=document_id,
        knowledge_base_id=(
            knowledge_base.id
        ),
        file_name="first.txt",
        content_hash=document_id,
    )

    job = repository.create_ingestion_job(
        document_id=document.id
    )

    db_session.commit()

    existing_document = (
        repository
        .get_document_by_content_hash(
            document_id
        )
    )

    existing_job = (
        repository
        .get_latest_job_by_document_id(
            document_id
        )
    )

    assert (
        existing_document.id
        == document.id
    )

    assert existing_job.id == job.id


def test_document_transaction_rollback(
    db_session: Session,
):
    knowledge_base = create_knowledge_base(
        db_session
    )

    repository = DocumentRepository(
        db_session
    )

    document_id = "c" * 64

    document = repository.create_document(
        document_id=document_id,
        knowledge_base_id=(
            knowledge_base.id
        ),
        file_name="rollback.txt",
        content_hash=document_id,
    )

    job = repository.create_ingestion_job(
        document_id=document.id
    )

    db_session.commit()

    repository.update_ingestion_job(
        task_id=job.id,
        status=(
            IngestionJobStatus.RUNNING
        ),
    )

    repository.update_document_status(
        document_id=document.id,
        status=DocumentStatus.READY,
    )

    db_session.rollback()

    saved_document = (
        repository.get_document(
            document.id
        )
    )

    saved_job = (
        repository.get_ingestion_job(
            job.id
        )
    )

    assert (
        saved_document.status
        == DocumentStatus.PENDING
    )

    assert (
        saved_job.status
        == IngestionJobStatus.PENDING
    )


def test_document_service_is_idempotent(
    db_session: Session,
):
    service = DocumentService(
        db_session
    )

    document_id = "d" * 64

    first_document, first_job, first_created = (
        service.create_or_get_upload(
            document_id=document_id,
            file_name="first.txt",
        )
    )

    (
        second_document,
        second_job,
        second_created,
    ) = service.create_or_get_upload(
        document_id=document_id,
        file_name="second.txt",
    )

    assert first_created is True
    assert second_created is False

    assert (
        second_document.id
        == first_document.id
    )

    assert second_job.id == first_job.id

    assert (
        second_document.file_name
        == "first.txt"
    )


def test_document_service_updates_statuses(
    db_session: Session,
):
    service = DocumentService(
        db_session
    )

    document_id = "e" * 64

    document, job, created = (
        service.create_or_get_upload(
            document_id=document_id,
            file_name="status.txt",
        )
    )

    assert created is True

    running_job = (
        service.update_ingestion_status(
            task_id=job.id,
            status=(
                IngestionJobStatus.RUNNING
            ),
        )
    )

    assert (
        running_job.status
        == IngestionJobStatus.RUNNING
    )

    succeeded_job = (
        service.update_ingestion_status(
            task_id=job.id,
            status=(
                IngestionJobStatus.SUCCEEDED
            ),
        )
    )

    saved_document = (
        service.document_repository
        .get_document(document.id)
    )

    assert (
        succeeded_job.status
        == IngestionJobStatus.SUCCEEDED
    )

    assert (
        saved_document.status
        == DocumentStatus.READY
    )


def test_delete_document_marks_it_deleted(
    db_session: Session,
):
    deleted_document_ids = []

    service = DocumentService(
        db_session,
        vector_delete=(
            deleted_document_ids.append
        ),
    )

    document_id = "f" * 64

    document, _, _ = (
        service.create_or_get_upload(
            document_id=document_id,
            file_name="delete.txt",
        )
    )

    service.document_repository\
        .update_document_status(
            document_id=document.id,
            status=DocumentStatus.READY,
        )

    db_session.commit()

    deleted_document = (
        service.delete_document(document.id)
    )

    assert deleted_document is not None
    assert (
        deleted_document.status
        == DocumentStatus.DELETED
    )
    assert deleted_document_ids == [
        document.id
    ]


def test_delete_document_rolls_back_when_vector_delete_fails(
    db_session: Session,
):
    def failing_vector_delete(
        document_id: str,
    ):
        raise RuntimeError(
            "Chroma deletion failed"
        )

    service = DocumentService(
        db_session,
        vector_delete=failing_vector_delete,
    )

    document_id = "1" * 64

    document, _, _ = (
        service.create_or_get_upload(
            document_id=document_id,
            file_name="rollback-delete.txt",
        )
    )

    service.document_repository\
        .update_document_status(
            document_id=document.id,
            status=DocumentStatus.READY,
        )

    db_session.commit()

    with pytest.raises(
        RuntimeError,
        match="Chroma deletion failed",
    ):
        service.delete_document(document.id)

    saved_document = (
        service.document_repository
        .get_document(document.id)
    )

    assert (
        saved_document.status
        == DocumentStatus.READY
    )