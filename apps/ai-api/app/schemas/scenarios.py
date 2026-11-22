"""Scenario catalog (deterministic episodes) and production what-if (owner: backend-b)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import ApiModel, Assumption, Formula, KpiValue, Provenance, ScenarioCode, StageCode


class ExpectedEffect(ApiModel):
    """A MEASURED effect (computed from the synthetic data at focus_ts vs baseline_ts) - never the designed-intent text."""

    module: str = Field(examples=["process_twin", "production_kpi", "anomaly", "maintenance_alert", "copilot", "impact"])
    description: str
    entity_code: str | None = None
    # ---- additive (backend-b) ----
    metric: str | None = None
    focus_value: float | None = None
    baseline_value: float | None = None
    delta: float | None = None
    unit: str | None = None
    significance: str | None = Field(None, description="How the change compares with normal day-to-day variation (robust sd of the 28 previous days)")
    basis: str | None = None


class ScenarioOut(ApiModel):
    code: ScenarioCode
    name_en: str
    name_th: str
    description: str
    start_ts: datetime
    end_ts: datetime
    focus_ts: datetime = Field(description="Send as as_of to 'activate' this scenario (stateless playback, ADR-005)")
    baseline_ts: datetime | None = None
    primary_stage_code: StageCode | None = None
    primary_equipment_code: str | None = None
    expected_effects: list[ExpectedEffect]
    # ---- additive (backend-b) ----
    activate_as_of: datetime | None = Field(None, description="= focus_ts; send as as_of (or send scenario_id) to activate")
    activate_query: str | None = None
    highlights_available: bool = Field(True, description="False when focus_ts is after the current demo clock (no future data is read)")
    highlights_note: str | None = None
    window_local: str | None = None
    data_basis: str = "Effects are measured from the synthetic data at focus_ts versus baseline_ts (same hours of day); the scenario's designed-intent text is not used."


class ScenarioCatalogResponse(ApiModel):
    items: list[ScenarioOut]
    playback_presets: list[str] = ["today", "last_7_days", "last_30_days", "scenario_date", "simulated_live"]


class ProductionWhatIfRequest(ApiModel):
    ffb_intake_t_per_day: float | None = Field(None, gt=0, le=10000)
    oer_pct: float | None = Field(None, gt=0, le=35)
    availability_pct: float | None = Field(None, gt=0, le=100)
    processing_hours_per_day: float | None = Field(None, gt=0, le=24)
    energy_cost_thb_per_kwh: float | None = Field(None, gt=0, le=20)
    oil_loss_pct: float | None = Field(None, ge=0, le=10)
    cpo_price_thb_per_kg: float | None = Field(None, gt=0, le=200)
    days: int = Field(30, ge=1, le=366)


class ProductionWhatIfResponse(ApiModel):
    baseline: list[KpiValue]
    scenario: list[KpiValue]
    delta: list[KpiValue]
    formulas: list[Formula]
    assumptions: list[Assumption]
    calculation_example: str = "Calculation example: 1,000 t FFB x +0.5 pp OER = +5 t CPO"
    provenance: Provenance
    # ---- additive (backend-b) ----
    baseline_inputs: dict = Field(default_factory=dict, description="Defaults derived from the trailing 30 days at the demo clock")
    inputs_used: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    horizon_days: int | None = None


class SavedScenarioRequest(ApiModel):
    kind: str = Field(pattern="^(production|maintenance|energy|roi|queue)$")
    name: str = Field(min_length=1, max_length=120)
    inputs: dict
    outputs: dict


class SavedScenarioOut(ApiModel):
    id: int
    kind: str
    name: str
    inputs: dict
    outputs: dict
    created_at: datetime
    demo_as_of: datetime | None = None


class SavedScenarioListResponse(ApiModel):
    items: list[SavedScenarioOut]
