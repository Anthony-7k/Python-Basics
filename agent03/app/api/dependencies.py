from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.security.tokens import Principal, TokenError, principal_from_token

bearer = HTTPBearer(auto_error=False)


def get_session(request: Request) -> Generator[Session, None, None]:
    session = request.app.state.database.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> Principal:
    if credentials is None:
        raise HTTPException(status_code=401, detail="authentication required")
    try:
        return principal_from_token(request.app.state.settings, credentials.credentials)
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def require_roles(*required: str):
    def dependency(principal: Principal = Depends(get_principal)) -> Principal:
        if not set(required).intersection(principal.roles):
            raise HTTPException(status_code=403, detail="insufficient role")
        return principal

    return dependency

