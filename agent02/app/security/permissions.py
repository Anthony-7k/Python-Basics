from __future__ import annotations

from enum import StrEnum

from fastapi import HTTPException, status

from app.security.models import UserContext


class Role(StrEnum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    APPROVER = "approver"
    ADMIN = "admin"


class Permission(StrEnum):
    TASK_READ = "task:read"
    TASK_CREATE = "task:create"
    TASK_RESUME = "task:resume"
    TASK_APPROVE = "task:approve"
    AUDIT_READ = "audit:read"
    METRICS_READ = "metrics:read"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: frozenset({Permission.TASK_READ}),
    Role.OPERATOR: frozenset(
        {
            Permission.TASK_READ,
            Permission.TASK_CREATE,
            Permission.TASK_RESUME,
            Permission.METRICS_READ,
        }
    ),
    Role.APPROVER: frozenset(
        {
            Permission.TASK_READ,
            Permission.TASK_APPROVE,
            Permission.METRICS_READ,
        }
    ),
    Role.ADMIN: frozenset(Permission),
}


def has_permission(context: UserContext, permission: Permission) -> bool:
    granted: set[Permission] = set()
    for raw_role in context.roles:
        try:
            granted.update(ROLE_PERMISSIONS[Role(raw_role)])
        except ValueError:
            continue
    return permission in granted


def require_permission(context: UserContext, permission: Permission) -> None:
    if not has_permission(context, permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "permission_denied",
                "required_permission": permission.value,
            },
        )
