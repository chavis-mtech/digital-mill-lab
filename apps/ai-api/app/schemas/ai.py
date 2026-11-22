"""AI endpoints: forecasts, anomalies, failure risk, model cards (owner: ml).

Honesty: metrics are measured on temporal hold-outs of synthetic data and always shown next to a naive baseline.
Anomaly outputs list *possible contributing factors*, never a proven cause.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import (
    AnomalyStatus,
    ApiModel,
    BandSeries,
    EntityRef,
    Evidence,
    FeatureStatus,
    Provenance,
    ScenarioCode,
    Series,
    Severity,
    StageCode,
)


class MetricValue(ApiModel):
    name: str = Field(examples=["mae"])
    model: float | None
    baseline: float | None = None
    baseline_name: str | None = Field(None, examples=["naive_last_value", "seasonal_naive_7d"])
    better_is: str = "lower"
    beats_baseline: bool | None = None


class ModelInfo(ApiModel):
    name: str
    version: str
    task: str
    algorithm: str
    trained_at: datetime | None
    train_window: list[datetime] = []
    test_window: list[datetime] = []
    metrics: list[MetricValue]
    status: str
    data_kind: str = "synthetic"


class ModelCard(ModelInfo):
    purpose: str
    input_features: list[str]
    training_data: str
    synthetic_data_assumptions: list[str]
    evaluation_method: str
    limitations: list[str]
    known_failure_modes: list[str]
    deployment_status: FeatureStatus
    card_markdown: str | None = None


class ModelCardListResponse(ApiModel):
    items: list[ModelCard]


class OerForecastResponse(ApiModel):
    horizon_h: int
    forecast: BandSeries
    actual: Series = Field(description="Actuals up to as_of (never beyond)")
    baseline: Series = Field(description="Naive baseline forecast over the same horizon")
    model: ModelInfo
    granularity_note: str | None = None


class FeatureContribution(ApiModel):
    feature: str
    label: str
    value: float | None
    contribution: float | None = Field(None, description="Signed contribution in OER pp (permutation / partial dependence)")
    importance: float | None = Field(None, description="Global importance (0-1)")


class OerNowcast(ApiModel):
    """'Expected OER given current conditions' (day level) and the residual actual - expected (additive, ml)."""

    granularity: str = "day"
    period_start: datetime
    period_end: datetime
    running_hours: int
    actual_oer_pct: float | None
    expected_oer_pct: float | None
    typical_conditions_oer_pct: float | None = Field(None, description="Prediction at average training conditions")
    residual_pp: float | None
    residual_band_pp: float | None = Field(None, description="90% split-conformal band for the residual")
    outside_band: bool | None = None
    contributions: list[FeatureContribution] = []
    note: str


class OerExplanationResponse(ApiModel):
    target_ts: datetime
    predicted_oer_pct: float | None
    expected_range: list[float] = Field([], description="[lower, upper] uncertainty interval")
    contributions: list[FeatureContribution]
    method: str = Field(examples=["permutation_importance + local perturbation"])
    caveat: str = "Associations learned from synthetic data; not proven causes."
    model: ModelInfo
    nowcast: OerNowcast | None = None
    granularity_note: str | None = None


class AnomalyOut(ApiModel):
    id: int
    code: str
    detector: str
    domain: str
    entity: EntityRef | None = None
    equipment: EntityRef | None = None
    process_stage_code: StageCode | None = None
    start_ts: datetime
    end_ts: datetime | None
    peak_ts: datetime | None = None
    score: float = Field(ge=0, le=1)
    severity: Severity
    status: AnomalyStatus = Field(description="Effective human-verification status for this session")
    evidence: list[Evidence]
    contributing_factors: list[str] = Field([], description="Possible contributing factors - not proven causes")
    recommended_investigation: list[str] = []
    contributing_sensors: list[str] = []
    scenario_code: ScenarioCode | None = None
    model_version: str | None = None


class AnomalyListResponse(ApiModel):
    items: list[AnomalyOut]
    total: int
    score_series: Series | None = Field(None, description="Anomaly score over time for the window, if applicable")


class AnomalyStatusRequest(ApiModel):
    to_status: AnomalyStatus
    note: str | None = Field(None, max_length=1000)


class FailureRiskItem(ApiModel):
    equipment: EntityRef
    risk_score: float = Field(ge=0, le=100)
    rank: int
    drivers: list[Evidence]
    horizon_days: int | None = None


class FailureRiskResponse(ApiModel):
    items: list[FailureRiskItem]
    meaning: str = "Relative risk ranking (0-100) from synthetic sensor patterns. NOT a calibrated failure probability."
    limitations: list[str]
    model: ModelInfo


class ForecastResponse(ApiModel):
    target: str
    forecast: BandSeries
    actual: Series
    baseline: Series | None = None
    model: ModelInfo


class QueuePredictionItem(ApiModel):
    truck_trip_id: int | None = None
    position: int
    predicted_wait_min: float
    lower_min: float | None = None
    upper_min: float | None = None


class QueuePredictionResponse(ApiModel):
    as_of: datetime
    trucks_waiting: int
    predicted_avg_wait_min: float | None
    items: list[QueuePredictionItem]
    model: ModelInfo
    provenance: Provenance


class ModelRunRequest(ApiModel):
    target_ts: datetime | None = Field(None, description="Default: request as_of")


class ModelRunResponse(ApiModel):
    model: ModelInfo
    ran_at: datetime
    outputs: dict
    provenance: Provenance
