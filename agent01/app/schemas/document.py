from datetime import datetime
from enum import Enum

from pydantic import (
    BaseModel,
    ConfigDict,
)

from app.models import DocumentStatus

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


class DocumentResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: str
    knowledge_base_id: str
    file_name: str
    content_hash: str
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]


class DocumentReindexResponse(BaseModel):
    document_id: str
    task_id: str
    status: IngestionStatus
