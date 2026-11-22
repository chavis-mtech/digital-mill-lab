"""Palm Mill Production Intelligence (SPEC 4.B). Owner: backend-a."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1._contract import STD_RESPONSES, contract
from app.db.session import get_db
from app.deps import require_permission
from app.errors import bad_request
from app.schemas.common import Granularity, Period
from app.schemas.production import (
    BatchListResponse,
    OerTrendResponse,
    OilLossResponse,
    ProcessStateResponse,
    ProductionSummaryResponse,
    QualityResponse,
    ShiftListResponse,
)
from app.services import production
from app.services.demo_context import DemoContext
from app.services.rbac import Permission as P

OWNER = "backend-a"
router = APIRouter(prefix="/production", tags=["production"], responses=STD_RESPONSES)
_read = require_permission(P.read_production)


def _no_custom(period: Period) -> None:
    if period == Period.custom:
        bad_request("invalid_period", "Use today, 7d or 30d")


@router.get("/summary", response_model=ProductionSummaryResponse, summary="Business-day production summary + mass balance",
            openapi_extra=contract(P.read_production, OWNER, "DML-043", status="implemented"))
def get_summary(business_date: date | None = Query(None, description="Default: as_of day"), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return production.summary(db, ctx, business_date)


@router.get("/oer-trend", response_model=OerTrendResponse, summary="OER/KER trend with expected OER for comparison",
            openapi_extra=contract(P.read_production, OWNER, "DML-045", status="implemented"))
def get_oer_trend(
    period: Period = Query(Period.last_30d),
    granularity: Granularity = Query(Granularity.day),
    ctx: DemoContext = Depends(_read),
    db: Session = Depends(get_db),
):
    _no_custom(period)
    return production.oer_trend(db, ctx, period, granularity.value)


@router.get("/process-state", response_model=ProcessStateResponse, summary="Current hourly mill state vs normal ranges",
            openapi_extra=contract(P.read_production, OWNER, "DML-044", status="implemented"))
def get_process_state(ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return production.process_state(db, ctx)


@router.get("/shifts", response_model=ShiftListResponse, summary="Shift results",
            openapi_extra=contract(P.read_production, OWNER, "DML-043", status="implemented"))
def list_shifts(period: Period = Query(Period.last_7d), limit: int = Query(60, ge=1, le=500), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    _no_custom(period)
    return production.shifts(db, ctx, period, limit)


@router.get("/losses", response_model=OilLossResponse, summary="Oil-loss breakdown vs industry-practice benchmarks",
            openapi_extra=contract(P.read_production, OWNER, "DML-045", status="implemented"))
def get_losses(period: Period = Query(Period.last_7d), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    _no_custom(period)
    return production.losses(db, ctx, period)


@router.get("/batches", response_model=BatchListResponse, summary="Processing batches",
            openapi_extra=contract(P.read_production, OWNER, "DML-043", status="implemented"))
def list_batches(
    period: Period = Query(Period.today),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: DemoContext = Depends(_read),
    db: Session = Depends(get_db),
):
    _no_custom(period)
    return production.batches(db, ctx, period, limit, offset)


@router.get("/quality", response_model=QualityResponse, summary="Lab / QC parameters (FFA, moisture, dirt, DOBI, losses)",
            openapi_extra=contract(P.read_production, OWNER, "DML-043", status="implemented"))
def get_quality(period: Period = Query(Period.last_7d), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    _no_custom(period)
    return production.quality(db, ctx, period)
