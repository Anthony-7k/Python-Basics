from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)

from app.api.dependencies import (
    get_document_service,
)
from app.api.authentication import (
    get_current_user,
)
from app.core.rate_limit import request_limiter
from app.core.security import AuthenticatedUser
from app.core.settings import (
    RATE_LIMIT_WINDOW_SECONDS,
    UPLOAD_RATE_LIMIT_REQUESTS,
)
from app.schemas.document import (
    DocumentDeleteResponse,
    DocumentListResponse,
    DocumentReindexResponse,
    DocumentResponse,
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
    get_uploaded_file_path,
    read_validated_file,
    sanitize_file_name,
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
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
):
    request_limiter.check(
        scope="upload",
        actor_id=current_user.audit_id,
        limit=UPLOAD_RATE_LIMIT_REQUESTS,
        window_seconds=(
            RATE_LIMIT_WINDOW_SECONDS
        ),
    )
    try:
        content, suffix = (
            await read_validated_file(file)
        )

        content_hash, file_path = (
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

    original_file_name = sanitize_file_name(
        file.filename or ""
    )

    document, job, created = (
        document_service.create_or_get_upload(
            content_hash=content_hash,
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
    knowledge_base_id: str = Query(
        ...,
        min_length=1,
    ),
    document_service: DocumentService = Depends(
        get_document_service
    ),
):
    document = (
        document_service.delete_document(
            knowledge_base_id=(
                knowledge_base_id
            ),
            document_id=document_id,
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


@router.get(
    "/knowledge-bases/{knowledge_base_id}/documents",
    response_model=DocumentListResponse,
)
def list_documents(
    knowledge_base_id: str,
    include_deleted: bool = False,
    document_service: DocumentService = Depends(
        get_document_service
    ),
):
    return DocumentListResponse(
        items=(
            document_service.list_documents(
                knowledge_base_id=(
                    knowledge_base_id
                ),
                include_deleted=include_deleted,
            )
        )
    )


@router.get(
    "/knowledge-bases/{knowledge_base_id}/documents/{document_id}",
    response_model=DocumentResponse,
)
def get_document(
    knowledge_base_id: str,
    document_id: str,
    document_service: DocumentService = Depends(
        get_document_service
    ),
):
    document = document_service.get_document(
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return document


@router.post(
    "/knowledge-bases/{knowledge_base_id}/documents/{document_id}/reindex",
    response_model=DocumentReindexResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def reindex_document(
    knowledge_base_id: str,
    document_id: str,
    background_tasks: BackgroundTasks,
    document_service: DocumentService = Depends(
        get_document_service
    ),
):
    document = document_service.get_document(
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    file_path = get_uploaded_file_path(
        content_hash=document.content_hash,
        file_name=document.file_name,
    )

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document source file is missing",
        )

    result = document_service.request_reindex(
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    document, job, created = result

    if created:
        background_tasks.add_task(
            run_ingestion_task,
            job.id,
            str(file_path),
        )

    return DocumentReindexResponse(
        document_id=document.id,
        task_id=job.id,
        status=job.status,
    )
