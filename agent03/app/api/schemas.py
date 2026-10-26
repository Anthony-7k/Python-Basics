from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)


class TenantChoice(BaseModel):
    id: str
    name: str
    roles: list[str]


class LoginResponse(BaseModel):
    access_token: str | None = None
    selection_token: str | None = None
    token_type: str = "bearer"
    expires_in: int | None = None
    requires_tenant_selection: bool = False
    tenants: list[TenantChoice] = Field(default_factory=list)


class SelectTenantRequest(BaseModel):
    selection_token: str
    tenant_id: str


class UserView(BaseModel):
    user_id: str
    email: str
    display_name: str
    tenant_id: str
    tenant_name: str
    roles: list[str]


class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)


class DocumentView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    original_name: str
    kind: str
    content_type: str
    size_bytes: int
    sha256: str
    scan_status: str
    parse_status: str
    classification: str | None
    classification_confidence: float | None
    page_count: int | None
    created_at: datetime


class EvidenceView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    page_number: int
    bbox: list[float]
    text_hash: str
    snippet: str


class FieldValueView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    field_name: str
    raw_value: str
    normalized_value: str
    confidence: float
    version: int
    source: str
    evidence: EvidenceView


class ExtractionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    document_id: str
    status: str
    extractor_version: str
    schema_version: str
    processing_metadata: dict = Field(default_factory=dict)
    classification: str | None
    classification_confidence: float | None
    created_at: datetime
    completed_at: datetime | None
    fields: list[FieldValueView] = Field(default_factory=list)


class CaseView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    description: str
    status: str
    owner_id: str
    version: int
    created_at: datetime
    updated_at: datetime
    documents: list[DocumentView] = Field(default_factory=list)


class JobView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    case_id: str
    status: str
    stage: str
    progress: int
    trace_id: str
    retry_count: int
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class SubmitResponse(JobView):
    replayed: bool


class JobEventView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sequence: int
    event_type: str
    trace_id: str
    schema_version: str
    payload: dict
    occurred_at: datetime


class PolicyCitationView(BaseModel):
    policy_id: str
    policy_title: str
    policy_version: str
    chunk_id: str
    page_number: int
    excerpt: str
    score: float
    effective_on: str


class RiskView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    risk_type: str
    severity: str
    status: str
    explanation: str
    score: float
    evidence_ids: list[str]
    policy_citations: list[PolicyCitationView]
    version: int
    resolution_reason: str | None
    resolved_by: str | None
    resolved_at: datetime | None
    created_at: datetime


class FieldCorrectionRequest(BaseModel):
    expected_version: int = Field(ge=1)
    normalized_value: str = Field(min_length=1, max_length=10000)
    reason: str = Field(min_length=3, max_length=1000)


class RiskResolutionRequest(BaseModel):
    expected_version: int = Field(ge=1)
    disposition: str = Field(pattern="^(RESOLVED|ACCEPTED)$")
    reason: str = Field(min_length=3, max_length=1000)


class ReviewRunView(BaseModel):
    run_group_id: str
    rules: int
    risks: int


class ComparisonFieldView(BaseModel):
    value: str
    confidence: float
    evidence_id: str


class ComparisonCandidateView(BaseModel):
    document_id: str
    original_name: str
    parse_status: str


class ComparisonColumnView(BaseModel):
    document_type: str
    match_status: Literal["MATCHED", "MISSING", "AMBIGUOUS", "UNAVAILABLE"]
    candidates: list[ComparisonCandidateView]
    document_id: str | None
    original_name: str | None
    fields: dict[str, ComparisonFieldView]


class ComparisonView(BaseModel):
    case_id: str
    columns: list[ComparisonColumnView]


class PolicyView(BaseModel):
    id: str
    title: str
    version: str
    status: str
    effective_on: date
    expires_on: date | None
    original_name: str
    content_hash: str
    chunk_count: int
    created_at: datetime


class PolicySearchResponse(BaseModel):
    query: str
    as_of: date
    citations: list[PolicyCitationView]


class ApprovalRequest(BaseModel):
    expected_version: int = Field(ge=1)
    decision: str = Field(pattern="^(APPROVED|REJECTED)$")
    reason: str = Field(min_length=3, max_length=2000)


class ApprovalView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    case_id: str
    decision: str
    reason: str
    actor_id: str
    case_version: int
    created_at: datetime


class ReportRequest(BaseModel):
    expected_version: int = Field(ge=1)


class ReportView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    case_id: str
    case_version: int
    report_version: int
    status: str
    content_hash: str | None
    content_type: str
    error_message: str | None
    created_at: datetime
    generated_at: datetime | None


class ReportRequestView(ReportView):
    replayed: bool


class WorkbenchPage(BaseModel):
    items: list[CaseView]
    jobs: dict[str, JobView]
    reports: dict[str, ReportView]
    total: int
    offset: int
    limit: int


class AuditLogView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    actor_id: str | None
    action: str
    resource_type: str
    resource_id: str | None
    outcome: str
    trace_id: str
    before: dict | None
    after: dict | None
    created_at: datetime


class AuditPage(BaseModel):
    items: list[AuditLogView]
    total: int
    offset: int
    limit: int


class DashboardPeriod(BaseModel):
    start: date | None
    end: date | None


class DashboardSummary(BaseModel):
    period: DashboardPeriod
    total_cases: int
    status_counts: dict[str, int]
    total_documents: int
    total_jobs: int
    job_success_rate: float
    average_processing_seconds: float
    manual_review_rate: float
    rule_hit_rate: float
    risk_by_severity: dict[str, int]
    risk_by_status: dict[str, int]
    approval_counts: dict[str, int]
    ready_reports: int

