from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    HTTPException,
    UploadFile,
    status,
)
from app.schemas.document import (
    DocumentUploadResponse,
    IngestionTaskResponse,
)
from app.services.ingestion.ingestion_service import run_ingestion_task
from app.services.ingestion.task_manager import (
    create_task,
    get_task,
    get_task_by_document_id,
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
):
    try:
        content, suffix = await read_validated_file(file)
        document_id, file_path = save_uploaded_file(
            content,
            suffix,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    existing_task = get_task_by_document_id(
        document_id
    )

    if existing_task is not None:
        return DocumentUploadResponse(
            document_id=document_id,
            task_id=existing_task.task_id,
            status=existing_task.status,
        )

    task = create_task(document_id)

    background_tasks.add_task(
        run_ingestion_task,
        task.task_id,
        str(file_path),
    )

    return DocumentUploadResponse(
        document_id=document_id,
        task_id=task.task_id,
        status=task.status,
    )

@router.get(
    "/ingestion/{task_id}",
    response_model=IngestionTaskResponse,
)
def get_ingestion_status(
    task_id: str,
):
    task = get_task(task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingestion task not found",
        )

    return task