from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    knowledge_base_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
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
    conversation_id: str | None = None
    answer: str
    sources: list[RAGSource]
    used_chunk_ids: list[str]
    request_id: str
    latency_ms: float = Field(
        default=0.0,
        ge=0,
    )