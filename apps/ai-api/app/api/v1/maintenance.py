"""Predictive Maintenance (SPEC 4.C). Owner: backend-b (health/risk computed by ml services)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.api.v1._contract import STD_RESPONSES, contract
from app.db.session import get_db
from app.deps import require_permission
from app.schemas.common import HealthState, Period, RecommendationStatus
from app.schemas.maintenance import (
    DowntimeAnalysisResponse,
    EquipmentDetail,
    EquipmentHealth,
    EquipmentListResponse,
    MaintenanceHistoryResponse,
    MaintenanceImpactRequest,
    MaintenanceImpactResponse,
    RecommendationDecisionRequest,
    RecommendationListResponse,
    RecommendationOut,
    SensorSeriesResponse,
    TechnicianListResponse,
)
from app.services import maintenance as svc
from app.services import maintenance_reco as reco
from app.services.demo_context import DemoContext
from app.services.rbac import Permission as P

OWNER = "backend-b"
router = APIRouter(prefix="/maintenance", tags=["maintenance"], responses=STD_RESPONSES)
_read = require_permission(P.read_maintenance)


@router.get("/equipment", response_model=EquipmentListResponse, summary="Equipment registry with computed health state",
            openapi_extra=contract(P.read_maintenance, OWNER, "DML-051", status="implemented"))
def list_equipment(
    stage_code: str | None = Query(None, max_length=32),
    equipment_type: str | None = Query(None, max_length=32),
    health_state: HealthState | None = Query(None),
    sort: str = Query("stage", pattern="^(stage|risk)$", description="stage order or highest relative risk index first"),
    ctx: DemoContext = Depends(_read),
    db: Session = Depends(get_db),
):
    return svc.list_equipment(db, ctx, stage_code, equipment_type, health_state, sort)


@router.get("/equipment/{equipment_id}", response_model=EquipmentDetail, summary="Equipment detail with sensors and health",
            openapi_extra=contract(P.read_maintenance, OWNER, "DML-051", status="implemented"))
def get_equipment(equipment_id: int = Path(ge=1), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return svc.equipment_detail(db, ctx, equipment_id)


@router.get("/equipment/{equipment_id}/health", response_model=EquipmentHealth, summary="Health state with the explicit criteria that produced it",
            openapi_extra=contract(P.read_maintenance, OWNER, "DML-052", status="implemented"))
def get_equipment_health(equipment_id: int = Path(ge=1), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return svc.equipment_health(db, ctx, equipment_id)


@router.get("/equipment/{equipment_id}/history", response_model=MaintenanceHistoryResponse, summary="Maintenance history, MTBF/MTTR",
            openapi_extra=contract(P.read_maintenance, OWNER, "DML-057", status="implemented"))
def get_equipment_history(
    equipment_id: int = Path(ge=1),
    period: Period = Query(Period.last_30d),
    ctx: DemoContext = Depends(_read),
    db: Session = Depends(get_db),
):
    return svc.history(db, ctx, equipment_id, period)


@router.get("/equipment/{equipment_id}/sensors", response_model=SensorSeriesResponse, summary="Sensor time-series (downsampled server-side)",
            openapi_extra=contract(P.read_maintenance, OWNER, "DML-052", status="implemented"))
def get_equipment_sensors(
    equipment_id: int = Path(ge=1),
    sensor_codes: list[str] | None = Query(None, max_length=20),
    start: datetime | None = Query(None, description="Default: as_of - 7 days"),
    end: datetime | None = Query(None, description="Default/maximum: as_of"),
    resolution: str = Query("hour", pattern="^(raw|10min|hour|day)$"),
    agg: str = Query("mean", pattern="^(mean|max)$", description="Bucket aggregation (use max to keep short peaks visible)"),
    ctx: DemoContext = Depends(_read),
    db: Session = Depends(get_db),
):
    return svc.sensor_series(db, ctx, equipment_id, sensor_codes, start, end, resolution, agg)


@router.get("/recommendations", response_model=RecommendationListResponse, summary="Advisory maintenance recommendations",
            openapi_extra=contract(P.read_maintenance, OWNER, "DML-055", status="implemented"))
def list_recommendations(
    status: RecommendationStatus | None = Query(None),
    equipment_id: int | None = Query(None, ge=1),
    ctx: DemoContext = Depends(_read),
    db: Session = Depends(get_db),
):
    items = reco.list_recommendations(db, ctx, status, equipment_id)
    return RecommendationListResponse(items=items, total=len(items), as_of=ctx.as_of)


@router.post("/recommendations/{recommendation_id}/decision", response_model=RecommendationOut,
             summary="Human approve / reject (optionally create a work order); audited",
             openapi_extra=contract(P.recommendation_decide, OWNER, "DML-055", status="implemented"))
def decide_recommendation(
    body: RecommendationDecisionRequest,
    recommendation_id: int = Path(ge=1),
    ctx: DemoContext = Depends(require_permission(P.recommendation_decide)),
    db: Session = Depends(get_db),
):
    return reco.decide(db, ctx, recommendation_id, body)


@router.post("/impact", response_model=MaintenanceImpactResponse, summary="Downtime impact what-if with formulas and assumptions",
             openapi_extra=contract(P.scenario_calculate, OWNER, "DML-058", status="implemented"))
def maintenance_impact(
    body: MaintenanceImpactRequest,
    ctx: DemoContext = Depends(require_permission(P.scenario_calculate)),
    db: Session = Depends(get_db),
):
    return svc.impact(db, ctx, body)


@router.get("/downtime", response_model=DowntimeAnalysisResponse, summary="Downtime analysis by equipment, cause, hour of day",
            openapi_extra=contract(P.read_maintenance, OWNER, "DML-057", status="implemented"))
def downtime_analysis(period: Period = Query(Period.last_30d), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return svc.downtime_analysis(db, ctx, period)


@router.get("/technicians", response_model=TechnicianListResponse, summary="Technicians (fictional) and open assignments",
            openapi_extra=contract(P.read_maintenance, OWNER, "DML-056", status="implemented"))
def list_technicians(ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return svc.technicians(db, ctx)
