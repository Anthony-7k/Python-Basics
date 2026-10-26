from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from time import perf_counter

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.database import (
    Document,
    DocumentPage,
    EvidenceRef,
    ExtractionRun,
    FieldValue,
    utc_now,
)
from app.document_ai.extractors import classify_document, extract_fields
from app.document_ai.parsers import parse_document
from app.domain import DocumentKind
from app.providers import ProviderBundle


class DocumentIntelligenceService:
    def __init__(self, session: Session, tenant_id: str, providers: ProviderBundle):
        self.session = session
        self.tenant_id = tenant_id
        self.providers = providers

    def process(self, document: Document) -> dict:
        started = perf_counter()
        if document.tenant_id != self.tenant_id:
            raise ValueError("document does not belong to the active tenant")
        run = ExtractionRun(tenant_id=self.tenant_id, document_id=document.id)
        self.session.add(run)
        self.session.flush()
        with tempfile.TemporaryDirectory(prefix="docflow-parse-") as temp_dir:
            local_path = Path(temp_dir) / f"input.{document.kind}"
            self.providers.storage.get_to(document.object_key, local_path)
            pages = parse_document(local_path, DocumentKind(document.kind), document.original_name,
                                   self.providers.ocr)
        full_text = "\n".join(page.text for page in pages)
        classification, confidence = classify_document(full_text, document.original_name)
        if classification == "unknown" and self.providers.ocr is None and self.providers.extractor is None:
            fallback = self.providers.processor.classify(document.id, DocumentKind(document.kind))
            classification, confidence = fallback.classification, 0.55

        candidates = extract_fields(classification, pages)
        metadata = {"provider": "deterministic", "model": None, "cost": None}
        if self.providers.extractor is not None:
            extraction = self.providers.extractor.extract(pages)
            classification, confidence = extraction.classification, 0.85
            candidates, metadata = extraction.fields, extraction.metadata
            run.extractor_version = f"{metadata['provider']}-grounded-v1"
        metadata["page_methods"] = [page.method for page in pages]

        self.session.execute(
            delete(DocumentPage).where(
                DocumentPage.tenant_id == self.tenant_id,
                DocumentPage.document_id == document.id,
            )
        )
        for page in pages:
            self.session.add(
                DocumentPage(
                    tenant_id=self.tenant_id,
                    document_id=document.id,
                    page_number=page.page_number,
                    text=page.text,
                    width=page.width,
                    height=page.height,
                    blocks=[{"text": block.text, "bbox": block.bbox, "confidence": block.confidence}
                            for block in page.blocks],
                )
            )

        for candidate in candidates:
            evidence = EvidenceRef(
                tenant_id=self.tenant_id,
                document_id=document.id,
                page_number=candidate.page_number,
                bbox=candidate.bbox,
                text_hash=hashlib.sha256(candidate.snippet.encode()).hexdigest(),
                snippet=candidate.snippet,
            )
            self.session.add(evidence)
            self.session.flush()
            self.session.add(
                FieldValue(
                    tenant_id=self.tenant_id,
                    document_id=document.id,
                    extraction_run_id=run.id,
                    evidence_id=evidence.id,
                    field_name=candidate.field_name,
                    raw_value=candidate.raw_value,
                    normalized_value=candidate.normalized_value,
                    confidence=candidate.confidence,
                    source="MODEL" if self.providers.extractor else "EXTRACTED",
                )
            )

        document.parse_status = "COMPLETED"
        document.classification = classification
        document.classification_confidence = confidence
        document.page_count = len(pages)
        run.status = "COMPLETED"
        run.classification = classification
        run.classification_confidence = confidence
        run.completed_at = utc_now()
        metadata["total_latency_ms"] = round((perf_counter() - started) * 1000, 2)
        run.processing_metadata = metadata
        self.session.flush()
        return {
            "document_id": document.id,
            "classification": classification,
            "confidence": confidence,
            "page_count": len(pages),
            "field_count": len(candidates),
            "extraction_run_id": run.id,
        }

