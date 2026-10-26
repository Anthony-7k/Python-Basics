from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pymupdf

from app.domain import DocumentKind, ScanStatus
from app.providers.base import ProcessedDocument, RenderedReport, StoredObject


class FilesystemObjectStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _target(self, key: str) -> Path:
        target = (self.root / key).resolve()
        if self.root not in target.parents:
            raise ValueError("invalid object key")
        return target

    def put(self, source: Path, key: str) -> StoredObject:
        target = self._target(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        return StoredObject(key=key, size_bytes=target.stat().st_size)

    def get_to(self, key: str, target: Path) -> None:
        source = self._target(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    def delete(self, key: str) -> None:
        target = self._target(key)
        target.unlink(missing_ok=True)


class FakeVirusScanner:
    def scan(self, path: Path) -> ScanStatus:
        prefix = path.read_bytes()[:64]
        return ScanStatus.INFECTED if b"EICAR" in prefix else ScanStatus.CLEAN


class FakeDocumentProcessor:
    def classify(self, document_id: str, kind: DocumentKind) -> ProcessedDocument:
        labels = {
            DocumentKind.PDF: "contract",
            DocumentKind.DOCX: "contract",
            DocumentKind.PNG: "invoice",
            DocumentKind.JPEG: "purchase_order",
        }
        return ProcessedDocument(
            document_id=document_id,
            classification=labels[kind],
            confidence=0.99,
        )


class PyMuPDFReportRenderer:
    """Render the immutable, escaped HTML snapshot into a paginated PDF artifact."""

    def render(self, html_content: str) -> RenderedReport:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as target:
            output_path = Path(target.name)
        writer = pymupdf.DocumentWriter(str(output_path))
        try:
            story = pymupdf.Story(html=html_content)
            media_box = pymupdf.paper_rect("a4")
            content_box = media_box + (42, 42, -42, -42)
            more = True
            while more:
                device = writer.begin_page(media_box)
                more, _ = story.place(content_box)
                story.draw(device)
                writer.end_page()
            writer.close()
            writer = None
            with pymupdf.open(output_path) as document:
                document.set_metadata(
                    {
                        "title": "DocFlow AI Review Report",
                        "author": "DocFlow AI",
                        "creator": "DocFlow AI PyMuPDF Provider",
                    }
                )
                for page_number, page in enumerate(document, start=1):
                    footer = f"DocFlow AI | Page {page_number} of {document.page_count}"
                    page.insert_textbox(
                        pymupdf.Rect(42, media_box.height - 28, media_box.width - 42, media_box.height - 14),
                        footer,
                        fontname="helv",
                        fontsize=8,
                        color=(0.36, 0.45, 0.52),
                        align=pymupdf.TEXT_ALIGN_RIGHT,
                    )
                document.saveIncr()
            payload = output_path.read_bytes()
        finally:
            if writer is not None:
                writer.close()
            output_path.unlink(missing_ok=True)
        if not payload.startswith(b"%PDF-"):
            raise RuntimeError("report renderer did not produce a PDF")
        return RenderedReport(
            payload=payload,
            content_type="application/pdf",
            extension="pdf",
        )


class DeferredTaskQueue:
    """Application service invokes eager work after committing the API transaction."""

    def enqueue(self, job_id: str) -> None:
        return None

    def enqueue_report(self, report_id: str) -> None:
        return None


class CeleryTaskQueue:
    def __init__(self, broker_url: str, result_backend: str):
        from celery import Celery

        self.client = Celery("docflow-client", broker=broker_url, backend=result_backend)

    def enqueue(self, job_id: str) -> None:
        self.client.send_task("docflow.process_job", args=[job_id])

    def enqueue_report(self, report_id: str) -> None:
        self.client.send_task("docflow.generate_report", args=[report_id])

