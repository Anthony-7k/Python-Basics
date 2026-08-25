import pytest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.core.security import AuthenticatedUser
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


TEST_DEFAULT_USER_EMAIL = (
    "local-user@agent01.local"
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
            knowledge_base.id,
            document_id,
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
        db_session,
        current_user=AuthenticatedUser(
            email=TEST_DEFAULT_USER_EMAIL
        ),
    )

    document_id = "d" * 64

    first_document, first_job, first_created = (
        service.create_or_get_upload(
            content_hash=document_id,
            file_name="first.txt",
        )
    )

    (
        second_document,
        second_job,
        second_created,
    ) = service.create_or_get_upload(
        content_hash=document_id,
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
        db_session,
        current_user=AuthenticatedUser(
            email=TEST_DEFAULT_USER_EMAIL
        ),
    )

    document_id = "e" * 64

    document, job, created = (
        service.create_or_get_upload(
            content_hash=document_id,
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
    deleted_documents = []

    service = DocumentService(
        db_session,
        vector_delete=(
            lambda knowledge_base_id,
            document_id: deleted_documents.append(
                (
                    knowledge_base_id,
                    document_id,
                )
            )
        ),
        current_user=AuthenticatedUser(
            email=TEST_DEFAULT_USER_EMAIL
        ),
    )

    document_id = "f" * 64

    document, _, _ = (
        service.create_or_get_upload(
            content_hash=document_id,
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
        service.delete_document(
            knowledge_base_id=(
                document.knowledge_base_id
            ),
            document_id=document.id,
        )
    )

    assert deleted_document is not None
    assert (
        deleted_document.status
        == DocumentStatus.DELETED
    )
    assert deleted_documents == [
        (
            document.knowledge_base_id,
            document.id,
        )
    ]


def test_delete_document_rolls_back_when_vector_delete_fails(
    db_session: Session,
):
    def failing_vector_delete(
        knowledge_base_id: str,
        document_id: str,
    ):
        raise RuntimeError(
            "Chroma deletion failed"
        )

    service = DocumentService(
        db_session,
        vector_delete=failing_vector_delete,
        current_user=AuthenticatedUser(
            email=TEST_DEFAULT_USER_EMAIL
        ),
    )

    document_id = "1" * 64

    document, _, _ = (
        service.create_or_get_upload(
            content_hash=document_id,
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
        service.delete_document(
            knowledge_base_id=(
                document.knowledge_base_id
            ),
            document_id=document.id,
        )

    saved_document = (
        service.document_repository
        .get_document(document.id)
    )

    assert (
        saved_document.status
        == DocumentStatus.READY
    )


def test_same_content_is_scoped_to_knowledge_base(
    db_session: Session,
):
    repository = ConversationRepository(
        db_session
    )
    user = repository.create_user(
        email="scope-test@example.com"
    )
    kb_a = repository.create_knowledge_base(
        owner_user_id=user.id,
        name="KB A",
    )
    kb_b = repository.create_knowledge_base(
        owner_user_id=user.id,
        name="KB B",
    )
    db_session.commit()

    service = DocumentService(
        db_session,
        current_user=AuthenticatedUser(
            email="scope-test@example.com"
        ),
    )
    content_hash = "2" * 64

    doc_a, _, created_a = (
        service.create_or_get_upload(
            content_hash=content_hash,
            file_name="same.txt",
            knowledge_base_id=kb_a.id,
        )
    )
    doc_b, _, created_b = (
        service.create_or_get_upload(
            content_hash=content_hash,
            file_name="same.txt",
            knowledge_base_id=kb_b.id,
        )
    )

    assert created_a is True
    assert created_b is True
    assert doc_a.id != doc_b.id
    assert doc_a.content_hash == content_hash
    assert doc_b.content_hash == content_hash

    deleted = []
    service.vector_delete = (
        lambda knowledge_base_id,
        document_id: deleted.append(
            (knowledge_base_id, document_id)
        )
    )
    assert service.delete_document(
        knowledge_base_id=kb_b.id,
        document_id=doc_a.id,
    ) is None
    service.delete_document(
        knowledge_base_id=kb_a.id,
        document_id=doc_a.id,
    )

    assert deleted == [(kb_a.id, doc_a.id)]
    assert service.get_document(
        knowledge_base_id=kb_b.id,
        document_id=doc_b.id,
    ).status != DocumentStatus.DELETED


def test_reindex_is_idempotent_and_failed_job_can_retry(
    db_session: Session,
):
    service = DocumentService(
        db_session,
        current_user=AuthenticatedUser(
            email=TEST_DEFAULT_USER_EMAIL
        ),
    )
    document, first_job, _ = (
        service.create_or_get_upload(
            content_hash="3" * 64,
            file_name="reindex.txt",
        )
    )
    service.update_ingestion_status(
        task_id=first_job.id,
        status=IngestionJobStatus.SUCCEEDED,
    )

    first_reindex = service.request_reindex(
        knowledge_base_id=(
            document.knowledge_base_id
        ),
        document_id=document.id,
    )
    assert first_reindex is not None
    _, reindex_job, created = first_reindex
    assert created is True

    duplicate = service.request_reindex(
        knowledge_base_id=(
            document.knowledge_base_id
        ),
        document_id=document.id,
    )
    assert duplicate is not None
    assert duplicate[1].id == reindex_job.id
    assert duplicate[2] is False

    service.update_ingestion_status(
        task_id=reindex_job.id,
        status=IngestionJobStatus.FAILED,
        error="temporary failure",
    )
    retry = service.request_reindex(
        knowledge_base_id=(
            document.knowledge_base_id
        ),
        document_id=document.id,
    )
    assert retry is not None
    assert retry[1].id != reindex_job.id
    assert retry[2] is True
