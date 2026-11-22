"""Unified alerts across modules. Owner: backend-a."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.api.v1._contract import STD_RESPONSES, contract
from app.db.session import get_db
from app.deps import require_permission
from app.schemas.alerts import AlertAcknowledgeRequest, AlertListResponse, AlertOut
from app.schemas.common import AlertStatus, Severity
from app.services import kpi_alerts
from app.services.demo_context import DemoContext
from app.services.rbac import Permission as P

OWNER = "backend-a"
router = APIRouter(prefix="/alerts", tags=["alerts"], responses=STD_RESPONSES)


@router.get("", response_model=AlertListResponse, summary="Prioritised alerts (risk level, team, impact) as of the demo clock",
            openapi_extra=contract(P.read_executive, OWNER, "DML-039", status="implemented"))
def list_alerts(
    module: str | None = Query(None, pattern="^(production|maintenance|energy|logistics|quality)$"),
    severity: Severity | None = Query(None),
    status: AlertStatus | None = Query(None),
    equipment_id: int | None = Query(None, ge=1),
    stage_code: str | None = Query(None, max_length=32),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    active_only: bool = Query(False, description="Only new / acknowledged / in_progress at as_of"),
    ctx: DemoContext = Depends(require_permission(P.read_executive)),
    db: Session = Depends(get_db),
):
    return kpi_alerts.list_alerts(
        db, ctx, module=module, severity=severity.value if severity else None, status=status.value if status else None,
        equipment_id=equipment_id, stage_code=stage_code, active_only=active_only, limit=limit, offset=offset,
    )


@router.get("/{alert_id}", response_model=AlertOut, summary="Alert detail with evidence and estimated impact",
            openapi_extra=contract(P.read_executive, OWNER, "DML-039", status="implemented"))
def get_alert(alert_id: int = Path(ge=1), ctx: DemoContext = Depends(require_permission(P.read_executive)), db: Session = Depends(get_db)):
    return kpi_alerts.get_alert(db, ctx, alert_id)


@router.post("/{alert_id}/status", response_model=AlertOut, summary="Acknowledge / resolve / dismiss (session-scoped, audited)",
             openapi_extra=contract(P.alert_acknowledge, OWNER, "DML-039", status="implemented"))
def change_alert_status(
    body: AlertAcknowledgeRequest,
    alert_id: int = Path(ge=1),
    ctx: DemoContext = Depends(require_permission(P.alert_acknowledge)),
    db: Session = Depends(get_db),
):
    return kpi_alerts.change_status(db, ctx, alert_id, body.to_status.value, body.note)
