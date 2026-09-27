from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, TypedDict
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class TaskStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING_TOOL = "WAITING_TOOL"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class RiskLevel(StrEnum):
    READ_ONLY = "READ_ONLY"
    LOW_RISK = "LOW_RISK"
    HIGH_RISK = "HIGH_RISK"


class TokenUsage(BaseModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)

    @property
    def total_tokens(self) -> int | None:
        if self.input_tokens is None or self.output_tokens is None:
            return None
        return self.input_tokens + self.output_tokens


class ToolCall(BaseModel):
    call_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(min_length=1, max_length=100)
    arguments: dict[str, Any] = Field(default_factory=dict)
    selection_reason: str = ""


class ToolError(BaseModel):
    error_type: str
    message: str
    retryable: bool = False


class ToolResult(BaseModel):
    call_id: str
    tool_name: str
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    error: ToolError | None = None
    latency_ms: float = Field(default=0.0, ge=0)
    retry_count: int = Field(default=0, ge=0)


class KnowledgeSource(BaseModel):
    """Normalized, display-safe citation returned by every knowledge backend."""

    source_id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    source_type: str = Field(default="document", min_length=1, max_length=100)
    locator: str | None = Field(default=None, max_length=500)
    score: float | None = Field(default=None, ge=0, le=1)
    url: str | None = Field(default=None, max_length=2000)
    content: str = Field(default="", max_length=8000)
    untrusted: bool = True


class AgentRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    user_id: str = Field(min_length=1, max_length=100)
    session_id: str = Field(min_length=1, max_length=100)
    knowledge_base_id: str | None = Field(default=None, max_length=100)
    max_steps: int | None = Field(default=None, ge=1, le=50)

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be blank")
        return value


class AgentV2Request(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str = Field(
        default_factory=lambda: str(uuid4()), min_length=1, max_length=100
    )
    knowledge_base_id: str | None = Field(default=None, max_length=100)
    max_steps: int | None = Field(default=None, ge=1, le=50)

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be blank")
        return value


class DevTokenRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    tenant_id: str = Field(min_length=1, max_length=100)
    roles: list[str] = Field(default_factory=lambda: ["operator"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class ApprovalV2Request(BaseModel):
    modified_payload: dict[str, Any] | None = None


class RejectV2Request(BaseModel):
    reason: str = Field(default="Rejected by approver", max_length=500)


class ApprovalRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    modified_payload: dict[str, Any] | None = None


class RejectRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    reason: str = Field(default="Rejected by user", max_length=500)


class ResumeRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)


class AgentResponse(BaseModel):
    request_id: str
    task_id: str
    session_id: str
    status: TaskStatus
    answer: str = ""
    sources: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    current_step: int = 0
    max_steps: int = 10
    error: ToolError | None = None
    token_usage: TokenUsage = Field(default_factory=TokenUsage)


class TaskView(AgentResponse):
    user_id: str
    created_at: datetime
    updated_at: datetime


class AuditEventView(BaseModel):
    id: str
    tenant_id: str
    actor: str
    action: str
    resource_type: str
    resource_id: str | None
    outcome: str
    request_id: str
    created_at: datetime


class WorkflowState(TypedDict, total=False):
    messages: list[dict[str, str]]
    user_id: str
    tenant_id: str
    session_id: str
    task_id: str
    request_id: str
    knowledge_base_id: str | None
    current_step: int
    max_steps: int
    planned_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    status: str
    error: dict[str, Any] | None
    token_usage: dict[str, int | None]
    pending_call: dict[str, Any] | None
    approved_call_id: str | None
    resume_approved: bool
    resume_from_checkpoint: bool
    next_action: str
    answer: str
    sources: list[dict[str, Any]]
