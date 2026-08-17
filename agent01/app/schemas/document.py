from app.models import DocumentStatus

from pydantic import BaseModel

from enum import Enum

class DocumentRecord(BaseModel):
    content: str

    source: str
    file_name: str

    page: int | None = None

    document_id: str

    content_hash: str

class IngestionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

class DocumentUploadResponse(BaseModel):
    document_id: str
    task_id: str
    status: IngestionStatus

class IngestionTaskResponse(BaseModel):
    task_id: str
    document_id: str
    status: IngestionStatus
    error: str | None = None

class DocumentDeleteResponse(BaseModel):
    document_id: str
    status: DocumentStatus