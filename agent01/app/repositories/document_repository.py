from sqlalchemy import select
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

    def get_document_by_content_hash(
        self,
        content_hash: str,
    ) -> Document | None:
        return self.session.scalar(
            select(Document).where(
                Document.content_hash
                == content_hash
            )
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
        job = IngestionJob(
            document_id=document_id,
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
                IngestionJob.created_at.desc(),
                IngestionJob.id.desc(),
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