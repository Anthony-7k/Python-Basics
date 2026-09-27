from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings
from app.security.models import UserContext

bearer_scheme = HTTPBearer(auto_error=False)


class JWTService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def issue_dev_token(
        self,
        *,
        subject: str,
        tenant_id: str,
        roles: list[str],
    ) -> str:
        if (
            not self.settings.allow_dev_identity
            or self.settings.app_env == "production"
        ):
            raise PermissionError("Development identity endpoint is disabled")
        if self.settings.jwt_algorithm != "HS256" or not self.settings.jwt_secret:
            raise RuntimeError("Development tokens require an HS256 secret")
        now = datetime.now(UTC)
        payload = {
            "iss": self.settings.jwt_issuer,
            "aud": self.settings.jwt_audience,
            "sub": subject,
            "tenant_id": tenant_id,
            "roles": roles,
            "jti": str(uuid4()),
            "iat": now,
            "exp": now + timedelta(seconds=self.settings.jwt_token_ttl_seconds),
        }
        return jwt.encode(
            payload,
            self.settings.jwt_secret.get_secret_value(),
            algorithm="HS256",
        )

    def decode(self, token: str) -> UserContext:
        try:
            key = self._verification_key(token)
            payload = jwt.decode(
                token,
                key,
                algorithms=[self.settings.jwt_algorithm],
                audience=self.settings.jwt_audience,
                issuer=self.settings.jwt_issuer,
                options={"require": ["exp", "iss", "aud", "sub", "tenant_id"]},
            )
            roles = payload.get("roles", [])
            if not isinstance(roles, list) or not all(
                isinstance(role, str) for role in roles
            ):
                raise jwt.InvalidTokenError("roles must be a string list")
            return UserContext(
                subject=payload["sub"],
                tenant_id=payload["tenant_id"],
                roles=frozenset(roles),
                token_id=payload.get("jti"),
            )
        except (jwt.PyJWTError, ValueError, KeyError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "invalid_token", "message": str(exc)},
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    def _verification_key(self, token: str):
        if self.settings.jwt_algorithm == "HS256":
            if not self.settings.jwt_secret:
                raise jwt.InvalidTokenError("JWT secret is not configured")
            return self.settings.jwt_secret.get_secret_value()
        if self.settings.jwks_url:
            return (
                jwt.PyJWKClient(self.settings.jwks_url)
                .get_signing_key_from_jwt(token)
                .key
            )
        if not self.settings.jwt_public_key:
            raise jwt.InvalidTokenError("JWT public key is not configured")
        return self.settings.jwt_public_key.get_secret_value()


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> UserContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "missing_token"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return JWTService(request.app.state.settings).decode(credentials.credentials)
