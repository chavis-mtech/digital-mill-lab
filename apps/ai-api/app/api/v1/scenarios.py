"""Scenario catalog + production what-if + saved scenarios. Owner: backend-b.

Maintenance-impact and energy what-ifs live at POST /maintenance/impact and POST /energy/what-if
(the Scenario Simulator page calls those); they are not duplicated here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.api.v1._contract import STD_RESPONSES, contract
from app.db.session import get_db
from app.deps import require_permission
from app.schemas.common import ScenarioCode
from app.schemas.scenarios import (
    ProductionWhatIfRequest,
    ProductionWhatIfResponse,
    SavedScenarioListResponse,
    SavedScenarioOut,
    SavedScenarioRequest,
    ScenarioCatalogResponse,
    ScenarioOut,
)
from app.services import scenarios as svc
from app.services.demo_context import DemoContext
from app.services.rbac import Permission as P

OWNER = "backend-b"
router = APIRouter(prefix="/scenarios", tags=["scenarios"], responses=STD_RESPONSES)


@router.get("", response_model=ScenarioCatalogResponse, summary="Deterministic scenario catalog (activate by sending focus_ts as as_of)",
            openapi_extra=contract(P.read_executive, OWNER, "DML-087", status="implemented"))
def list_scenarios(ctx: DemoContext = Depends(require_permission(P.read_executive)), db: Session = Depends(get_db)):
    return svc.catalog(db, ctx)


@router.get("/saved", response_model=SavedScenarioListResponse, summary="What-if runs saved in this session",
            openapi_extra=contract(P.scenario_calculate, OWNER, "DML-087", status="implemented"))
def list_saved(
    kind: str | None = Query(None, pattern="^(production|maintenance|energy|roi|queue)$"),
    ctx: DemoContext = Depends(require_permission(P.scenario_calculate)),
    db: Session = Depends(get_db),
):
    return svc.list_saved(db, ctx, kind)


@router.post("/saved", response_model=SavedScenarioOut, status_code=201, summary="Save a what-if run (session-scoped)",
             openapi_extra=contract(P.scenario_save, OWNER, "DML-087", status="implemented"))
def save_scenario(
    body: SavedScenarioRequest,
    ctx: DemoContext = Depends(require_permission(P.scenario_save)),
    db: Session = Depends(get_db),
):
    return svc.save_scenario(db, ctx, body)


@router.post("/production/calculate", response_model=ProductionWhatIfResponse, summary="Production what-if, recomputed with formulas echoed",
             openapi_extra=contract(P.scenario_calculate, OWNER, "DML-050", status="implemented"))
def production_what_if(
    body: ProductionWhatIfRequest,
    ctx: DemoContext = Depends(require_permission(P.scenario_calculate)),
    db: Session = Depends(get_db),
):
    return svc.production_what_if(db, ctx, body)


@router.get("/{code}", response_model=ScenarioOut, summary="Scenario detail: window, focus time, expected cross-module effects",
            openapi_extra=contract(P.read_executive, OWNER, "DML-087", status="implemented"))
def get_scenario(code: ScenarioCode = Path(), ctx: DemoContext = Depends(require_permission(P.read_executive)), db: Session = Depends(get_db)):
    return svc.get_scenario(db, ctx, code)
