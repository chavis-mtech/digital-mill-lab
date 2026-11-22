"""Executive Control Tower (owner: backend-a)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.alerts import AlertOut
from app.schemas.common import (
    ApiModel,
    EntityRef,
    Evidence,
    Formula,
    KpiValue,
    Period,
    Provenance,
    ScenarioCode,
    Series,
    SeriesPoint,
    Severity,
)


class ExecutiveKpisResponse(ApiModel):
    """The 12 control-tower KPIs (SPEC 4.A), current vs previous period."""

    period: Period
    period_start: datetime
    period_end: datetime
    previous_start: datetime
    previous_end: datetime
    kpis: list[KpiValue] = Field(
        description="keys: ffb_received_t, ffb_processed_t, cpo_produced_t, oer_pct, ker_pct, throughput_tph, "
        "equipment_availability_pct, plant_downtime_h, energy_kwh_per_t, est_production_cost_thb_per_t, "
        "active_maintenance_alerts, logistics_queue_time_min"
    )
    oer_baseline_pct: float | None = Field(None, description="Trailing 28-day OER (ratio of sums) before the period - status reference")
    definitions_ref: str | None = Field(None, description="Where each KPI formula is documented")
    sparklines: dict[str, list[SeriesPoint]] = Field(default_factory=dict, description="Daily values of each KPI over the last 14 days")


class KpiSeriesResponse(ApiModel):
    metric: str
    granularity: str
    series: list[Series] = Field(description="Primary series plus optional comparison (previous period / target)")


class InsightItem(ApiModel):
    headline: str
    detail: str
    severity: Severity
    evidence: list[Evidence]
    suggested_team: str | None = None
    suggested_decision: str | None = None
    related: list[EntityRef] = []


class AiInsightSummaryResponse(ApiModel):
    """'What is abnormal today, how much does it affect business, which team checks first, what to decide.'"""

    generated_by: str = Field(description="deterministic_rules | model name; never an unlabelled LLM guess")
    summary: str
    items: list[InsightItem]
    provenance: Provenance
    method: str | None = None


class BottleneckStage(ApiModel):
    stage_code: str
    label: str
    utilisation_pct: float | None
    capacity_tph: float | None
    actual_tph: float | None
    downtime_h: float | None
    is_bottleneck: bool
    reason: str | None = None


class BottleneckOverviewResponse(ApiModel):
    stages: list[BottleneckStage]
    provenance: Provenance
    method: str | None = None


class CostLine(ApiModel):
    key: str
    label: str
    thb_per_t_ffb: float | None
    total_thb: float | None
    share_pct: float | None


class CostProductivityResponse(ApiModel):
    period: Period
    cost_lines: list[CostLine]
    productivity: list[KpiValue]
    note: str = "Illustrative cost model on synthetic data; not any company's financial results."
    provenance: Provenance


class ScenarioComparisonRow(ApiModel):
    scenario_code: ScenarioCode
    label: str
    kpis: list[KpiValue]
    focus_day: str | None = None


class ScenarioComparisonResponse(ApiModel):
    baseline: ScenarioCode = ScenarioCode.NORMAL_DAY
    rows: list[ScenarioComparisonRow]
    note: str | None = None


class ImpactCard(ApiModel):
    """Business-impact estimate (what_if) with its formula."""

    key: str
    label: str
    value: float | None
    unit: str
    formula: Formula
    provenance: Provenance


class ExecutiveOverviewResponse(ApiModel):
    """One-call payload for the dashboard first paint (KPIs + top alerts + insight headline)."""

    kpis: ExecutiveKpisResponse
    top_alerts: list[AlertOut]
    insight: AiInsightSummaryResponse | None
    impact_cards: list[ImpactCard] = []
