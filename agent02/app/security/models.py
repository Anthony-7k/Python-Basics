from __future__ import annotations

from pydantic import BaseModel, Field


class UserContext(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    tenant_id: str = Field(min_length=1, max_length=100)
    roles: frozenset[str] = Field(default_factory=frozenset)
    token_id: str | None = Field(default=None, max_length=200)
