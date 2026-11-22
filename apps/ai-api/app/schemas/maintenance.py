"""Predictive Maintenance (owner: backend-b; health/risk scores produced by ml services)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import Field

from app.schemas.common import (
    ApiModel,
    Assumption,
    EntityRef,
    Evidence,
    Formula,
    HealthState,
    NormalRange,
    Provenance,
    Quantity,
    RecommendationStatus,
    Series,
    Severity,
    StageCode,
)


class HealthCriterion(ApiModel):
    """One explicit rule behind a health state (AI-C01: computed criteria, not random colours)."""

    sensor_code: str
    rule: str = Field(examples=["vibration_rms > warn_limit (7.1 mm/s) for >= 30 min"])
    observed: float | None
    limit: float | None
    unit: str
    breached: bool
    state_if_breached: HealthState
    # ---- additive (backend-b): the evidence behind the rule ----
    kind: str = Field("sensor_limit", description="sensor_limit | service_interval | open_alert")
    observed_ts: datetime | None = Field(None, description="Timestamp of the newest sample / event used")
    samples_evaluated: int | None = None
    samples_in_breach: int | None = None
    window_min: float | None = Field(None, description="Least severe value among the evaluated samples (persistence check)")
    window_max: float | None = None
    iso_zone: str | None = Field(None, description="ISO 10816-3 style vibration zone A/B/C/D (vibration sensors only)")
    note: str | None = None
    affects_state: bool = Field(True, description="False = informational evidence (feeds the risk index / recommendations, not the state)")


class RiskComponent(ApiModel):
    key: str
    label: str
    weight: float = Field(description="Maximum points this component can add (weights sum to 100)")
    sub_score: float = Field(description="0-1 component score")
    points: float
    basis: str


class EquipmentHealth(ApiModel):
    equipment_id: int
    state: HealthState
    criteria: list[HealthCriterion]
    anomaly_score: float | None = Field(None, description="0-1 from the equipment anomaly model")
    risk_score: float | None = Field(None, description="0-100 relative failure-risk score - NOT a calibrated probability")
    risk_meaning: str = "Relative ranking score from synthetic data; not a calibrated failure probability."
    provenance: Provenance
    # ---- additive (backend-b) ----
    equipment_code: str | None = None
    as_of: datetime | None = None
    state_rule: str | None = Field(None, description="How the final state was derived from the criteria (precedence)")
    triggered_by: list[str] = Field(default_factory=list, description="Criteria that determined the state (sensor codes / rule ids)")
    risk_components: list[RiskComponent] = Field(default_factory=list)
    risk_method: str | None = None
    risk_limits: str | None = None
    risk_band: str | None = Field(None, description="low | elevated | high | very_high - bands of a relative index, not probabilities")
    data_quality_notes: list[str] = Field(default_factory=list)
    maintenance_status: str | None = Field(None, description="none | work_order_open | assigned | in_progress | on_hold (this session, ADR-014)")
    active_work_order_ids: list[int] = Field(default_factory=list)
    health_rules_version: str | None = None


class EquipmentSummary(ApiModel):
    id: int
    code: str
    name: str
    equipment_type: str
    process_stage_code: StageCode
    criticality: str
    health_state: HealthState
    risk_score: float | None = None
    open_work_orders: int = 0
    active_alerts: int = 0
    # ---- additive (backend-b) ----
    maintenance_status: str = "none"
    triggered_by: list[str] = Field(default_factory=list)
    risk_band: str | None = None


class EquipmentListResponse(ApiModel):
    items: list[EquipmentSummary]
    total: int
    counts_by_state: dict[str, int]
    as_of: datetime
    provenance: Provenance | None = None
    health_rules_version: str | None = None


class SensorInfo(ApiModel):
    id: int
    code: str
    name: str
    sensor_type: str
    unit: str
    latest: Quantity | None = None
    normal_range: NormalRange | None = None
    warn_limit: float | None = None
    crit_limit: float | None = None


class EquipmentDetail(ApiModel):
    id: int
    code: str
    name: str
    equipment_type: str
    process_stage_code: StageCode
    criticality: str
    manufacturer: str | None = None
    install_date: date | None = None
    rated_power_kw: float | None = None
    sensors: list[SensorInfo]
    health: EquipmentHealth
    running_hours: float | None = None
    last_maintenance_at: datetime | None = None
    # ---- additive (backend-b) ----
    maintenance_status: str = "none"
    active_work_order_ids: list[int] = Field(default_factory=list)
    days_since_last_service: float | None = None
    service_interval: str | None = None


class MaintenanceEventOut(ApiModel):
    id: int
    event_type: str
    start_ts: datetime
    end_ts: datetime | None
    downtime_min: float
    planned: bool
    description: str | None
    work_order_id: int | None = None
    cost_thb: float | None = None


class MaintenanceHistoryResponse(ApiModel):
    equipment_id: int
    items: list[MaintenanceEventOut]
    total_downtime_h: float
    mtbf_h: float | None = Field(None, description="Mean time between failures over the window (synthetic)")
    mttr_h: float | None = None
    # ---- additive (backend-b) ----
    period: str | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    failures: int = 0
    total_cost_thb: float | None = None
    mtbf_basis: str | None = None
    provenance: Provenance | None = None


class SensorLimits(ApiModel):
    warn_limit: float | None = None
    crit_limit: float | None = None
    low_is_bad: bool = False


class SeriesMarker(ApiModel):
    kind: str = Field(description="anomaly | alert")
    id: int
    code: str
    start_ts: datetime
    end_ts: datetime | None = None
    peak_ts: datetime | None = None
    severity: str | None = None
    score: float | None = None
    label: str | None = None
    sensor_code: str | None = None


class SensorSeriesResponse(ApiModel):
    equipment_id: int
    resolution: str = Field(description="raw | 10min | hour | day (server-side downsampling)")
    series: list[Series]
    normal_ranges: dict[str, NormalRange]
    # ---- additive (backend-b) ----
    start: datetime | None = None
    end: datetime | None = None
    requested_resolution: str | None = None
    aggregation: str = "mean"
    limits: dict[str, SensorLimits] = Field(default_factory=dict)
    anomaly_markers: list[SeriesMarker] = Field(default_factory=list, description="From anomaly_events (empty until the ML pipeline has run)")
    alert_markers: list[SeriesMarker] = Field(default_factory=list, description="Threshold alerts raised on this equipment within the window")
    note: str | None = None


class RecommendationOut(ApiModel):
    id: int
    code: str
    rec_type: str
    title: str
    rationale: str
    priority: Severity
    risk_score: float | None = None
    advisory: bool = Field(True, description="Always true: AI recommendations are advisory, humans decide")
    status: RecommendationStatus
    equipment: EntityRef | None = None
    process_stage_code: StageCode | None = None
    anomaly_event_id: int | None = None
    evidence: list[Evidence] = []
    created_at: datetime
    decided_by_role: str | None = None
    decided_at: datetime | None = None
    work_order_id: int | None = None
    model_version: str | None = None
    # ---- additive (backend-b) ----
    rule_id: str | None = None
    corroborating_sensors: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    advisory_notice: str = "Advisory only - verify by a qualified engineer. Nothing here is sent to or executed on any machine."
    decision_note: str | None = None
    generated_for_as_of: datetime | None = None
    source: str = Field("rule_engine", description="rule_engine (computed at the demo clock) | seeded")


class RecommendationListResponse(ApiModel):
    items: list[RecommendationOut]
    total: int
    as_of: datetime | None = None
    notice: str = "Recommendations are advisory and generated from threshold/trend rules over synthetic data. A human decision is required; AI never controls machines."


class RecommendationDecisionRequest(ApiModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    note: str | None = Field(None, max_length=1000)
    create_work_order: bool = Field(False, description="If approved, also create a work order (human-confirmed)")


class MaintenanceImpactRequest(ApiModel):
    equipment_id: int | None = None
    downtime_hours: float = Field(ge=0, le=720)
    throughput_tph: float | None = Field(None, gt=0, le=200, description="Default: recent average")
    oer_pct: float | None = Field(None, gt=0, le=35)
    cpo_price_thb_per_kg: float | None = Field(None, gt=0, le=200)
    maintenance_cost_thb: float | None = Field(None, ge=0)
    planned: bool = Field(False, description="Planned stop (can be scheduled into low-intake hours) vs breakdown")
    recovery_hours: float | None = Field(None, ge=0, le=720, description="Extra hours to recover backlog")
    capacity_loss_fraction: float | None = Field(
        None, ge=0, le=1, description="Share of mill throughput lost while the equipment is down (default derived from its parallel group)"
    )


class ImpactScenario(ApiModel):
    key: str = Field(description="planned_stop | run_to_failure")
    label: str
    lost_ffb_processing_t: float
    lost_cpo_opportunity_t: float
    lost_value_thb: float
    maintenance_cost_thb: float
    total_impact_thb: float
    description: str


class MaintenanceImpactResponse(ApiModel):
    lost_ffb_processing_t: float
    lost_cpo_opportunity_t: float
    lost_value_thb: float
    maintenance_cost_thb: float
    total_impact_thb: float
    recovery_scenario: str
    formulas: list[Formula]
    assumptions: list[Assumption]
    required_real_data: list[str] = Field(description="What a real plant would need to make this estimate reliable")
    provenance: Provenance
    # ---- additive (backend-b) ----
    comparison: list[ImpactScenario] = Field(default_factory=list, description="Planned stop vs run-to-failure, same inputs")
    equipment_code: str | None = None
    notice: str = "What-if estimate on synthetic data with adjustable assumptions - not a prediction and not verified plant financials."


class DowntimeBucket(ApiModel):
    key: str
    label: str
    downtime_h: float
    events: int


class DowntimeAnalysisResponse(ApiModel):
    total_downtime_h: float
    availability_pct: float | None
    by_equipment: list[DowntimeBucket]
    by_cause: list[DowntimeBucket]
    by_hour_of_day: list[DowntimeBucket]
    series: Series
    provenance: Provenance


class TechnicianOut(ApiModel):
    id: int
    code: str
    display_name: str
    skill: str
    shift_code: str | None
    open_assignments: int = 0


class TechnicianListResponse(ApiModel):
    items: list[TechnicianOut]
