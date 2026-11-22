"""Unified alerts (owner: backend-a). Used by executive, process twin, maintenance, logistics, energy."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import (
    AlertSource,
    AlertStatus,
    ApiModel,
    EntityRef,
    Evidence,
    Formula,
    Provenance,
    ScenarioCode,
    Severity,
    StageCode,
)


class BusinessImpact(ApiModel):
    """Estimated impact of an alert - always with the formula and assumptions used."""

    lost_cpo_t: float | None = None
    lost_value_thb: float | None = None
    downtime_h: float | None = None
    formulas: list[Formula] = []
    assumptions_note: str | None = None
    provenance: Provenance


class AlertOut(ApiModel):
    id: int
    code: str
    source: AlertSource
    module: str
    severity: Severity
    status: AlertStatus = Field(description="Effective status for this caller's session (baseline + session changes)")
    title: str
    message: str
    raised_at: datetime
    resolved_at: datetime | None = None
    equipment: EntityRef | None = None
    process_stage_code: StageCode | None = None
    anomaly_event_id: int | None = None
    recommendation_id: int | None = None
    priority_score: float | None = Field(None, description="0-100 ranking score (severity x impact x recency); not a probability")
    suggested_team: str | None = Field(None, description="Which team checks first (maintenance, production, logistics, QC)")
    evidence: list[Evidence] = []
    impact: BusinessImpact | None = None
    scenario_code: ScenarioCode | None = None


class AlertListResponse(ApiModel):
    items: list[AlertOut]
    total: int
    counts_by_severity: dict[str, int]
    as_of: datetime


class AlertAcknowledgeRequest(ApiModel):
    to_status: AlertStatus = AlertStatus.acknowledged
    note: str | None = Field(None, max_length=1000)
