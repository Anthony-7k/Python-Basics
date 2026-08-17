from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)

from app.api.dependencies import (
    get_document_service,
)
from app.schemas.document import (
    DocumentDeleteResponse,
    DocumentUploadResponse,
    IngestionTaskResponse,
)
from app.services.documents import (
    DocumentService,
)
from app.services.ingestion.ingestion_service import (
    run_ingestion_task,
)
from app.services.ingestion.uploader import (
    read_validated_file,
    save_uploaded_file,
)


router = APIRouter(
    prefix="/api/v1",
    tags=["documents"],
)


@router.post(
    "/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_service: DocumentService = Depends(
        get_document_service
    ),
    knowledge_base_id: str | None = None,
):
    try:
        content, suffix = (
            await read_validated_file(file)
        )

        document_id, file_path = (
            save_uploaded_file(
                content,
                suffix,
            )
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=str(exc),
        ) from exc

    original_file_name = Path(
        file.filename or ""
    ).name

    document, job, created = (
        document_service.create_or_get_upload(
            document_id=document_id,
            file_name=original_file_name,
            knowledge_base_id=(
                knowledge_base_id
            ),
        )
    )

    if created:
        background_tasks.add_task(
            run_ingestion_task,
            job.id,
            str(file_path),
        )

    return DocumentUploadResponse(
        document_id=document.id,
        task_id=job.id,
        status=job.status,
    )


@router.get(
    "/ingestion/{task_id}",
    response_model=IngestionTaskResponse,
)
def get_ingestion_status(
    task_id: str,
    document_service: DocumentService = Depends(
        get_document_service
    ),
):
    job = (
        document_service.get_ingestion_job(
            task_id
        )
    )

    if job is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Ingestion task not found"
            ),
        )

    return IngestionTaskResponse(
        task_id=job.id,
        document_id=job.document_id,
        status=job.status,
        error=job.error,
    )

@router.delete(
    "/documents/{document_id}",
    response_model=DocumentDeleteResponse,
)
def delete_document(
    document_id: str,
    document_service: DocumentService = Depends(
        get_document_service
    ),
):
    document = (
        document_service.delete_document(
            document_id
        )
    )

    if document is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Document not found",
        )

    return DocumentDeleteResponse(
        document_id=document.id,
        status=document.status,
    )