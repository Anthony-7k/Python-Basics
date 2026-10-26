from enum import StrEnum


class Role(StrEnum):
    SUBMITTER = "submitter"
    REVIEWER = "reviewer"
    APPROVER = "approver"
    TENANT_ADMIN = "tenant_admin"


class CaseStatus(StrEnum):
    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    REVIEW_READY = "REVIEW_READY"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ScanStatus(StrEnum):
    CLEAN = "CLEAN"
    INFECTED = "INFECTED"
    UNAVAILABLE = "UNAVAILABLE"


class DocumentKind(StrEnum):
    PDF = "pdf"
    PNG = "png"
    JPEG = "jpeg"
    DOCX = "docx"

