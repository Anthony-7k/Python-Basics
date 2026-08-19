from collections.abc import Callable
from hashlib import sha256
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.exceptions import (
    DocumentReindexConflictError,
    KnowledgeBaseNotFoundError,
)
from app.core.settings import (
    DEFAULT_KNOWLEDGE_BASE_NAME,
    DEFAULT_USER_EMAIL,
)
from app.models import (
    Document,
    DocumentStatus,
    IngestionJob,
    IngestionJobStatus,
)
from app.repositories import (
    ConversationRepository,
    DocumentRepository,
)


def build_document_id(
    knowledge_base_id: str,
    content_hash: str,
) -> str:
    scoped_value = (
        f"{knowledge_base_id}:{content_hash}"
    )
    return sha256(
        scoped_value.encode("utf-8")
    ).hexdigest()


class DocumentService:
    def __init__(
        self,
        session: Session,
        vector_delete: (
            Callable[[str, str], None]
            | None
        ) = None,
    ) -> None:
        self.session = session
        self.vector_delete = vector_delete
        self.document_repository = (
            DocumentRepository(session)
        )
        self.conversation_repository = (
            ConversationRepository(session)
        )

    def create_or_get_upload(
        self,
        content_hash: str,
        file_name: str,
        knowledge_base_id: str | None = None,
    ) -> tuple[
        Document,
        IngestionJob,
        bool,
    ]:
        try:
            knowledge_base = (
                self._resolve_knowledge_base(
                    knowledge_base_id
                )
            )
            safe_file_name = Path(
                file_name
            ).name
            existing_document = (
                self.document_repository
                .get_document_by_content_hash(
                    knowledge_base_id=(
                        knowledge_base.id
                    ),
                    content_hash=content_hash,
                )
            )

            if existing_document is not None:
                if existing_document.status in {
                    DocumentStatus.FAILED,
                    DocumentStatus.DELETED,
                }:
                    existing_document.file_name = (
                        safe_file_name
                    )
                return self._reuse_or_retry(
                    existing_document
                )

            document = (
                self.document_repository
                .create_document(
                    document_id=(
                        build_document_id(
                            knowledge_base.id,
                            content_hash,
                        )
                    ),
                    knowledge_base_id=(
                        knowledge_base.id
                    ),
                    file_name=safe_file_name,
                    content_hash=content_hash,
                )
            )
            job = (
                self.document_repository
                .create_ingestion_job(
                    document.id
                )
            )
            self.session.commit()
            return document, job, True
        except Exception:
            self.session.rollback()
            raise

    def get_document(
        self,
        knowledge_base_id: str,
        document_id: str,
    ) -> Document | None:
        return (
            self.document_repository
            .get_document_for_knowledge_base(
                document_id=document_id,
                knowledge_base_id=(
                    knowledge_base_id
                ),
            )
        )

    def list_documents(
        self,
        knowledge_base_id: str,
        include_deleted: bool = False,
    ) -> list[Document]:
        self._resolve_knowledge_base(
            knowledge_base_id
        )
        return (
            self.document_repository
            .list_documents(
                knowledge_base_id=(
                    knowledge_base_id
                ),
                include_deleted=include_deleted,
            )
        )

    def get_ingestion_job(
        self,
        task_id: str,
    ) -> IngestionJob | None:
        return (
            self.document_repository
            .get_ingestion_job(task_id)
        )

    def update_ingestion_status(
        self,
        task_id: str,
        status: IngestionJobStatus,
        error: str | None = None,
    ) -> IngestionJob | None:
        try:
            existing_job = (
                self.document_repository
                .get_ingestion_job(task_id)
            )
            previous_status = (
                existing_job.status
                if existing_job is not None
                else None
            )
            job = (
                self.document_repository
                .update_ingestion_job(
                    task_id=task_id,
                    status=status,
                    error=error,
                )
            )

            if job is None:
                return None

            if (
                status
                == IngestionJobStatus.SUCCEEDED
            ):
                document_status = (
                    DocumentStatus.READY
                )
            elif (
                status
                == IngestionJobStatus.FAILED
            ):
                document_status = (
                    DocumentStatus.FAILED
                )
            else:
                document_status = (
                    DocumentStatus.PENDING
                )

            self.document_repository\
                .update_document_status(
                    document_id=(
                        job.document_id
                    ),
                    status=document_status,
                )

            if (
                status
                == IngestionJobStatus.SUCCEEDED
                and previous_status
                != IngestionJobStatus.SUCCEEDED
            ):
                document = (
                    self.document_repository
                    .get_document(job.document_id)
                )
                if document is not None:
                    self.conversation_repository\
                        .increment_knowledge_base_version(
                            document.knowledge_base_id
                        )
            self.session.commit()
            return job
        except Exception:
            self.session.rollback()
            raise

    def delete_document(
        self,
        knowledge_base_id: str,
        document_id: str,
    ) -> Document | None:
        document = self.get_document(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
        )

        if document is None:
            return None

        if (
            document.status
            == DocumentStatus.DELETED
        ):
            return document

        try:
            vector_delete = self.vector_delete

            if vector_delete is None:
                from app.services.vector_stores.vector_store import (
                    delete_by_document,
                )

                vector_delete = delete_by_document

            vector_delete(
                knowledge_base_id,
                document_id,
            )
            document = (
                self.document_repository
                .update_document_status(
                    document_id=document_id,
                    status=(
                        DocumentStatus.DELETED
                    ),
                )
            )
            self.conversation_repository\
                .increment_knowledge_base_version(
                    knowledge_base_id
                )
            self.session.commit()
            return document
        except Exception:
            self.session.rollback()
            raise

    def request_reindex(
        self,
        knowledge_base_id: str,
        document_id: str,
    ) -> tuple[
        Document,
        IngestionJob,
        bool,
    ] | None:
        document = self.get_document(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
        )

        if document is None:
            return None

        if (
            document.status
            == DocumentStatus.DELETED
        ):
            raise DocumentReindexConflictError(
                "Deleted document cannot be "
                "reindexed"
            )

        try:
            latest_job = (
                self.document_repository
                .get_latest_job_by_document_id(
                    document.id
                )
            )

            if (
                latest_job is not None
                and latest_job.status
                in {
                    IngestionJobStatus.PENDING,
                    IngestionJobStatus.RUNNING,
                }
            ):
                return (
                    document,
                    latest_job,
                    False,
                )

            job = (
                self.document_repository
                .create_ingestion_job(
                    document.id
                )
            )
            self.document_repository\
                .update_document_status(
                    document_id=document.id,
                    status=(
                        DocumentStatus.PENDING
                    ),
                )
            self.conversation_repository\
                .increment_knowledge_base_version(
                    knowledge_base_id
                )
            self.session.commit()
            return document, job, True
        except Exception:
            self.session.rollback()
            raise

    def _reuse_or_retry(
        self,
        document: Document,
    ) -> tuple[
        Document,
        IngestionJob,
        bool,
    ]:
        latest_job = (
            self.document_repository
            .get_latest_job_by_document_id(
                document.id
            )
        )

        if (
            latest_job is not None
            and document.status
            not in {
                DocumentStatus.FAILED,
                DocumentStatus.DELETED,
            }
        ):
            return document, latest_job, False

        job = (
            self.document_repository
            .create_ingestion_job(
                document.id
            )
        )
        self.document_repository\
            .update_document_status(
                document_id=document.id,
                status=DocumentStatus.PENDING,
            )
        self.session.commit()
        return document, job, True

    def _resolve_knowledge_base(
        self,
        knowledge_base_id: str | None,
    ):
        if knowledge_base_id is not None:
            knowledge_base = (
                self.conversation_repository
                .get_knowledge_base(
                    knowledge_base_id
                )
            )

            if knowledge_base is None:
                raise KnowledgeBaseNotFoundError(
                    "Knowledge base not found"
                )

            return knowledge_base

        user = (
            self.conversation_repository
            .create_user(
                email=DEFAULT_USER_EMAIL,
                display_name=(
                    "Local Development User"
                ),
            )
        )
        return (
            self.conversation_repository
            .get_or_create_knowledge_base(
                owner_user_id=user.id,
                name=(
                    DEFAULT_KNOWLEDGE_BASE_NAME
                ),
            )
        )
