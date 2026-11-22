"""Energy & Sustainability (owner: backend-a)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import ApiModel, Assumption, Formula, KpiValue, Provenance, Series


class EnergyBreakdownItem(ApiModel):
    key: str
    label: str
    kwh: float | None
    share_pct: float | None


class EnergyMarker(ApiModel):
    """Production-adjusted abnormal-consumption marker (statistical baseline; not the ML model)."""

    t: datetime
    actual_kwh: float | None
    expected_kwh: float | None
    z_score: float | None
    ffb_processed_t: float | None
    hours: int
    abnormal: bool
    severity: str | None = None
    basis: str


class EnergySummaryResponse(ApiModel):
    kpis: list[KpiValue] = Field(
        description="electricity_kwh, kwh_per_t_ffb, steam_t_per_t_ffb, water_m3_per_t_ffb, energy_cost_thb_per_t, "
        "grid_import_share_pct, idle_kwh"
    )
    by_stage: list[EnergyBreakdownItem]
    provenance: Provenance
    sources: list[EnergyBreakdownItem] = Field(default_factory=list, description="Electricity by source: grid import vs self-generated")
    fuels: list[KpiValue] = Field(default_factory=list, description="Diesel L, biomass t (fibre + shell), steam t")
    abnormal_days: list[EnergyMarker] = Field(default_factory=list)
    method: str | None = None


class EnergySeriesResponse(ApiModel):
    metric: str
    granularity: str
    series: list[Series]
    markers: list[EnergyMarker] = Field(default_factory=list, description="Daily production-adjusted z-score markers")


class EnergyWhatIfRequest(ApiModel):
    efficiency_improvement_pct: float = Field(0, ge=0, le=50)
    idle_reduction_pct: float = Field(0, ge=0, le=100)
    grid_import_reduction_pct: float = Field(0, ge=0, le=100, description="Shift to self-generated (biomass) power")
    electricity_tariff_thb_per_kwh: float | None = Field(None, gt=0, le=20)
    biogas_capture: bool = False
    days: int = Field(365, ge=1, le=366)


class EnergyWhatIfResponse(ApiModel):
    baseline_kwh: float
    scenario_kwh: float
    saving_kwh: float
    saving_thb: float
    kwh_per_t_before: float | None
    kwh_per_t_after: float | None
    grid_import_before_kwh: float | None = None
    grid_import_after_kwh: float | None = None
    biogas_kwh: float | None = None
    formulas: list[Formula]
    assumptions: list[Assumption]
    limits: list[str] = Field(description="What this estimate cannot conclude (no unsupported engineering/environment claims)")
    provenance: Provenance
