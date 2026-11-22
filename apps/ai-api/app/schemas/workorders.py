"""Maintenance work orders (owner: backend-b). Writes are session-scoped (ADR-006) and audited."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import ApiModel, EntityRef, Role, WorkOrderPriority, WorkOrderSource, WorkOrderStatus


class WorkOrderCreateRequest(ApiModel):
    source_type: WorkOrderSource = WorkOrderSource.manual
    equipment_id: int = Field(ge=1)
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(None, max_length=4000)
    priority: WorkOrderPriority = WorkOrderPriority.medium
    alert_id: int | None = Field(None, ge=1)
    recommendation_id: int | None = Field(None, ge=1)
    anomaly_event_id: int | None = Field(None, ge=1)
    due_at: datetime | None = None
    estimated_downtime_h: float | None = Field(None, ge=0, le=720)
    confirm: bool = Field(False, description="Must be true: explicit human confirmation before a record is created")


class WorkOrderAssignRequest(ApiModel):
    technician_id: int = Field(ge=1)
    note: str | None = Field(None, max_length=1000)


class WorkOrderTransitionRequest(ApiModel):
    to_status: WorkOrderStatus
    note: str | None = Field(None, max_length=2000)
    resolution_notes: str | None = Field(None, max_length=4000, description="Required when to_status = resolved")
    downtime_min: float | None = Field(None, ge=0, le=43200, description="Recorded on the maintenance record at resolve")


class WorkOrderStatusChange(ApiModel):
    from_status: WorkOrderStatus | None
    to_status: WorkOrderStatus
    actor_role: Role
    changed_at: datetime
    note: str | None = None


class WorkOrderOut(ApiModel):
    id: int
    code: str
    title: str
    description: str | None
    status: WorkOrderStatus
    priority: WorkOrderPriority
    source_type: WorkOrderSource
    equipment: EntityRef
    alert_id: int | None = None
    recommendation_id: int | None = None
    anomaly_event_id: int | None = None
    assigned_technician: EntityRef | None = None
    created_by_role: Role
    created_at: datetime
    demo_as_of: datetime | None = None
    due_at: datetime | None = None
    resolved_at: datetime | None = None
    is_baseline: bool = Field(description="True for seeded shared rows (read-only); false for your session's rows")
    cloned_from_id: int | None = None
    allowed_transitions: list[WorkOrderStatus] = Field(description="Valid next states for the caller's role")
    # ---- additive (backend-b) ----
    alert_code: str | None = None
    alert_status: str | None = Field(None, description="Effective status of the linked alert in this session (ADR-014 cross-module effect)")
    latest_recorded_status: WorkOrderStatus | None = None
    read_only_reason: str | None = Field(None, description="Set when the demo clock is before the last recorded change")


class WorkOrderDetail(WorkOrderOut):
    history: list[WorkOrderStatusChange]
    resolution_notes: str | None = None
    maintenance_event_id: int | None = None


class WorkOrderListResponse(ApiModel):
    items: list[WorkOrderOut]
    total: int
    counts_by_status: dict[str, int]


class AuditEntry(ApiModel):
    id: int
    ts: datetime
    role: Role
    actor: str
    action: str
    entity_type: str
    entity_id: str | None
    before: dict | None = None
    after: dict | None = None
    hash: str
    prev_hash: str | None


class AuditTrailResponse(ApiModel):
    entity_type: str
    entity_id: str | None
    items: list[AuditEntry]
    chain_verified: bool | None = Field(None, description="Result of recomputing the hash chain (tamper evidence)")
