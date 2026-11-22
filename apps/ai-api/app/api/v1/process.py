"""Industrial Digital Twin Lite - process flow (SPEC 4 / DML-079..081). Owner: backend-a."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.api.v1._contract import STD_RESPONSES, contract
from app.db.session import get_db
from app.deps import require_permission
from app.schemas.common import StageCode
from app.schemas.process import ProcessStageListResponse, StageDetailResponse
from app.services import production_process
from app.services.demo_context import DemoContext
from app.services.rbac import Permission as P

OWNER = "backend-a"
router = APIRouter(prefix="/process", tags=["process"], responses=STD_RESPONSES)
_read = require_permission(P.read_production)


@router.get("/stages", response_model=ProcessStageListResponse, summary="Process stages with live state + material-flow edges",
            openapi_extra=contract(P.read_production, OWNER, "DML-079", status="implemented"))
def list_stages(ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return production_process.list_stages(db, ctx)


@router.get("/stages/{stage_code}", response_model=StageDetailResponse, summary="Stage detail: equipment, sensors, KPIs, alerts, recommendations",
            openapi_extra=contract(P.read_production, OWNER, "DML-080", status="implemented"))
def get_stage(stage_code: StageCode = Path(), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return production_process.stage_detail(db, ctx, stage_code.value)
