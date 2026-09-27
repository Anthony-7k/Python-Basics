from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException

from app.config import Settings
from app.security.auth import JWTService
from app.security.models import UserContext
from app.security.permissions import Permission, has_permission, require_permission


def test_dev_token_is_disabled_when_identity_endpoint_is_off():
    service = JWTService(Settings(allow_dev_identity=False))
    with pytest.raises(PermissionError):
        service.issue_dev_token(subject="user", tenant_id="tenant", roles=["operator"])


def test_dev_token_requires_hs256():
    service = JWTService(
        Settings(jwt_algorithm="RS256", jwt_public_key="not-used-for-issuing")
    )
    with pytest.raises(RuntimeError, match="HS256"):
        service.issue_dev_token(subject="user", tenant_id="tenant", roles=["operator"])


def test_token_roles_must_be_a_string_list():
    settings = Settings()
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "sub": "user",
            "tenant_id": "tenant",
            "roles": "operator",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as caught:
        JWTService(settings).decode(token)
    assert caught.value.status_code == 401


@pytest.mark.parametrize(
    "settings",
    [
        Settings(jwt_secret=None),
        Settings(jwt_algorithm="RS256", jwt_public_key=None, jwks_url=None),
    ],
)
def test_missing_verification_key_is_rejected(settings):
    with pytest.raises(HTTPException) as caught:
        JWTService(settings).decode("opaque-token")
    assert caught.value.status_code == 401


def test_permissions_ignore_unknown_roles_and_raise_consistently():
    identity = UserContext(
        subject="user",
        tenant_id="tenant",
        roles=frozenset({"unknown-role"}),
    )
    assert has_permission(identity, Permission.TASK_READ) is False
    with pytest.raises(HTTPException) as caught:
        require_permission(identity, Permission.TASK_CREATE)
    assert caught.value.status_code == 403
    assert caught.value.detail["required_permission"] == "task:create"
