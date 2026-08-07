from pydantic import BaseModel


class ChunkRecord(BaseModel):
    chunk_id: str

    document_id: str

    content: str

    start_index: int
    end_index: int

    page: int | None = None

    content_hash: str