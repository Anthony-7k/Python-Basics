from hmac import compare_digest

from fastapi import (
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from app.core.security import AuthenticatedUser
from app.core.settings import DEMO_AUTH_USERS


bearer_scheme = HTTPBearer(auto_error=False)


def _authentication_error() -> HTTPException:
    return HTTPException(
        status_code=(
            status.HTTP_401_UNAUTHORIZED
        ),
        detail="Missing or invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    request: Request,
    credentials: (
        HTTPAuthorizationCredentials | None
    ) = Depends(bearer_scheme),
) -> AuthenticatedUser:
    if (
        credentials is None
        or credentials.scheme.lower()
        != "bearer"
    ):
        raise _authentication_error()

    matched_email = None

    for configured_token, email in (
        DEMO_AUTH_USERS.items()
    ):
        if compare_digest(
            credentials.credentials,
            configured_token,
        ):
            matched_email = email

    if matched_email is None:
        raise _authentication_error()

    current_user = AuthenticatedUser(
        email=matched_email,
        display_name="Demo API User",
    )
    request.state.actor_id = (
        current_user.audit_id
    )
    return current_user
