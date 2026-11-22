"""FFB Supplier & Traceability (SPEC 4.H). Owner: backend-b."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.api.v1._contract import STD_RESPONSES, contract
from app.db.session import get_db
from app.deps import require_permission
from app.schemas.common import Period
from app.schemas.roi import PrintableDocument
from app.schemas.traceability import DeliveryListResponse, LotListResponse, TraceGraphResponse, TraceReportResponse
from app.services import traceability as svc
from app.services.demo_context import DemoContext
from app.services.rbac import Permission as P

OWNER = "backend-b"
router = APIRouter(prefix="/traceability", tags=["traceability"], responses=STD_RESPONSES)
_read = require_permission(P.read_traceability)


@router.get("/lots", response_model=LotListResponse, summary="CPO output lots",
            openapi_extra=contract(P.read_traceability, OWNER, "DML-083", status="implemented"))
def list_lots(
    period: Period = Query(Period.last_7d),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: DemoContext = Depends(_read),
    db: Session = Depends(get_db),
):
    return svc.list_lots(db, ctx, period, limit, offset)


@router.get("/deliveries", response_model=DeliveryListResponse, summary="FFB deliveries (supplier, ticket, grade)",
            openapi_extra=contract(P.read_traceability, OWNER, "DML-082", status="implemented"))
def list_deliveries(
    supplier_id: int | None = Query(None, ge=1),
    period: Period = Query(Period.today),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: DemoContext = Depends(_read),
    db: Session = Depends(get_db),
):
    return svc.list_deliveries(db, ctx, supplier_id, period, limit, offset)


@router.get("/forward", response_model=TraceGraphResponse, summary="Forward trace: supplier/delivery -> batches -> CPO lots",
            openapi_extra=contract(P.read_traceability, OWNER, "DML-082", status="implemented"))
def trace_forward(
    supplier_id: int | None = Query(None, ge=1),
    delivery_id: int | None = Query(None, ge=1),
    max_nodes: int = Query(200, ge=10, le=1000),
    ctx: DemoContext = Depends(_read),
    db: Session = Depends(get_db),
):
    return svc.trace_forward(db, ctx, supplier_id, delivery_id, max_nodes)


@router.get("/backward", response_model=TraceGraphResponse, summary="Backward trace: CPO lot / batch -> suppliers (mass-balance shares)",
            openapi_extra=contract(P.read_traceability, OWNER, "DML-083", status="implemented"))
def trace_backward(
    lot_id: int | None = Query(None, ge=1),
    production_batch_id: int | None = Query(None, ge=1),
    max_nodes: int = Query(200, ge=10, le=1000),
    ctx: DemoContext = Depends(_read),
    db: Session = Depends(get_db),
):
    return svc.trace_backward(db, ctx, lot_id, production_batch_id, max_nodes)


@router.get("/lots/{lot_id}/report", response_model=TraceReportResponse, summary="Traceability report for a CPO lot",
            openapi_extra=contract(P.read_traceability, OWNER, "DML-084", status="implemented"))
def lot_report(lot_id: int = Path(ge=1), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return svc.lot_report(db, ctx, lot_id)


@router.get("/lots/{lot_id}/report/printable", response_model=PrintableDocument, summary="Printable HTML traceability report for a CPO lot (render in an iframe, print to PDF)",
            openapi_extra=contract(P.read_traceability, OWNER, "DML-084", status="implemented"))
def lot_report_printable(lot_id: int = Path(ge=1), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return svc.lot_report_document(db, ctx, lot_id)
