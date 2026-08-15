from uuid import uuid4

from app.schemas.document import IngestionStatus, IngestionTaskResponse


_tasks: dict[str, IngestionTaskResponse] = {}

_document_task_ids: dict[str, str] = {}

def create_task(document_id: str) -> IngestionTaskResponse:
    task = IngestionTaskResponse(
        task_id=str(uuid4()),
        document_id=document_id,
        status=IngestionStatus.PENDING,
    )

    _tasks[task.task_id] = task
    _document_task_ids[document_id] = task.task_id
    return task

def get_task(task_id: str) -> IngestionTaskResponse | None:
    return _tasks.get(task_id)

def update_task_status(
    task_id: str,
    status: IngestionStatus,
    error: str | None = None,
) -> IngestionTaskResponse | None:
    task = get_task(task_id)

    if task is None:
        return None

    task.status = status
    task.error = error
    return task

def get_task_by_document_id(
    document_id: str,
) -> IngestionTaskResponse | None:
    task_id = _document_task_ids.get(document_id)

    if task_id is None:
        return None

    return get_task(task_id)