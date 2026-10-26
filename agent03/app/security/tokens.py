from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt

from app.config import Settings


class TokenError(ValueError):
    pass


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str
    roles: tuple[str, ...]
    jti: str


def _encode(settings: Settings, claims: dict, minutes: int) -> str:
    now = datetime.now(UTC)
    payload = {
        **claims,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
        "jti": str(uuid4()),
        "iss": "docflow-ai",
        "aud": "docflow-web",
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_access_token(settings: Settings, user_id: str, tenant_id: str, roles: list[str]) -> str:
    return _encode(
        settings,
        {"sub": user_id, "tenant_id": tenant_id, "roles": roles, "type": "access"},
        settings.access_token_minutes,
    )


def create_selection_token(settings: Settings, user_id: str) -> str:
    return _encode(
        settings,
        {"sub": user_id, "type": "tenant_selection"},
        settings.selection_token_minutes,
    )


def decode_token(settings: Settings, token: str, expected_type: str) -> dict:
    try:
        claims = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            audience="docflow-web",
            issuer="docflow-ai",
        )
    except jwt.PyJWTError as exc:
        raise TokenError("invalid or expired token") from exc
    if claims.get("type") != expected_type or not claims.get("sub"):
        raise TokenError("invalid token type")
    return claims


def principal_from_token(settings: Settings, token: str) -> Principal:
    claims = decode_token(settings, token, "access")
    tenant_id = claims.get("tenant_id")
    if not tenant_id:
        raise TokenError("token has no tenant")
    return Principal(
        user_id=claims["sub"],
        tenant_id=tenant_id,
        roles=tuple(claims.get("roles", [])),
        jti=claims["jti"],
    )

