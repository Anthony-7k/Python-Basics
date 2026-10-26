from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.domain import DocumentKind, ScanStatus


@dataclass(frozen=True)
class StoredObject:
    key: str
    size_bytes: int


@dataclass(frozen=True)
class ProcessedDocument:
    document_id: str
    classification: str
    confidence: float


class ObjectStorage(Protocol):
    def put(self, source: Path, key: str) -> StoredObject: ...
    def get_to(self, key: str, target: Path) -> None: ...
    def delete(self, key: str) -> None: ...


class VirusScanner(Protocol):
    def scan(self, path: Path) -> ScanStatus: ...


class DocumentProcessor(Protocol):
    def classify(self, document_id: str, kind: DocumentKind) -> ProcessedDocument: ...


@dataclass(frozen=True)
class RenderedReport:
    payload: bytes
    content_type: str
    extension: str


class ReportRenderer(Protocol):
    def render(self, html_content: str) -> RenderedReport: ...


class TaskQueue(Protocol):
    def enqueue(self, job_id: str) -> None: ...
    def enqueue_report(self, report_id: str) -> None: ...

