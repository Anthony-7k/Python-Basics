from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.document_ai.parsers import OCRProvider
    from app.providers.model_extraction import OllamaExtractor

from app.config import Settings
from app.providers.base import (
    DocumentProcessor,
    ObjectStorage,
    ReportRenderer,
    TaskQueue,
    VirusScanner,
)
from app.providers.local import (
    CeleryTaskQueue,
    DeferredTaskQueue,
    FakeDocumentProcessor,
    FakeVirusScanner,
    FilesystemObjectStorage,
    PyMuPDFReportRenderer,
)


@dataclass(frozen=True)
class ProviderBundle:
    storage: ObjectStorage
    scanner: VirusScanner
    processor: DocumentProcessor
    report_renderer: ReportRenderer
    queue: TaskQueue
    ocr: OCRProvider | None = None
    extractor: OllamaExtractor | None = None


def build_providers(settings: Settings) -> ProviderBundle:
    settings.validate_runtime()
    ocr = None
    extractor = None
    if settings.ocr_backend == "rapidocr":
        from app.providers.ocr import RapidOCRProvider

        ocr = RapidOCRProvider()
    if settings.extraction_backend == "ollama":
        from app.providers.model_extraction import OllamaExtractor

        extractor = OllamaExtractor(settings.ollama_base_url, settings.ollama_model,
                                    settings.model_timeout_seconds, settings.model_retries)
    if settings.extraction_backend == "cloud":
        from app.providers.model_extraction import OllamaExtractor

        extractor = OllamaExtractor(settings.cloud_model_base_url, settings.cloud_model_name,
                                    settings.model_timeout_seconds, settings.model_retries,
                                    api_key=settings.cloud_model_api_key.get_secret_value(),
                                    cloud_provider=settings.cloud_model_provider)
    if settings.object_storage_backend == "filesystem":
        storage: ObjectStorage = FilesystemObjectStorage(settings.object_storage_path)
    elif settings.object_storage_backend == "s3":
        from app.providers.s3 import S3ObjectStorage

        storage = S3ObjectStorage(
            settings.s3_endpoint,
            settings.s3_bucket,
            settings.s3_access_key,
            settings.s3_secret_key,
        )
    else:
        raise ValueError(f"unsupported storage backend: {settings.object_storage_backend}")
    if settings.virus_scanner_backend != "fake":
        raise ValueError("configured virus scanner adapter is not installed")
    if settings.report_renderer_backend != "pymupdf":
        raise ValueError("unsupported report renderer backend")
    if settings.task_queue_backend not in {"eager", "celery"}:
        raise ValueError("unsupported task queue backend")
    queue: TaskQueue
    if settings.task_queue_backend == "celery":
        queue = CeleryTaskQueue(settings.celery_broker_url, settings.celery_result_backend)
    else:
        queue = DeferredTaskQueue()
    return ProviderBundle(
        storage=storage,
        scanner=FakeVirusScanner(),
        processor=FakeDocumentProcessor(),
        report_renderer=PyMuPDFReportRenderer(),
        queue=queue,
        ocr=ocr,
        extractor=extractor,
    )


