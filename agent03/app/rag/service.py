from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database import AuditLog, PolicyChunk, PolicyDocument
from app.document_ai.parsers import ParsedPage, parse_document
from app.domain import DocumentKind, ScanStatus
from app.providers import ProviderBundle


@dataclass(frozen=True)
class PolicyCitation:
    policy_id: str
    policy_title: str
    policy_version: str
    chunk_id: str
    page_number: int
    excerpt: str
    score: float
    effective_on: str

    def as_dict(self) -> dict:
        return self.__dict__.copy()


class PolicyService:
    def __init__(
        self,
        session: Session,
        tenant_id: str,
        actor_id: str,
        providers: ProviderBundle | None,
    ):
        self.session = session
        self.tenant_id = tenant_id
        self.actor_id = actor_id
        self.providers = providers

    def upload(
        self,
        path: Path,
        original_name: str,
        content_type: str,
        title: str,
        version: str,
        effective_on: date,
        expires_on: date | None,
        max_bytes: int,
        trace_id: str,
    ) -> PolicyDocument:
        from app.services.errors import Conflict, InvalidInput
        from app.services.uploads import inspect_upload

        if self.providers is None:
            raise RuntimeError("providers are required for policy upload")
        if expires_on is not None and expires_on < effective_on:
            raise InvalidInput("policy expiry cannot be earlier than its effective date")
        inspected = inspect_upload(path, original_name, content_type, max_bytes)
        if inspected.kind not in {DocumentKind.PDF, DocumentKind.DOCX}:
            raise InvalidInput("policies must be PDF or DOCX files")
        if self.providers.scanner.scan(path) != ScanStatus.CLEAN:
            raise InvalidInput("policy upload was rejected by the virus scanner")
        pages = parse_document(path, inspected.kind, original_name, self.providers.ocr)
        chunks = _chunk_pages(pages)
        if not chunks:
            raise InvalidInput("policy contains no searchable text")
        policy_id = str(uuid4())
        object_key = f"{self.tenant_id}/policies/{policy_id}.{inspected.kind.value}"
        self.providers.storage.put(path, object_key)
        policy = PolicyDocument(
            id=policy_id,
            tenant_id=self.tenant_id,
            title=title.strip(),
            version=version.strip(),
            effective_on=effective_on,
            expires_on=expires_on,
            original_name=Path(original_name).name[:500],
            object_key=object_key,
            content_hash=inspected.sha256,
            created_by=self.actor_id,
        )
        self.session.add(policy)
        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            self.providers.storage.delete(object_key)
            raise Conflict("policy version or content already exists") from exc
        for index, (page_number, heading, text) in enumerate(chunks):
            self.session.add(
                PolicyChunk(
                    tenant_id=self.tenant_id,
                    policy_document_id=policy.id,
                    chunk_index=index,
                    page_number=page_number,
                    heading=heading,
                    text=text,
                    text_hash=hashlib.sha256(text.encode()).hexdigest(),
                )
            )
        self.session.add(
            AuditLog(
                tenant_id=self.tenant_id,
                actor_id=self.actor_id,
                action="policy.upload",
                resource_type="policy_document",
                resource_id=policy.id,
                outcome="success",
                trace_id=trace_id,
                after={"title": policy.title, "version": policy.version, "chunks": len(chunks)},
            )
        )
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            self.providers.storage.delete(object_key)
            raise Conflict("policy version or content already exists") from exc
        return policy

    def list(self) -> list[PolicyDocument]:
        return list(
            self.session.scalars(
                select(PolicyDocument)
                .where(PolicyDocument.tenant_id == self.tenant_id)
                .options(selectinload(PolicyDocument.chunks))
                .order_by(PolicyDocument.effective_on.desc(), PolicyDocument.created_at.desc())
            )
        )


class PolicyRetrievalService:
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    def search(self, query: str, *, as_of: date | None = None, limit: int = 3) -> list[PolicyCitation]:
        target_date = as_of or date.today()
        policies = list(
            self.session.scalars(
                select(PolicyDocument)
                .where(
                    PolicyDocument.tenant_id == self.tenant_id,
                    PolicyDocument.status == "ACTIVE",
                    PolicyDocument.effective_on <= target_date,
                    or_(PolicyDocument.expires_on.is_(None), PolicyDocument.expires_on >= target_date),
                )
                .options(selectinload(PolicyDocument.chunks))
                .order_by(PolicyDocument.title, PolicyDocument.effective_on.desc(), PolicyDocument.created_at.desc())
            )
        )
        latest: dict[str, PolicyDocument] = {}
        for policy in policies:
            latest.setdefault(policy.title, policy)
        ranked = []
        for policy in latest.values():
            for chunk in policy.chunks:
                score = _hybrid_score(query, f"{chunk.heading}\n{chunk.text}")
                if score > 0:
                    ranked.append((score, policy, chunk))
        ranked.sort(key=lambda item: (-item[0], item[1].title, item[2].chunk_index))
        return [
            PolicyCitation(
                policy_id=policy.id,
                policy_title=policy.title,
                policy_version=policy.version,
                chunk_id=chunk.id,
                page_number=chunk.page_number,
                excerpt=chunk.text[:500],
                score=round(score, 4),
                effective_on=policy.effective_on.isoformat(),
            )
            for score, policy, chunk in ranked[: max(1, min(limit, 10))]
        ]


def _chunk_pages(pages: list[ParsedPage], max_chars: int = 900) -> list[tuple[int, str, str]]:
    chunks = []
    for page in pages:
        current: list[str] = []
        size = 0
        heading = ""
        for block in page.blocks:
            text = block.text.strip()
            if not text:
                continue
            if not heading and len(text) <= 80:
                heading = text
            if current and size + len(text) + 1 > max_chars:
                chunks.append((page.page_number, heading, "\n".join(current)))
                current = []
                size = 0
            current.append(text)
            size += len(text) + 1
        if current:
            chunks.append((page.page_number, heading, "\n".join(current)))
    return chunks


def _tokens(value: str) -> list[str]:
    lowered = value.lower()
    words = re.findall(r"[a-z0-9_]+", lowered)
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", lowered))
    words.extend(chinese[index : index + 2] for index in range(max(0, len(chinese) - 1)))
    return [token for token in words if token]


def _vector(tokens: list[str], dimensions: int = 128) -> list[float]:
    result = [0.0] * dimensions
    for token, count in Counter(tokens).items():
        bucket = int.from_bytes(hashlib.sha256(token.encode()).digest()[:4], "big") % dimensions
        result[bucket] += 1.0 + math.log(count)
    length = math.sqrt(sum(value * value for value in result)) or 1.0
    return [value / length for value in result]


def _hybrid_score(query: str, text: str) -> float:
    query_tokens = _tokens(query)
    text_tokens = _tokens(text)
    if not query_tokens or not text_tokens:
        return 0.0
    query_set = set(query_tokens)
    text_set = set(text_tokens)
    sparse = len(query_set & text_set) / math.sqrt(len(query_set) * len(text_set))
    query_vector = _vector(query_tokens)
    text_vector = _vector(text_tokens)
    dense = sum(left * right for left, right in zip(query_vector, text_vector, strict=True))
    return 0.65 * sparse + 0.35 * max(0.0, dense)
