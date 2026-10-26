from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_principal, get_session
from app.api.schemas import (
    LoginRequest,
    LoginResponse,
    SelectTenantRequest,
    TenantChoice,
    UserView,
)
from app.database import Membership, User
from app.security.passwords import verify_password
from app.security.tokens import (
    Principal,
    TokenError,
    create_access_token,
    create_selection_token,
    decode_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _choice(membership: Membership) -> TenantChoice:
    return TenantChoice(
        id=membership.tenant_id,
        name=membership.tenant.name,
        roles=membership.role_list(),
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, session: Session = Depends(get_session)):
    user = session.scalar(
        select(User)
        .where(User.email == payload.email.strip().lower())
        .options(selectinload(User.memberships).selectinload(Membership.tenant))
    )
    if user is None or not user.active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    memberships = user.memberships
    if not memberships:
        raise HTTPException(status_code=403, detail="user has no tenant membership")
    settings = request.app.state.settings
    if len(memberships) == 1:
        membership = memberships[0]
        token = create_access_token(settings, user.id, membership.tenant_id, membership.role_list())
        return LoginResponse(access_token=token, expires_in=settings.access_token_minutes * 60)
    return LoginResponse(
        selection_token=create_selection_token(settings, user.id),
        requires_tenant_selection=True,
        tenants=[_choice(item) for item in memberships],
    )


@router.post("/select-tenant", response_model=LoginResponse)
def select_tenant(
    payload: SelectTenantRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    try:
        claims = decode_token(request.app.state.settings, payload.selection_token, "tenant_selection")
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    membership = session.scalar(
        select(Membership).where(
            Membership.user_id == claims["sub"], Membership.tenant_id == payload.tenant_id
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="tenant membership not found")
    token = create_access_token(
        request.app.state.settings,
        membership.user_id,
        membership.tenant_id,
        membership.role_list(),
    )
    return LoginResponse(
        access_token=token,
        expires_in=request.app.state.settings.access_token_minutes * 60,
    )


@router.get("/me", response_model=UserView)
def me(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    membership = session.scalar(
        select(Membership)
        .where(
            Membership.user_id == principal.user_id,
            Membership.tenant_id == principal.tenant_id,
        )
        .options(selectinload(Membership.user), selectinload(Membership.tenant))
    )
    if membership is None:
        raise HTTPException(status_code=401, detail="membership is no longer active")
    return UserView(
        user_id=membership.user_id,
        email=membership.user.email,
        display_name=membership.user.display_name,
        tenant_id=membership.tenant_id,
        tenant_name=membership.tenant.name,
        roles=membership.role_list(),
    )

