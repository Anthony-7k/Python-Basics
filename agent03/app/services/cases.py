from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import AuditLog, Document, ReviewCase
from app.domain import CaseStatus, ScanStatus
from app.providers import ProviderBundle
from app.repositories import TenantRepository
from app.services.errors import Conflict, InvalidInput
from app.services.uploads import inspect_upload


class CaseService:
    def __init__(self, session: Session, tenant_id: str, actor_id: str, providers: ProviderBundle):
        self.session = session
        self.tenant_id = tenant_id
        self.actor_id = actor_id
        self.providers = providers
        self.repo = TenantRepository(session, tenant_id)

    def create_case(self, title: str, description: str, trace_id: str) -> ReviewCase:
        if not title.strip():
            raise InvalidInput("case title cannot be blank")
        case = ReviewCase(
            tenant_id=self.tenant_id,
            title=title.strip(),
            description=description.strip(),
            owner_id=self.actor_id,
        )
        self.session.add(case)
        self.session.flush()
        self._audit("case.create", "case", case.id, "success", trace_id, after={"title": case.title})
        self.session.commit()
        return case

    def add_document(
        self,
        case_id: str,
        temp_path: Path,
        original_name: str,
        content_type: str,
        max_bytes: int,
        trace_id: str,
    ) -> Document:
        case = self.repo.get_case(case_id)
        if CaseStatus(case.status) != CaseStatus.DRAFT:
            raise Conflict("documents can only be added to DRAFT cases")
        inspected = inspect_upload(temp_path, original_name, content_type, max_bytes)
        existing = self.repo.find_document_hash(case.id, inspected.sha256)
        if existing:
            raise Conflict(f"duplicate document: {existing.id}")
        scan_status = self.providers.scanner.scan(temp_path)
        if scan_status != ScanStatus.CLEAN:
            raise InvalidInput(f"upload rejected by virus scanner: {scan_status}")
        document_id = str(uuid4())
        object_key = f"{self.tenant_id}/{case.id}/{document_id}.{inspected.kind.value}"
        self.providers.storage.put(temp_path, object_key)
        document = Document(
            id=document_id,
            tenant_id=self.tenant_id,
            case_id=case.id,
            original_name=Path(original_name).name[:500],
            kind=inspected.kind.value,
            content_type=inspected.content_type,
            size_bytes=inspected.size_bytes,
            sha256=inspected.sha256,
            object_key=object_key,
            scan_status=scan_status.value,
        )
        self.session.add(document)
        self._audit("document.upload", "document", document.id, "success", trace_id)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            self.providers.storage.delete(object_key)
            raise Conflict("duplicate document") from exc
        return document

    def delete_document(self, document_id: str, trace_id: str) -> None:
        document = self.repo.get_document(document_id)
        case = self.repo.get_case(document.case_id)
        if CaseStatus(case.status) != CaseStatus.DRAFT:
            raise Conflict("documents can only be deleted from DRAFT cases")
        self.providers.storage.delete(document.object_key)
        self.session.delete(document)
        self._audit("document.delete", "document", document.id, "success", trace_id)
        self.session.commit()

    def _audit(
        self,
        action: str,
        resource_type: str,
        resource_id: str,
        outcome: str,
        trace_id: str,
        *,
        before: dict | None = None,
        after: dict | None = None,
    ) -> None:
        self.session.add(
            AuditLog(
                tenant_id=self.tenant_id,
                actor_id=self.actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome=outcome,
                trace_id=trace_id,
                before=before,
                after=after,
            )
        )

