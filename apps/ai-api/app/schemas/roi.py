"""ROI & Value Simulator (owner: backend-b). Illustrative only; no double counting."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.schemas.common import ApiModel, Assumption, Disclaimer, ExportFormat, Formula, Provenance

ROI_DISCLAIMER = (
    "Illustrative business scenario based on adjustable assumptions, not verified financial results of any company."
)


class RoiCase(StrEnum):
    baseline = "baseline"
    conservative = "conservative"
    expected = "expected"
    optimistic = "optimistic"


class RoiInputs(ApiModel):
    daily_ffb_t: float = Field(gt=0, le=10000)
    operating_days: int = Field(gt=0, le=366)
    current_oer_pct: float = Field(gt=0, le=35)
    target_oer_pct: float = Field(gt=0, le=35)
    cpo_price_thb_per_kg: float = Field(gt=0, le=200)
    downtime_h_per_month: float = Field(ge=0, le=744)
    processing_capacity_tph: float = Field(gt=0, le=200)
    energy_cost_thb_per_year: float = Field(ge=0)
    maintenance_expense_thb_per_year: float = Field(ge=0)
    efficiency_improvement_pct: float = Field(ge=0, le=100, description="Applied to energy + maintenance cost")
    downtime_reduction_pct: float = Field(0, ge=0, le=100)
    implementation_cost_thb: float = Field(ge=0)
    recurring_cost_thb_per_year: float = Field(ge=0)


class RoiCaseResult(ApiModel):
    case: RoiCase
    additional_cpo_t: float
    gross_value_uplift_thb: float
    cost_avoidance_thb: float
    implementation_cost_thb: float
    annual_recurring_cost_thb: float
    net_benefit_year1_thb: float
    payback_months: float | None
    multipliers: dict[str, float] = Field(description="Case factors applied to the improvement assumptions")


class RoiResponse(ApiModel):
    inputs: RoiInputs
    cases: list[RoiCaseResult]
    formulas: list[Formula]
    assumptions: list[Assumption]
    double_counting_note: str = "OER uplift is applied to FFB processed at baseline availability; downtime recovery uses a separate base (recovered hours x capacity x current OER)."
    disclaimer: Disclaimer
    provenance: Provenance


class RoiDefaultsResponse(ApiModel):
    inputs: RoiInputs
    assumptions: list[Assumption]
    case_multipliers: dict[str, dict[str, float]]
    disclaimer: Disclaimer


class SensitivityRequest(ApiModel):
    inputs: RoiInputs
    variables: list[str] = Field(
        ["target_oer_pct", "cpo_price_thb_per_kg", "downtime_reduction_pct", "implementation_cost_thb"], max_length=12
    )
    swing_pct: float = Field(20, gt=0, le=100)


class SensitivityBar(ApiModel):
    variable: str
    low_value: float
    high_value: float
    net_benefit_low_thb: float
    net_benefit_high_thb: float
    note: str | None = Field(None, description="How the swing was applied (OER variables swing the improvement, not the OER level)")


class SensitivityResponse(ApiModel):
    base_net_benefit_thb: float
    bars: list[SensitivityBar] = Field(description="Tornado-chart ready, sorted by swing")
    provenance: Provenance


class RoiExportRequest(ApiModel):
    inputs: RoiInputs
    format: ExportFormat = ExportFormat.markdown


class PrintableDocument(ApiModel):
    """Self-contained printable HTML page returned as data (render in an iframe `srcdoc`, then print / save as PDF)."""

    report_type: str
    title: str
    filename: str
    media_type: str = "text/html"
    html: str = Field(description="Complete HTML document with print CSS and no scripts; every dynamic value is HTML-escaped")
    generated_at: datetime
    as_of: datetime
    disclaimers: list[Disclaimer]
