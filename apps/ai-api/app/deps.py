"""FastAPI dependencies: DemoContext parsing/validation and permission checks.

Usage in a handler:
    @router.get("/x", response_model=XOut)
    def x(ctx: DemoContext = Depends(require_permission(Permission.read_production)),
          db: Session = Depends(get_db)) -> XOut: ...
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Depends, Header, Query, Request
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.errors import ApiError
from app.models.enums import Role, ScenarioCode
from app.services.demo_context import DemoContext, parse_as_of, resolve_scenario_focus
from app.services.rbac import DEFAULT_ROLE, Permission, has_permission


def get_demo_context(
    request: Request,
    as_of: str | None = Query(
        None,
        description="Demo clock. ISO date (-> 18:00 mill time) or datetime (naive = Asia/Bangkok). Must lie inside the dataset window.",
        max_length=40,
    ),
    scenario_id: str | None = Query(None, description="Scenario code; if as_of is omitted the scenario's focus time is used.", max_length=40),
    x_demo_session: str | None = Header(None, description="Sandbox session uuid (ADR-006). Required for writes."),
    x_demo_role: str | None = Header(None, description="Simulated role (ADR-007). Default public_viewer."),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> DemoContext:
    # role
    role = DEFAULT_ROLE
    if x_demo_role:
        try:
            role = Role(x_demo_role.strip().lower())
        except ValueError as exc:
            raise ApiError(422, "invalid_role", "Unknown X-Demo-Role", {"allowed": [r.value for r in Role]}) from exc
    # session
    session_id = None
    if x_demo_session:
        try:
            session_id = str(uuid.UUID(x_demo_session.strip()))
        except ValueError as exc:
            raise ApiError(422, "invalid_session", "X-Demo-Session must be a UUID") from exc
    # scenario
    scenario = None
    if scenario_id:
        try:
            scenario = ScenarioCode(scenario_id.strip().upper())
        except ValueError as exc:
            raise ApiError(422, "invalid_scenario", "Unknown scenario_id", {"allowed": [s.value for s in ScenarioCode]}) from exc
    # clock
    explicit = as_of is not None
    if explicit:
        ts = parse_as_of(as_of, settings)
    else:
        ts = (resolve_scenario_focus(db, scenario) if scenario else None) or settings.default_as_of
    return DemoContext(
        as_of=ts,
        as_of_explicit=explicit,
        scenario_id=scenario,
        session_id=session_id,
        role=role,
        request_id=getattr(request.state, "request_id", None),
        window_start=settings.window_start,
        window_end=settings.window_end,
        timezone=settings.mill_timezone,
    )


def require_permission(permission: Permission | str) -> Callable[..., DemoContext]:
    perm = Permission(permission)

    def _dep(ctx: DemoContext = Depends(get_demo_context)) -> DemoContext:
        if not has_permission(ctx.role, perm):
            raise ApiError(
                403,
                "forbidden",
                f"Role '{ctx.role.value}' is not permitted to perform '{perm.value}' (simulated role, ADR-007).",
                {"role": ctx.role.value, "permission": perm.value},
            )
        return ctx

    _dep.__name__ = f"require_{perm.name}"
    _dep.permission = perm  # type: ignore[attr-defined]  # introspected by the contract doc generator
    return _dep
