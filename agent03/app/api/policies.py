from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import get_principal, get_session, require_roles
from app.api.schemas import PolicySearchResponse, PolicyView
from app.domain import Role
from app.rag import PolicyRetrievalService, PolicyService
from app.security.tokens import Principal
from app.services import InvalidInput

router = APIRouter(tags=["policies"])


def _view(policy) -> dict:
    return {
        "id": policy.id,
        "title": policy.title,
        "version": policy.version,
        "status": policy.status,
        "effective_on": policy.effective_on,
        "expires_on": policy.expires_on,
        "original_name": policy.original_name,
        "content_hash": policy.content_hash,
        "chunk_count": len(policy.chunks),
        "created_at": policy.created_at,
    }


@router.post("/policies", response_model=PolicyView, status_code=201)
def upload_policy(
    request: Request,
    file: UploadFile,
    title: str = Form(min_length=1, max_length=300),
    version: str = Form(min_length=1, max_length=100),
    effective_on: date = Form(),
    expires_on: date | None = Form(default=None),
    principal: Principal = Depends(require_roles(Role.TENANT_ADMIN)),
    session: Session = Depends(get_session),
):
    suffix = Path(file.filename or "policy").suffix
    total = 0
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as target:
        temp_path = Path(target.name)
        while chunk := file.file.read(1024 * 1024):
            total += len(chunk)
            if total > request.app.state.settings.max_upload_bytes:
                target.close()
                temp_path.unlink(missing_ok=True)
                raise InvalidInput("file exceeds the 25 MB upload limit")
            target.write(chunk)
    try:
        policy = PolicyService(
            session,
            principal.tenant_id,
            principal.user_id,
            request.app.state.providers,
        ).upload(
            temp_path,
            file.filename or "policy",
            file.content_type or "application/octet-stream",
            title,
            version,
            effective_on,
            expires_on,
            request.app.state.settings.max_upload_bytes,
            request.state.trace_id,
        )
        return _view(policy)
    finally:
        temp_path.unlink(missing_ok=True)


@router.get("/policies", response_model=list[PolicyView])
def list_policies(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return [_view(policy) for policy in PolicyService(session, principal.tenant_id, principal.user_id, None).list()]


@router.get("/policies/search", response_model=PolicySearchResponse)
def search_policies(
    q: str = Query(min_length=2, max_length=500),
    as_of: date | None = None,
    limit: int = Query(default=3, ge=1, le=10),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    target_date = as_of or date.today()
    citations = PolicyRetrievalService(session, principal.tenant_id).search(
        q, as_of=target_date, limit=limit
    )
    return {
        "query": q,
        "as_of": target_date,
        "citations": [citation.as_dict() for citation in citations],
    }
