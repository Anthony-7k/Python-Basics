from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Document,
    DocumentStatus,
    IngestionJob,
    IngestionJobStatus,
)


class DocumentRepository:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def get_document(
        self,
        document_id: str,
    ) -> Document | None:
        return self.session.get(
            Document,
            document_id,
        )

    def get_document_for_knowledge_base(
        self,
        document_id: str,
        knowledge_base_id: str,
    ) -> Document | None:
        return self.session.scalar(
            select(Document).where(
                Document.id == document_id,
                Document.knowledge_base_id
                == knowledge_base_id,
            )
        )

    def get_document_by_content_hash(
        self,
        knowledge_base_id: str,
        content_hash: str,
    ) -> Document | None:
        return self.session.scalar(
            select(Document).where(
                Document.knowledge_base_id
                == knowledge_base_id,
                Document.content_hash
                == content_hash
            )
        )

    def list_documents(
        self,
        knowledge_base_id: str,
        include_deleted: bool = False,
    ) -> list[Document]:
        statement = select(Document).where(
            Document.knowledge_base_id
            == knowledge_base_id
        )

        if not include_deleted:
            statement = statement.where(
                Document.status
                != DocumentStatus.DELETED
            )

        statement = statement.order_by(
            Document.created_at.desc(),
            Document.id.desc(),
        )

        return list(
            self.session.scalars(
                statement
            ).all()
        )

    def create_document(
        self,
        document_id: str,
        knowledge_base_id: str,
        file_name: str,
        content_hash: str,
    ) -> Document:
        document = Document(
            id=document_id,
            knowledge_base_id=(
                knowledge_base_id
            ),
            file_name=file_name,
            content_hash=content_hash,
            status=DocumentStatus.PENDING,
        )

        self.session.add(document)
        self.session.flush()

        return document

    def update_document_status(
        self,
        document_id: str,
        status: DocumentStatus,
    ) -> Document | None:
        document = self.get_document(
            document_id
        )

        if document is None:
            return None

        document.status = status
        self.session.flush()

        return document

    def create_ingestion_job(
        self,
        document_id: str,
    ) -> IngestionJob:
        self.session.scalar(
            select(Document)
            .where(
                Document.id == document_id
            )
            .with_for_update()
        )
        latest_attempt = (
            self.session.scalar(
                select(
                    func.max(
                        IngestionJob.attempt_number
                    )
                ).where(
                    IngestionJob.document_id
                    == document_id
                )
            )
            or 0
        )
        job = IngestionJob(
            document_id=document_id,
            attempt_number=(
                latest_attempt + 1
            ),
            status=(
                IngestionJobStatus.PENDING
            ),
        )

        self.session.add(job)
        self.session.flush()

        return job

    def get_ingestion_job(
        self,
        task_id: str,
    ) -> IngestionJob | None:
        return self.session.get(
            IngestionJob,
            task_id,
        )

    def get_latest_job_by_document_id(
        self,
        document_id: str,
    ) -> IngestionJob | None:
        statement = (
            select(IngestionJob)
            .where(
                IngestionJob.document_id
                == document_id
            )
            .order_by(
                IngestionJob.attempt_number.desc(),
            )
            .limit(1)
        )

        return self.session.scalar(
            statement
        )

    def update_ingestion_job(
        self,
        task_id: str,
        status: IngestionJobStatus,
        error: str | None = None,
    ) -> IngestionJob | None:
        job = self.get_ingestion_job(
            task_id
        )

        if job is None:
            return None

        job.status = status
        job.error = error

        self.session.flush()

        return job
