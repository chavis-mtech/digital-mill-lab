"""Industrial Digital Twin Lite - process stages driven by the same simulated state (owner: backend-a)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.alerts import AlertOut
from app.schemas.common import ApiModel, HealthState, KpiValue, Provenance, Series, StageCode
from app.schemas.maintenance import EquipmentSummary, RecommendationOut
from app.schemas.production import ProcessVariable


class StageState(ApiModel):
    code: StageCode
    name_en: str
    name_th: str
    sequence: int
    kind: str
    status: HealthState = Field(description="Worst computed equipment health in the stage")
    throughput_tph: float | None = None
    headline_kpi: KpiValue | None = None
    active_alerts: int = 0
    equipment_count: int = 0


class FlowEdge(ApiModel):
    source: StageCode
    target: StageCode
    material: str = Field(examples=["FFB", "sterilized FFB", "fruitlets", "mash", "crude oil", "CPO"])
    flow_tph: float | None = None


class ProcessStageListResponse(ApiModel):
    ts: datetime
    stages: list[StageState]
    edges: list[FlowEdge]
    provenance: Provenance
    health_rule: str | None = None


class StageDetailResponse(ApiModel):
    stage: StageState
    equipment: list[EquipmentSummary]
    variables: list[ProcessVariable]
    kpis: list[KpiValue]
    trends: list[Series]
    alerts: list[AlertOut]
    recommendations: list[RecommendationOut]
