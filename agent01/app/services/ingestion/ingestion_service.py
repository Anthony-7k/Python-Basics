from pathlib import Path

from app.core.logging_config import get_logger
from app.db.session import SessionLocal
from app.models import (
    IngestionJobStatus,
)
from app.schemas.chunk import ChunkRecord
from app.schemas.document import (
    DocumentRecord,
)
from app.services.chunkers.chunker import (
    split_text,
)
from app.services.cleaners.text_cleaner import (
    clean_text,
)
from app.services.documents import (
    DocumentService,
)
from app.services.loaders.docx_loader import (
    load_docx,
)
from app.services.loaders.pdf_loader import (
    load_pdf,
)
from app.services.loaders.txt_loader import (
    load_txt,
)
from app.services.vector_stores.vector_store import (
    delete_by_document,
    upsert_chunks,
)


logger = get_logger(__name__)


def load_documents(
    file_path: str,
) -> list[DocumentRecord]:
    suffix = Path(
        file_path
    ).suffix.lower()

    if suffix == ".txt":
        return [
            load_txt(file_path)
        ]

    if suffix == ".pdf":
        return load_pdf(file_path)

    if suffix == ".docx":
        return load_docx(file_path)

    raise ValueError(
        f"Unsupported file type: {suffix}"
    )


def build_chunks(
    file_path: str,
    document_id: str,
    knowledge_base_id: str,
    display_file_name: str | None = None,
) -> list[ChunkRecord]:
    documents = load_documents(
        file_path
    )

    all_chunks = []

    for document in documents:
        cleaned_text = clean_text(
            document.content
        )

        chunks = split_text(
            cleaned_text,
            document_id,
            knowledge_base_id,
            source=(
                display_file_name
                or document.file_name
            ),
            page=document.page,
        )

        all_chunks.extend(chunks)

    return all_chunks


def ingest_file(
    file_path: str,
    document_id: str,
    knowledge_base_id: str,
    display_file_name: str | None = None,
) -> list[ChunkRecord]:
    chunks = build_chunks(
        file_path,
        document_id=document_id,
        knowledge_base_id=(
            knowledge_base_id
        ),
        display_file_name=display_file_name,
    )

    delete_by_document(
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
    )
    upsert_chunks(chunks)

    return chunks


def run_ingestion_task(
    task_id: str,
    file_path: str,
) -> None:
    db = SessionLocal()

    try:
        service = DocumentService(db)

        running_job = (
            service.update_ingestion_status(
                task_id=task_id,
                status=(
                    IngestionJobStatus.RUNNING
                ),
            )
        )

        if running_job is None:
            return

        document = (
            service.document_repository
            .get_document(
                running_job.document_id
            )
        )

        if document is None:
            return

        try:
            ingest_file(
                file_path,
                document_id=document.id,
                knowledge_base_id=(
                    document.knowledge_base_id
                ),
                display_file_name=(
                    document.file_name
                ),
            )

        except Exception:
            service.update_ingestion_status(
                task_id=task_id,
                status=(
                    IngestionJobStatus.FAILED
                ),
                error="Document ingestion failed",
            )

            logger.error(
                "document ingestion failed",
                extra={
                    "event": "ingestion_error",
                    "document_id": document.id,
                    "knowledge_base_id": (
                        document.knowledge_base_id
                    ),
                    "error_code": (
                        "document_ingestion_failed"
                    ),
                },
            )

            return

        service.update_ingestion_status(
            task_id=task_id,
            status=(
                IngestionJobStatus.SUCCEEDED
            ),
        )

    finally:
        db.close()
