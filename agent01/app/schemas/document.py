from pydantic import BaseModel


class DocumentRecord(BaseModel):
    content: str

    source: str
    file_name: str

    page: int | None = None

    document_id: str

    content_hash: str