from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
    )


class RAGSource(BaseModel):
    source_id: str
    chunk_id: str
    file_name: str | None = None
    page: int | None = None
    content: str


class RAGResponse(BaseModel):
    answer: str
    sources: list[RAGSource]
    used_chunk_ids: list[str]
    request_id: str