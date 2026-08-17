from collections.abc import Callable

from pathlib import Path

from sqlalchemy.orm import Session

from app.core.exceptions import (
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


class DocumentService:
    def __init__(
            self,
            session: Session,
            vector_delete: Callable[[str], None] | None = None,
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
        document_id: str,
        file_name: str,
        knowledge_base_id: str | None = None,
    ) -> tuple[
        Document,
        IngestionJob,
        bool,
    ]:
        try:
            existing_document = (
                self.document_repository
                .get_document_by_content_hash(
                    document_id
                )
            )

            if existing_document is not None:
                existing_job = (
                    self.document_repository
                    .get_latest_job_by_document_id(
                        existing_document.id
                    )
                )

                if existing_job is None:
                    existing_job = (
                        self.document_repository
                        .create_ingestion_job(
                            existing_document.id
                        )
                    )

                    self.session.commit()

                return (
                    existing_document,
                    existing_job,
                    False,
                )

            knowledge_base = (
                self._resolve_knowledge_base(
                    knowledge_base_id
                )
            )

            safe_file_name = Path(
                file_name
            ).name

            document = (
                self.document_repository
                .create_document(
                    document_id=document_id,
                    knowledge_base_id=(
                        knowledge_base.id
                    ),
                    file_name=safe_file_name,
                    content_hash=document_id,
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
                self.document_repository\
                    .update_document_status(
                        document_id=(
                            job.document_id
                        ),
                        status=(
                            DocumentStatus.READY
                        ),
                    )

            elif (
                status
                == IngestionJobStatus.FAILED
            ):
                self.document_repository\
                    .update_document_status(
                        document_id=(
                            job.document_id
                        ),
                        status=(
                            DocumentStatus.FAILED
                        ),
                    )

            self.session.commit()

            return job

        except Exception:
            self.session.rollback()
            raise


    def delete_document(
        self,
        document_id: str,
    ) -> Document | None:
        document = (
            self.document_repository
            .get_document(document_id)
        )

        if document is None:
            return None

        if document.status == DocumentStatus.DELETED:
            return document

        try:
            vector_delete = self.vector_delete

            if vector_delete is None:
                from app.services.vector_stores.vector_store import (
                    delete_by_document,
                )

                vector_delete = delete_by_document

            # 先删除 Chroma 向量
            vector_delete(document_id)

            # 再把 MySQL 文档标记为已删除
            document = (
                self.document_repository
                .update_document_status(
                    document_id=document_id,
                    status=DocumentStatus.DELETED,
                )
            )

            self.session.commit()

            return document

        except Exception:
            self.session.rollback()
            raise


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
                raise (
                    KnowledgeBaseNotFoundError(
                        "Knowledge base not found"
                    )
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