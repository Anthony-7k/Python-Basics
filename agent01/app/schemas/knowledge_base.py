from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=255,
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
    )


class KnowledgeBaseResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseListResponse(BaseModel):
    items: list[KnowledgeBaseResponse]
