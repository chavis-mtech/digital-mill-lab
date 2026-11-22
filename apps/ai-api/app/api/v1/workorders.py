"""Maintenance work-order workflow (AI-C05). Owner: backend-b. All writes session-scoped + audited."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.api.v1._contract import STD_RESPONSES, contract
from app.db.session import get_db
from app.deps import require_permission
from app.schemas.common import WorkOrderPriority, WorkOrderStatus
from app.schemas.workorders import (
    AuditTrailResponse,
    WorkOrderAssignRequest,
    WorkOrderCreateRequest,
    WorkOrderDetail,
    WorkOrderListResponse,
    WorkOrderOut,
    WorkOrderTransitionRequest,
)
from app.services import workorders as svc
from app.services.demo_context import DemoContext
from app.services.rbac import Permission as P

OWNER = "backend-b"
router = APIRouter(prefix="/work-orders", tags=["work-orders"], responses=STD_RESPONSES)
_read = require_permission(P.read_maintenance)


@router.get("", response_model=WorkOrderListResponse, summary="Work orders (shared baseline + your session)",
            openapi_extra=contract(P.read_maintenance, OWNER, "DML-056", status="implemented"))
def list_work_orders(
    status: WorkOrderStatus | None = Query(None),
    priority: WorkOrderPriority | None = Query(None),
    equipment_id: int | None = Query(None, ge=1),
    mine_only: bool = Query(False, description="Only rows created in this session"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: DemoContext = Depends(_read),
    db: Session = Depends(get_db),
):
    return svc.list_work_orders(db, ctx, status, priority, equipment_id, mine_only, limit, offset)


@router.post("", response_model=WorkOrderOut, status_code=201, summary="Create (manual / from alert / from recommendation); requires confirm=true",
             openapi_extra=contract(P.workorder_create, OWNER, "DML-056", status="implemented"))
def create_work_order(
    body: WorkOrderCreateRequest,
    ctx: DemoContext = Depends(require_permission(P.workorder_create)),
    db: Session = Depends(get_db),
):
    return svc.create_work_order(db, ctx, body)


@router.get("/{work_order_id}", response_model=WorkOrderDetail, summary="Work order with status history",
            openapi_extra=contract(P.read_maintenance, OWNER, "DML-056", status="implemented"))
def get_work_order(work_order_id: int = Path(ge=1), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return svc.view_to_detail(db, ctx, svc.find_view(db, ctx, work_order_id))


@router.post("/{work_order_id}/assign", response_model=WorkOrderOut, summary="Assign a technician",
             openapi_extra=contract(P.workorder_assign, OWNER, "DML-056", status="implemented"))
def assign_work_order(
    body: WorkOrderAssignRequest,
    work_order_id: int = Path(ge=1),
    ctx: DemoContext = Depends(require_permission(P.workorder_assign)),
    db: Session = Depends(get_db),
):
    return svc.assign_work_order(db, ctx, work_order_id, body)


@router.post("/{work_order_id}/transition", response_model=WorkOrderOut, summary="Change status (validated state machine)",
             openapi_extra=contract(P.workorder_transition, OWNER, "DML-056", status="implemented"))
def transition_work_order(
    body: WorkOrderTransitionRequest,
    work_order_id: int = Path(ge=1),
    ctx: DemoContext = Depends(require_permission(P.workorder_transition)),
    db: Session = Depends(get_db),
):
    return svc.transition_work_order(db, ctx, work_order_id, body)


@router.get("/{work_order_id}/audit", response_model=AuditTrailResponse, summary="Audit trail with hash-chain verification",
            openapi_extra=contract(P.read_maintenance, OWNER, "DML-056", status="implemented"))
def work_order_audit(work_order_id: int = Path(ge=1), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return svc.audit_trail(db, ctx, work_order_id)
