from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)


class ToolName(str, Enum):
    SEARCH_KNOWLEDGE = "search_knowledge"
    SUMMARIZE_DOCUMENT = "summarize_document"
    COMPARE_DOCUMENTS = "compare_documents"


class ToolStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AgentStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


class SearchKnowledgeArguments(BaseModel):
    knowledge_base_id: str = Field(
        min_length=1,
        max_length=100,
    )
    query: str = Field(
        min_length=1,
        max_length=2000,
    )
    top_k: int = Field(default=5, ge=1, le=10)


class SummarizeDocumentArguments(BaseModel):
    knowledge_base_id: str = Field(
        min_length=1,
        max_length=100,
    )
    document_id: str = Field(
        min_length=1,
        max_length=100,
    )
    instruction: str = Field(
        min_length=1,
        max_length=2000,
    )


class CompareDocumentsArguments(BaseModel):
    knowledge_base_id: str = Field(
        min_length=1,
        max_length=100,
    )
    left_document_id: str = Field(
        min_length=1,
        max_length=100,
    )
    right_document_id: str = Field(
        min_length=1,
        max_length=100,
    )
    instruction: str = Field(
        min_length=1,
        max_length=2000,
    )

    @model_validator(mode="after")
    def require_distinct_documents(self):
        if self.left_document_id == self.right_document_id:
            raise ValueError(
                "comparison requires two different documents"
            )
        return self


class ToolCall(BaseModel):
    call_id: str = Field(
        default_factory=lambda: str(uuid4()),
        min_length=1,
        max_length=100,
    )
    tool_name: ToolName
    selection_reason: str = Field(
        min_length=1,
        max_length=200,
    )
    arguments: dict[str, Any]


class ToolError(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)
    retryable: bool = False


class ToolResult(BaseModel):
    call_id: str
    tool_name: ToolName
    status: ToolStatus
    duration_ms: float = Field(ge=0)
    result_summary: str = Field(
        min_length=1,
        max_length=300,
    )
    output: dict[str, Any] | None = None
    error: ToolError | None = None

    @model_validator(mode="after")
    def validate_result_shape(self):
        if self.status == ToolStatus.SUCCEEDED:
            if self.output is None or self.error is not None:
                raise ValueError(
                    "successful tool results require output only"
                )
        elif self.error is None or self.output is not None:
            raise ValueError(
                "failed tool results require error only"
            )
        return self


class AgentRequest(BaseModel):
    knowledge_base_id: str = Field(
        min_length=1,
        max_length=100,
    )
    instruction: str = Field(
        min_length=1,
        max_length=2000,
    )
    document_ids: list[str] = Field(
        default_factory=list,
        max_length=2,
    )

    @field_validator("instruction")
    @classmethod
    def strip_instruction(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("instruction cannot be blank")
        return stripped

    @field_validator("document_ids")
    @classmethod
    def validate_document_ids(
        cls,
        values: list[str],
    ) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(
            not value or len(value) > 100
            for value in cleaned
        ):
            raise ValueError("document IDs must be 1-100 characters")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("document IDs must be unique")
        return cleaned


class AgentTrace(BaseModel):
    request_id: str
    step_count: int = Field(ge=0)
    stop_reason: str = Field(
        min_length=1,
        max_length=100,
    )
    tool_calls: list[ToolCall] = Field(
        default_factory=list,
    )
    tool_results: list[ToolResult] = Field(
        default_factory=list,
    )


class AgentResponse(BaseModel):
    status: AgentStatus
    answer: str
    trace: AgentTrace
    error: ToolError | None = None
