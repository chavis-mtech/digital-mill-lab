"""Demo control: sandbox sessions, roles, context, session reset, simulated-live tick. Owner: backend-b.

The architect implemented the stateless parts (roles, session id issue, context echo); backend-b added reset,
reset-all, the simulated-live tick and latest_data_ts.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1._contract import STD_RESPONSES, contract
from app.config import Settings, get_settings
from app.db.session import get_db
from app.deps import require_permission
from app.models.enums import Role
from app.schemas.common import DemoContextOut
from app.schemas.demo import (
    DemoContextResponse,
    ResetAllResponse,
    RoleListResponse,
    RoleOut,
    SessionCreateResponse,
    SessionResetResponse,
    TickRequest,
    TickResponse,
)
from app.services import demo_state
from app.services.demo_context import DemoContext
from app.services.rbac import ROLE_LABELS, ROLE_PERMISSIONS, copilot_tools_for, is_read_only
from app.services.rbac import Permission as P

OWNER = "backend-b"
router = APIRouter(prefix="/demo", tags=["demo"], responses=STD_RESPONSES)
_session = require_permission(P.demo_session)


def context_out(ctx: DemoContext) -> DemoContextOut:
    return DemoContextOut(
        as_of=ctx.as_of,
        as_of_explicit=ctx.as_of_explicit,
        scenario_id=ctx.scenario_id,
        session_id=ctx.session_id,
        role=ctx.role,
        window_start=ctx.window_start,
        window_end=ctx.window_end,
        timezone=ctx.timezone,
        business_date=ctx.business_date,
    )


@router.get("/roles", response_model=RoleListResponse, summary="Simulated roles with permissions and copilot tools",
            openapi_extra=contract(None, OWNER, "DML-103", status="implemented"))
def list_roles() -> RoleListResponse:
    return RoleListResponse(
        items=[
            RoleOut(
                role=r,
                label_en=ROLE_LABELS[r]["en"],
                label_th=ROLE_LABELS[r]["th"],
                read_only=is_read_only(r),
                permissions=sorted(p.value for p in ROLE_PERMISSIONS[r]),
                copilot_tools=copilot_tools_for(r),
            )
            for r in Role
        ]
    )


@router.post("/session", response_model=SessionCreateResponse, status_code=201, summary="Issue a new sandbox session id",
             openapi_extra=contract(P.demo_session, OWNER, "DML-034", status="implemented"))
def create_session(ctx: DemoContext = Depends(_session)) -> SessionCreateResponse:
    return SessionCreateResponse(session_id=str(uuid.uuid4()), created_at=datetime.now(UTC))


@router.get("/context", response_model=DemoContextResponse, summary="Echo the resolved DemoContext (clock, window, role, session)",
            openapi_extra=contract(P.demo_session, OWNER, "DML-034", status="implemented"))
def get_context(ctx: DemoContext = Depends(_session), settings: Settings = Depends(get_settings), db: Session = Depends(get_db)) -> DemoContextResponse:
    return DemoContextResponse(context=context_out(ctx), default_as_of=settings.default_as_of, latest_data_ts=demo_state.latest_data_ts(db))


@router.post("/session/reset", response_model=SessionResetResponse, summary="Delete this session's rows (audit log kept)",
             openapi_extra=contract(P.demo_session, OWNER, "DML-034", status="implemented"))
def reset_session(ctx: DemoContext = Depends(_session), db: Session = Depends(get_db)):
    return demo_state.reset_session(db, ctx)


@router.post("/reset-all", response_model=ResetAllResponse, summary="Admin: clear all visitor sessions",
             openapi_extra=contract(P.demo_reset_all, OWNER, "DML-034", status="implemented"))
def reset_all(ctx: DemoContext = Depends(require_permission(P.demo_reset_all)), db: Session = Depends(get_db)):
    return demo_state.reset_all(db, ctx)


@router.post("/tick", response_model=TickResponse, summary="Simulated live mode: next as_of + headline deltas",
             openapi_extra=contract(P.demo_session, OWNER, "DML-037", status="implemented"))
def tick(body: TickRequest, ctx: DemoContext = Depends(_session), db: Session = Depends(get_db)):
    return demo_state.tick(db, ctx, body)
