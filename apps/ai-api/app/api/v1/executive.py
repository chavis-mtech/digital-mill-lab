"""Executive Industrial Control Tower (SPEC 4.A). Owner: backend-a."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1._contract import STD_RESPONSES, contract
from app.db.session import get_db
from app.deps import require_permission
from app.schemas.common import Granularity, Period
from app.schemas.executive import (
    AiInsightSummaryResponse,
    BottleneckOverviewResponse,
    CostProductivityResponse,
    ExecutiveKpisResponse,
    ExecutiveOverviewResponse,
    KpiSeriesResponse,
    ScenarioComparisonResponse,
)
from app.services import kpi, kpi_alerts, kpi_insights
from app.services.demo_context import DemoContext
from app.services.rbac import Permission as P

OWNER = "backend-a"
router = APIRouter(prefix="/executive", tags=["executive"], responses=STD_RESPONSES)
_read = require_permission(P.read_executive)


@router.get("/overview", response_model=ExecutiveOverviewResponse, summary="Dashboard first paint: KPIs + top alerts + insight",
            openapi_extra=contract(P.read_executive, OWNER, "DML-036", status="implemented"))
def get_overview(period: Period = Query(Period.today), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    if period == Period.custom:
        from app.errors import bad_request  # noqa: PLC0415

        bad_request("invalid_period", "Use /executive/kpis for custom windows")
    k = kpi.executive_kpis(db, ctx, period)
    k["sparklines"] = kpi.sparklines(db, ctx)
    alerts = kpi_alerts.list_alerts(db, ctx, active_only=True, limit=5)["items"]
    return {"kpis": k, "top_alerts": alerts, "insight": kpi_insights.insights(db, ctx), "impact_cards": kpi.impact_cards(db, ctx, period)}


@router.get("/kpis", response_model=ExecutiveKpisResponse, summary="12 control-tower KPIs, current vs previous period",
            openapi_extra=contract(P.read_executive, OWNER, "DML-035", status="implemented"))
def get_kpis(
    period: Period = Query(Period.today),
    start: date | None = Query(None, description="Required when period=custom"),
    end: date | None = Query(None, description="Required when period=custom"),
    ctx: DemoContext = Depends(_read),
    db: Session = Depends(get_db),
):
    return kpi.executive_kpis(db, ctx, period, start, end)


@router.get("/series", response_model=KpiSeriesResponse, summary="KPI time-series for trend charts / drill-down",
            openapi_extra=contract(P.read_executive, OWNER, "DML-037", status="implemented"))
def get_series(
    metric: str = Query(..., max_length=64, description="A KPI key from /executive/kpis"),
    period: Period = Query(Period.last_30d),
    granularity: Granularity = Query(Granularity.day),
    compare_previous: bool = Query(False),
    ctx: DemoContext = Depends(_read),
    db: Session = Depends(get_db),
):
    return kpi.kpi_series(db, ctx, metric, period, granularity.value, compare_previous)


@router.get("/insights", response_model=AiInsightSummaryResponse, summary="AI insight summary: what is abnormal, impact, who checks first",
            openapi_extra=contract(P.read_executive, OWNER, "DML-040", status="implemented"))
def get_insights(ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return kpi_insights.insights(db, ctx)


@router.get("/bottlenecks", response_model=BottleneckOverviewResponse, summary="Bottleneck overview by process stage",
            openapi_extra=contract(P.read_executive, OWNER, "DML-036", status="implemented"))
def get_bottlenecks(period: Period = Query(Period.today), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    if period == Period.custom:
        from app.errors import bad_request  # noqa: PLC0415

        bad_request("invalid_period", "Use today, 7d or 30d")
    return kpi_insights.bottlenecks(db, ctx, period)


@router.get("/cost-productivity", response_model=CostProductivityResponse, summary="Cost & productivity analysis (illustrative)",
            openapi_extra=contract(P.read_executive, OWNER, "DML-041", status="implemented"))
def get_cost_productivity(period: Period = Query(Period.last_30d), ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    if period == Period.custom:
        from app.errors import bad_request  # noqa: PLC0415

        bad_request("invalid_period", "Use today, 7d or 30d")
    return kpi.cost_productivity(db, ctx, period)


@router.get("/scenario-comparison", response_model=ScenarioComparisonResponse, summary="KPIs per scenario vs NORMAL_DAY",
            openapi_extra=contract(P.read_executive, OWNER, "DML-041", status="implemented"))
def get_scenario_comparison(ctx: DemoContext = Depends(_read), db: Session = Depends(get_db)):
    return kpi.scenario_comparison(db, ctx)
