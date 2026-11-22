"""Shared API types (architect-owned). Module schemas compose these; keep changes additive.

Glossary (see docs/architecture/API_CONTRACT.md):
- Provenance: required on every numeric payload -> UI badge (synthetic_actual | forecast | what_if).
- SeriesPoint {t, v}: chart-ready point; t is ISO-8601 UTC.
- Series: one named line with unit + provenance; optional lower/upper band for forecasts.
- KpiValue: current vs previous period with delta and "good direction".
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    AlertSource,
    AlertStatus,
    AnomalyStatus,
    HealthState,
    ProvenanceKind,
    RecommendationStatus,
    Role,
    ScenarioCode,
    Severity,
    StageCode,
    WorkOrderPriority,
    WorkOrderSource,
    WorkOrderStatus,
)

__all__ = [
    "AlertSource",
    "AlertStatus",
    "AnomalyStatus",
    "HealthState",
    "ProvenanceKind",
    "RecommendationStatus",
    "Role",
    "ScenarioCode",
    "Severity",
    "StageCode",
    "WorkOrderPriority",
    "WorkOrderSource",
    "WorkOrderStatus",
]

T = TypeVar("T")


class ApiModel(BaseModel):
    """Base for all response/request models: snake_case JSON, ORM-friendly, ignores nothing silently."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ---------------------------------------------------------------------------- errors
class ErrorBody(ApiModel):
    code: str = Field(examples=["not_implemented"])
    message: str
    details: Any | None = None


class ErrorEnvelope(ApiModel):
    error: ErrorBody


# ---------------------------------------------------------------------------- provenance & status
class Provenance(ApiModel):
    kind: ProvenanceKind
    source: str = Field(description="Table, service or model that produced the number", examples=["process_hourly"])
    as_of: datetime = Field(description="Demo clock the number was computed for (UTC)")
    model_version: str | None = Field(None, description="Model name@version for forecasts / AI outputs")


class FeatureStatus(StrEnum):
    implemented = "implemented"
    partial = "partial"
    prototype = "prototype"
    planned = "planned"


class FactTag(StrEnum):
    """SPEC fact taxonomy for assumptions and business statements."""

    verified_public_fact = "verified_public_fact"
    historical_public_information = "historical_public_information"
    industry_practice = "industry_practice"
    engineering_assumption = "engineering_assumption"
    synthetic_demonstration_data = "synthetic_demonstration_data"
    proposed_future_capability = "proposed_future_capability"


class Period(StrEnum):
    today = "today"
    last_7d = "7d"
    last_30d = "30d"
    custom = "custom"


class Granularity(StrEnum):
    hour = "hour"
    shift = "shift"
    day = "day"
    week = "week"


class TrendDirection(StrEnum):
    up = "up"
    down = "down"
    flat = "flat"


class ExportFormat(StrEnum):
    json = "json"
    csv = "csv"
    markdown = "markdown"


# ---------------------------------------------------------------------------- numbers & series
class Quantity(ApiModel):
    value: float | None
    unit: str
    provenance: Provenance


class SeriesPoint(ApiModel):
    t: datetime
    v: float | None


class BandPoint(ApiModel):
    t: datetime
    v: float | None
    lower: float | None = None
    upper: float | None = None


class Series(ApiModel):
    key: str
    label: str
    unit: str
    points: list[SeriesPoint]
    provenance: Provenance


class BandSeries(ApiModel):
    key: str
    label: str
    unit: str
    points: list[BandPoint]
    interval: str | None = Field(None, description="e.g. 'P10-P90 empirical residual quantiles'")
    provenance: Provenance


class NormalRange(ApiModel):
    low: float | None = None
    high: float | None = None
    unit: str
    basis: str = Field(description="How the range was derived, e.g. 'design spec (engineering assumption)' or 'P5-P95 of last 30 normal days'")


class KpiValue(ApiModel):
    key: str = Field(examples=["oer_pct"])
    label: str
    value: float | None
    unit: str
    previous: float | None = None
    delta: float | None = None
    delta_pct: float | None = None
    good_direction: TrendDirection = TrendDirection.up
    status: Severity | None = Field(None, description="Severity if the KPI breaches a threshold")
    target: float | None = None
    provenance: Provenance


class Formula(ApiModel):
    """A calculation shown to the user: expression, named inputs, result (spec: formulas echoed)."""

    key: str
    label: str
    expression: str = Field(examples=["delta_cpo_t = ffb_t * delta_oer_pp / 100"])
    inputs: dict[str, float | str | None]
    result: float | None
    unit: str


class Assumption(ApiModel):
    key: str
    label: str
    value: float | str | None
    unit: str | None = None
    tag: FactTag
    source: str | None = Field(None, description="Reference (docs/business/... or URL) for the value")
    editable: bool = True


class EntityRef(ApiModel):
    type: str = Field(examples=["equipment"])
    id: int | str
    code: str | None = None
    label: str | None = None


class Evidence(ApiModel):
    """Observed signal supporting an insight/anomaly. Never a proven cause."""

    metric: str
    label: str
    observed: float | None
    expected: float | None = None
    normal_range: NormalRange | None = None
    unit: str
    window_start: datetime | None = None
    window_end: datetime | None = None
    entity: EntityRef | None = None
    note: str | None = None


class Disclaimer(ApiModel):
    key: str
    text_en: str
    text_th: str | None = None


class Page(ApiModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class Ack(ApiModel):
    ok: bool = True
    message: str | None = None


class DemoContextOut(ApiModel):
    as_of: datetime
    as_of_explicit: bool
    scenario_id: ScenarioCode | None
    session_id: str | None
    role: Role
    window_start: datetime
    window_end: datetime
    timezone: str
    business_date: date


class ReportDocument(ApiModel):
    """Exported report. `content` holds the serialised body (json/csv/markdown text)."""

    report_type: str
    title: str
    format: ExportFormat
    generated_at: datetime
    as_of: datetime
    filename: str
    content: str
    disclaimers: list[Disclaimer]
