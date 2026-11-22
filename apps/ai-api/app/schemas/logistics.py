"""Logistics & Weighbridge (owner: backend-a). Anomalies flag data for review - never accusations."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from app.schemas.common import ApiModel, Assumption, KpiValue, Provenance, Series


class TruckInQueue(ApiModel):
    truck_trip_id: int
    code: str
    supplier_code: str
    plate_masked: str
    status: str
    arrival_ts: datetime
    waiting_min: float
    position: int | None = None


class QueueNowResponse(ApiModel):
    as_of: datetime
    trucks_waiting: int
    trucks_unloading: int
    avg_wait_min: float | None
    max_wait_min: float | None
    trucks: list[TruckInQueue]
    queue_length_series: Series
    provenance: Provenance
    by_stage: dict[str, int] = Field(default_factory=dict, description="Trucks on site by stage at as_of (derived from timestamps)")
    note: str | None = None


class TicketOut(ApiModel):
    id: int
    ticket_no: str
    truck_trip_id: int
    supplier_code: str
    bridge_code: str
    weigh_in_ts: datetime
    weigh_out_ts: datetime | None
    gross_kg: int
    tare_kg: int | None
    net_kg: int | None
    grade: str | None = None
    deduction_pct: float | None = None
    accepted_kg: int | None = None
    flags: list[str] = Field([], description="Data-quality flags for review (e.g. implausible_tare) - not accusations")


class TicketListResponse(ApiModel):
    items: list[TicketOut]
    total: int
    note: str | None = None


class SupplierOut(ApiModel):
    id: int
    code: str
    name: str
    supplier_type: str
    province: str | None
    deliveries_30d: int | None = None
    ffb_30d_t: float | None = None
    avg_ripe_pct: float | None = None
    grade_mix: dict[str, float] = {}
    avg_wait_min: float | None = None
    sustainability_status: str


class SupplierListResponse(ApiModel):
    items: list[SupplierOut]
    total: int


class PlantationOut(ApiModel):
    id: int
    code: str
    name: str
    area_ha: float | None
    district: str | None
    planting_year: int | None


class SupplierDetail(SupplierOut):
    plantations: list[PlantationOut]
    quality_series: Series
    volume_series: Series


class LogisticsKpisResponse(ApiModel):
    kpis: list[KpiValue] = Field(description="avg_wait_min, avg_turnaround_min, max_queue_length, bridge_utilisation_pct, trucks_per_day, ffb_received_t")
    period_start: datetime | None = None
    period_end: datetime | None = None


class ArrivalHeatCell(ApiModel):
    weekday: int = Field(description="0 = Monday (mill-local)")
    hour: int
    avg_arrivals: float


class ArrivalPatternResponse(ApiModel):
    business_date: date
    by_hour: Series = Field(description="Arrivals per hour (actual)")
    typical_by_hour: Series = Field(description="Average arrivals per hour over the last N days")
    provenance: Provenance
    heatmap: list[ArrivalHeatCell] = Field(default_factory=list, description="Average arrivals per weekday x hour (history before business_date)")
    heatmap_note: str | None = None


class QueuePolicy(StrEnum):
    fifo = "fifo"
    slot_based = "slot_based"


class QueueSimulationRequest(ApiModel):
    business_date: date | None = Field(None, description="Arrival set to replay (default: as_of day)")
    policies: list[QueuePolicy] = Field([QueuePolicy.fifo, QueuePolicy.slot_based], min_length=1, max_length=2, description="At most one entry per policy (QA-12: the list was unbounded and every entry re-ran the simulation)")
    weighbridges: int = Field(2, ge=1, le=6)
    slot_minutes: int = Field(30, ge=5, le=240)
    trucks_per_slot: int = Field(6, ge=1, le=50)
    unloading_ramps: int = Field(4, ge=1, le=20)
    seed: int = Field(42, ge=0, le=2**31 - 1)
    ramp_capacity_t: float | None = Field(600, ge=50, le=5000, description="Loading-ramp FFB capacity; unloading waits when the ramp is full "
                                          "(stock + processing replayed from process_hourly). null = no ramp constraint")
    replay_observed_outages: bool = Field(True, description="Replay weighbridge / ramp outages inferred from recorded queue events")


class QueuePolicyResult(ApiModel):
    policy: QueuePolicy
    avg_wait_min: float
    p90_wait_min: float
    max_queue_length: int
    avg_turnaround_min: float
    bridge_utilisation_pct: float
    queue_length_series: Series
    max_wait_min: float | None = None
    unloading_utilisation_pct: float | None = None
    avg_deferral_min: float | None = Field(None, description="Slot policy: waiting moved off-site (yard arrival - actual arrival)")
    max_deferral_min: float | None = None
    avg_total_delay_min: float | None = Field(None, description="Deferral + in-yard wait")


class QueueSimulationResponse(ApiModel):
    trucks_simulated: int
    business_date: date | None = None
    slot_capacity_used: int | None = None
    observed: dict[str, float | int | None] = Field(default_factory=dict, description="Historical wait/turnaround of the same trucks (model fit check)")
    inferred_outages: list[dict[str, Any]] = Field(default_factory=list, description="Unit outages inferred from recorded queue events")
    results: list[QueuePolicyResult]
    assumptions: list[Assumption]
    limitations: list[str]
    provenance: Provenance
