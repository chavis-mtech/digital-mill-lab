"""Logistics & Weighbridge (SPEC 4.D). Owner: backend-a."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.api.v1._contract import STD_RESPONSES, contract
from app.db.session import get_db
from app.deps import require_permission
from app.errors import bad_request
from app.schemas.common import Period
from app.schemas.logistics import (
    ArrivalPatternResponse,
    LogisticsKpisResponse,
    QueueNowResponse,
    QueueSimulationRequest,
    QueueSimulationResponse,
    SupplierDetail,
    SupplierListResponse,
    TicketListResponse,
)
from app.services import logistics, logistics_sim
from app.services.demo_context import DemoContext
from app.services.rbac import Permission as P

OWNER = "backend-a"
router = APIRouter(prefix="/logistics", tags=["logistics"], responses=STD_RESPONSES)
_read = require_permission(P.read_logistics)


@router.get("/queue", response_model=QueueNowResponse, summary="Trucks waiting / unloading at the demo clock",
            openapi_extra=contract(P.read_logistics, OWNER, "DML-061", status="implemented"))
def queue_now(ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return logistics.queue_now(db, ctx)


@router.get("/tickets", response_model=TicketListResponse, summary="Weighbridge tickets (gross/tare/net) with review flags",
            openapi_extra=contract(P.read_logistics, OWNER, "DML-060", status="implemented"))
def list_tickets(
    period: Period = Query(Period.today),
    supplier_id: int | None = Query(None, ge=1),
    flagged_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: DemoContext = Depends(_read),
    db: Session = Depends(get_db),
):
    if period == Period.custom:
        bad_request("invalid_period", "Use today, 7d or 30d")
    return logistics.tickets(db, ctx, period, supplier_id, flagged_only, limit, offset)


@router.get("/suppliers", response_model=SupplierListResponse, summary="Suppliers with volume / quality / wait KPIs",
            openapi_extra=contract(P.read_logistics, OWNER, "DML-059", status="implemented"))
def list_suppliers(
    supplier_type: str | None = Query(None, pattern="^(smallholder|dealer|estate|own_estate)$"),
    ctx: DemoContext = Depends(_read),
    db: Session = Depends(get_db),
):
    return logistics.suppliers(db, ctx, supplier_type)


@router.get("/suppliers/{supplier_id}", response_model=SupplierDetail, summary="Supplier detail with plantations and trends",
            openapi_extra=contract(P.read_logistics, OWNER, "DML-059", status="implemented"))
def get_supplier(supplier_id: int = Path(ge=1), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return logistics.supplier_detail(db, ctx, supplier_id)


@router.get("/kpis", response_model=LogisticsKpisResponse, summary="Waiting time, turnaround, queue length, utilisation",
            openapi_extra=contract(P.read_logistics, OWNER, "DML-064", status="implemented"))
def logistics_kpis(period: Period = Query(Period.today), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    if period == Period.custom:
        bad_request("invalid_period", "Use today, 7d or 30d")
    return logistics.kpis(db, ctx, period)


@router.get("/arrival-pattern", response_model=ArrivalPatternResponse, summary="Arrivals by hour vs typical pattern",
            openapi_extra=contract(P.read_logistics, OWNER, "DML-061", status="implemented"))
def arrival_pattern(
    business_date: date | None = Query(None),
    lookback_days: int = Query(14, ge=1, le=90),
    ctx: DemoContext = Depends(_read),
    db: Session = Depends(get_db),
):
    return logistics.arrival_pattern(db, ctx, business_date, lookback_days)


@router.post("/queue-simulation", response_model=QueueSimulationResponse, summary="FIFO vs constraint-aware slot scheduling (simulated)",
             openapi_extra=contract(P.scenario_calculate, OWNER, "DML-063", status="implemented"))
def queue_simulation(
    body: QueueSimulationRequest,
    ctx: DemoContext = Depends(require_permission(P.scenario_calculate)),
    db: Session = Depends(get_db),
):
    return logistics_sim.run(db, ctx, body)
