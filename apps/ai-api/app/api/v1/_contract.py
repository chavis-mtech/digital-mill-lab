"""Contract metadata helpers shared by all routers (architect-owned).

Every operation carries OpenAPI extensions:
  x-owner       agent responsible for implementing the handler
  x-task        backlog task id (docs/TASKS.md)
  x-status      stub | implemented | partial | prototype  (owners flip to "implemented" when done)
  x-permission  permission checked by the require_permission dependency
  x-roles       roles holding that permission (derived from services/rbac.py - never hand-written)
docs/architecture/API_CONTRACT.md is generated from these by `make contracts`.
A test asserts x-permission matches the handler's require_permission dependency.
"""

from __future__ import annotations

from typing import Any

from app.schemas.common import ErrorEnvelope
from app.services.rbac import Permission, roles_with

STD_RESPONSES: dict[int | str, dict[str, Any]] = {
    403: {"model": ErrorEnvelope, "description": "Role not permitted (simulated RBAC)"},
    422: {"model": ErrorEnvelope, "description": "Validation error (query, headers, body, as_of window)"},
    429: {"model": ErrorEnvelope, "description": "Rate limited"},
    501: {"model": ErrorEnvelope, "description": "Contract stub - not implemented yet"},
}


def contract(permission: Permission | None, owner: str, task: str | None = None, status: str = "stub") -> dict[str, Any]:
    extra: dict[str, Any] = {"x-owner": owner, "x-task": task, "x-status": status}
    if permission is not None:
        perm = Permission(permission)
        extra["x-permission"] = perm.value
        extra["x-roles"] = [r.value for r in roles_with(perm)]
    else:
        extra["x-permission"] = None
        extra["x-roles"] = ["*"]
    return extra
