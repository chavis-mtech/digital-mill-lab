"""Energy & Sustainability (SPEC 4.E). Owner: backend-a."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1._contract import STD_RESPONSES, contract
from app.db.session import get_db
from app.deps import require_permission
from app.errors import bad_request
from app.schemas.common import Granularity, Period
from app.schemas.energy import EnergySeriesResponse, EnergySummaryResponse, EnergyWhatIfRequest, EnergyWhatIfResponse
from app.services import energy
from app.services.demo_context import DemoContext
from app.services.rbac import Permission as P

OWNER = "backend-a"
router = APIRouter(prefix="/energy", tags=["energy"], responses=STD_RESPONSES)
_read = require_permission(P.read_energy)


@router.get("/summary", response_model=EnergySummaryResponse, summary="Energy KPIs (kWh/t, steam/t, water/t, cost/t) and stage breakdown",
            openapi_extra=contract(P.read_energy, OWNER, "DML-065", status="implemented"))
def energy_summary(period: Period = Query(Period.today), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    if period == Period.custom:
        bad_request("invalid_period", "Use today, 7d or 30d")
    return energy.summary(db, ctx, period)


@router.get("/series", response_model=EnergySeriesResponse, summary="Energy time-series",
            openapi_extra=contract(P.read_energy, OWNER, "DML-066", status="implemented"))
def energy_series(
    metric: str = Query("kwh_per_t_ffb", pattern="^(electricity_kwh|kwh_per_t_ffb|steam_t|water_m3|cost_thb|grid_import_kwh|idle_kwh)$"),
    period: Period = Query(Period.last_30d),
    granularity: Granularity = Query(Granularity.day),
    ctx: DemoContext = Depends(_read),
    db: Session = Depends(get_db),
):
    return energy.series(db, ctx, metric, period, granularity.value)


@router.post("/what-if", response_model=EnergyWhatIfResponse, summary="Energy what-if (efficiency, idle, energy mix) with limits",
             openapi_extra=contract(P.scenario_calculate, OWNER, "DML-069", status="implemented"))
def energy_what_if(
    body: EnergyWhatIfRequest,
    ctx: DemoContext = Depends(require_permission(P.scenario_calculate)),
    db: Session = Depends(get_db),
):
    return energy.what_if(db, ctx, body)
