"""Maintenance work-order workflow (AI-C05, DML-056). Owner: backend-b.

Workflow: AI Alert -> Engineer Review -> Work Order -> Assigned Technician -> Maintenance Record -> Resolved.
  * "AI Alert"           an `alerts` row (threshold / ML) or an advisory recommendation
  * "Engineer Review"    the human `confirm=true` on create (or an approved recommendation decision)
  * "Work Order"         status `open`
  * "Assigned Technician" `assigned` -> `in_progress`
  * "Maintenance Record" a `maintenance_events` row written when the order is `resolved`
  * "Resolved"           `resolved`, then `closed` after engineer verification

State machine (anything else is rejected with 409 `invalid_transition`):
  open        -> assigned | on_hold | cancelled
  assigned    -> in_progress | on_hold | cancelled        (re-assign keeps `assigned`)
  in_progress -> resolved | on_hold | cancelled
  on_hold     -> assigned | in_progress | cancelled
  resolved    -> closed | in_progress                      (reopen if verification fails)
  closed, cancelled: terminal
Guards: assigned / in_progress need a technician; resolved needs resolution_notes.

Session scoping (ADR-006/014): visitor-created rows carry session_id; seeded rows are a read-only baseline. A change to
a seeded order creates a session copy (`cloned_from_id`) that carries a copy of the baseline history; reads show the
copy instead of the baseline row. Status is replayed from `work_order_status_history` at the demo clock, so time travel
shows what was true then. Cross-module effects stay inside the session: the linked alert gets an
`alert_status_changes` row and the equipment's displayed maintenance status follows the active orders - sensor history is
never rewritten.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found
from app.models import (
    Alert,
    AlertStatusChange,
    AnomalyEvent,
    AuditLog,
    Equipment,
    MaintenanceEvent,
    Technician,
    WorkOrder,
    WorkOrderStatusHistory,
)
from app.models.enums import Role, WorkOrderPriority, WorkOrderSource, WorkOrderStatus
from app.schemas.common import EntityRef
from app.schemas.workorders import (
    AuditEntry,
    AuditTrailResponse,
    WorkOrderAssignRequest,
    WorkOrderCreateRequest,
    WorkOrderDetail,
    WorkOrderListResponse,
    WorkOrderOut,
    WorkOrderStatusChange,
    WorkOrderTransitionRequest,
)
from app.services.audit import verify_chain_cached, write_audit
from app.services.demo_context import DemoContext, require_session, session_filter
from app.services.maintenance_health import OPEN_ALERT_STATES, effective_alert_status, load_alert_overrides
from app.services.rbac import Permission, has_permission

S = WorkOrderStatus
ACTIVE: frozenset[WorkOrderStatus] = frozenset({S.open, S.assigned, S.in_progress, S.on_hold})
TERMINAL: frozenset[WorkOrderStatus] = frozenset({S.closed, S.cancelled})
TRANSITIONS: dict[WorkOrderStatus, frozenset[WorkOrderStatus]] = {
    S.open: frozenset({S.assigned, S.on_hold, S.cancelled}),
    S.assigned: frozenset({S.in_progress, S.on_hold, S.cancelled}),
    S.in_progress: frozenset({S.resolved, S.on_hold, S.cancelled}),
    S.on_hold: frozenset({S.assigned, S.in_progress, S.cancelled}),
    S.resolved: frozenset({S.closed, S.in_progress}),
    S.closed: frozenset(),
    S.cancelled: frozenset(),
}
NEEDS_TECHNICIAN = frozenset({S.assigned, S.in_progress})
MAX_SESSION_WORK_ORDERS = 100
MAINT_STATUS_ORDER = [S.in_progress, S.assigned, S.on_hold, S.open]  # precedence for the displayed equipment status
MAINT_STATUS_LABEL = {S.open: "work_order_open", S.assigned: "assigned", S.in_progress: "in_progress", S.on_hold: "on_hold"}


def _utc(ts: datetime) -> datetime:
    from datetime import UTC  # noqa: PLC0415

    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


# ------------------------------------------------------------------ visibility / effective status
@dataclass
class WOView:
    row: WorkOrder
    status: WorkOrderStatus  # effective at the demo clock
    latest_status: WorkOrderStatus  # latest recorded (differs only when the clock is before the last change)
    history: list[WorkOrderStatusHistory]  # entries <= as_of, ordered
    last_change_ts: datetime | None
    resolved_at: datetime | None
    technician_id: int | None

    @property
    def is_baseline(self) -> bool:
        return self.row.session_id is None

    @property
    def writable_now(self) -> bool:
        return self.status == self.latest_status


def load_visible(db: Session, ctx: DemoContext, equipment_id: int | None = None) -> list[WOView]:
    """Work orders visible to the caller at the demo clock: baseline (not superseded by a session copy) + own session."""
    base_q = select(WorkOrder).where(WorkOrder.session_id.is_(None), WorkOrder.created_at <= ctx.as_of)
    own_q = select(WorkOrder).where(WorkOrder.session_id == ctx.session_id, WorkOrder.created_at <= ctx.as_of) if ctx.session_id else None
    if equipment_id is not None:
        base_q = base_q.where(WorkOrder.equipment_id == equipment_id)
        own_q = own_q.where(WorkOrder.equipment_id == equipment_id) if own_q is not None else None
    baseline = list(db.execute(base_q).scalars())
    own = list(db.execute(own_q).scalars()) if own_q is not None else []
    cloned_from = {w.cloned_from_id for w in own if w.cloned_from_id}
    rows = [w for w in baseline if w.id not in cloned_from] + own
    ids = {w.id for w in rows}
    hist: dict[int, list[WorkOrderStatusHistory]] = {}
    if ids:
        for h in db.execute(
            select(WorkOrderStatusHistory).where(session_filter(WorkOrderStatusHistory.session_id, ctx)).order_by(WorkOrderStatusHistory.changed_at, WorkOrderStatusHistory.id)
        ).scalars():
            if h.work_order_id in ids:
                hist.setdefault(h.work_order_id, []).append(h)
    out = []
    for w in rows:
        full = hist.get(w.id, [])
        upto = [h for h in full if _utc(h.changed_at) <= ctx.as_of]
        latest = S(full[-1].to_status) if full else S(w.status)
        status = S(upto[-1].to_status) if upto else (S(w.status) if not full else S.open)
        resolved = next((_utc(h.changed_at) for h in reversed(upto) if h.to_status == S.resolved.value), None)
        tech = w.assigned_technician_id if status != S.open else None
        out.append(WOView(w, status, latest, upto, _utc(upto[-1].changed_at) if upto else None, resolved, tech))
    out.sort(key=lambda v: (_utc(v.row.created_at), v.row.id), reverse=True)
    return out


def active_work_order_counts(db: Session, ctx: DemoContext) -> dict[int, int]:
    counts: dict[int, int] = {}
    for v in load_visible(db, ctx):
        if v.status in ACTIVE:
            counts[v.row.equipment_id] = counts.get(v.row.equipment_id, 0) + 1
    return counts


def maintenance_status_map(db: Session, ctx: DemoContext) -> dict[int, tuple[str, list[int]]]:
    """equipment_id -> (displayed maintenance status, active work-order ids). Absent = 'none'."""
    per: dict[int, list[WOView]] = {}
    for v in load_visible(db, ctx):
        if v.status in ACTIVE:
            per.setdefault(v.row.equipment_id, []).append(v)
    out: dict[int, tuple[str, list[int]]] = {}
    for eid, views in per.items():
        best = min(views, key=lambda v: MAINT_STATUS_ORDER.index(v.status))
        out[eid] = (MAINT_STATUS_LABEL[best.status], sorted(v.row.id for v in views))
    return out


def find_view(db: Session, ctx: DemoContext, work_order_id: int) -> WOView:
    """The caller's effective view of a work order (a session copy replaces its baseline row)."""
    views = load_visible(db, ctx)
    for v in views:
        if v.row.id == work_order_id:
            return v
    for v in views:  # baseline id whose session copy is what the caller sees
        if v.row.cloned_from_id == work_order_id:
            return v
    not_found("work_order", work_order_id)


# ------------------------------------------------------------------ output mapping
def _alert_status_for(db: Session, ctx: DemoContext, alert_id: int | None) -> tuple[str | None, str | None]:
    if alert_id is None:
        return None, None
    a = db.get(Alert, alert_id)
    if a is None:
        return None, None
    ov = load_alert_overrides(db, ctx, [alert_id]).get(alert_id, [])
    return a.code, effective_alert_status(a, ctx.as_of, ov)


def _out_kwargs(db: Session, ctx: DemoContext, v: WOView, eq: dict[int, Equipment], tech: dict[int, Technician]) -> dict[str, Any]:
    w = v.row
    e = eq.get(w.equipment_id)
    t = tech.get(v.technician_id) if v.technician_id else None
    can = has_permission(ctx.role, Permission.workorder_transition) and v.writable_now
    alert_code, alert_status = _alert_status_for(db, ctx, w.alert_id)
    return {
        "id": w.id,
        "code": w.code,
        "title": w.title,
        "description": w.description,
        "status": v.status,
        "priority": WorkOrderPriority(w.priority),
        "source_type": WorkOrderSource(w.source_type),
        "equipment": EntityRef(type="equipment", id=w.equipment_id, code=e.code if e else None, label=e.name if e else None),
        "alert_id": w.alert_id,
        "recommendation_id": w.recommendation_id,
        "anomaly_event_id": w.anomaly_event_id,
        "assigned_technician": EntityRef(type="technician", id=t.id, code=t.code, label=t.display_name) if t else None,
        "created_by_role": Role(w.created_by_role),
        "created_at": _utc(w.created_at),
        "demo_as_of": _utc(w.demo_as_of) if w.demo_as_of else None,
        "due_at": _utc(w.due_at) if w.due_at else None,
        "resolved_at": v.resolved_at,
        "is_baseline": v.is_baseline,
        "cloned_from_id": w.cloned_from_id,
        "allowed_transitions": sorted(TRANSITIONS[v.status], key=lambda s: list(S).index(s)) if can else [],
        "alert_code": alert_code,
        "alert_status": alert_status,
        "latest_recorded_status": v.latest_status,
        "read_only_reason": None if v.writable_now else "The demo clock is earlier than the last recorded change of this work order; move the clock forward to modify it.",
    }


def _maps(db: Session, views: list[WOView]) -> tuple[dict[int, Equipment], dict[int, Technician]]:
    eids = {v.row.equipment_id for v in views}
    tids = {v.technician_id for v in views if v.technician_id}
    eq = {e.id: e for e in db.execute(select(Equipment).where(Equipment.id.in_(eids))).scalars()} if eids else {}
    tech = {t.id: t for t in db.execute(select(Technician).where(Technician.id.in_(tids))).scalars()} if tids else {}
    return eq, tech


def view_to_out(db: Session, ctx: DemoContext, v: WOView) -> WorkOrderOut:
    eq, tech = _maps(db, [v])
    return WorkOrderOut(**_out_kwargs(db, ctx, v, eq, tech))


def view_to_detail(db: Session, ctx: DemoContext, v: WOView) -> WorkOrderDetail:
    eq, tech = _maps(db, [v])
    base_id = v.row.cloned_from_id or v.row.id
    ev = db.execute(
        select(MaintenanceEvent.id)
        .where(MaintenanceEvent.work_order_id.in_([v.row.id, base_id]), session_filter(MaintenanceEvent.session_id, ctx), MaintenanceEvent.start_ts <= ctx.as_of)
        .order_by(MaintenanceEvent.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    notes = v.row.resolution_notes if v.status in {S.resolved, S.closed} else None
    return WorkOrderDetail(
        **_out_kwargs(db, ctx, v, eq, tech),
        history=[
            WorkOrderStatusChange(
                from_status=S(h.from_status) if h.from_status else None, to_status=S(h.to_status), actor_role=Role(h.actor_role),
                changed_at=_utc(h.changed_at), note=h.note,
            )
            for h in v.history
        ],
        resolution_notes=notes,
        maintenance_event_id=ev if v.status in {S.resolved, S.closed} else None,
    )


def list_work_orders(
    db: Session, ctx: DemoContext, status: WorkOrderStatus | None, priority: WorkOrderPriority | None,
    equipment_id: int | None, mine_only: bool, limit: int, offset: int,
) -> WorkOrderListResponse:
    views = load_visible(db, ctx, equipment_id)
    if priority is not None:
        views = [v for v in views if v.row.priority == priority.value]
    if mine_only:
        views = [v for v in views if not v.is_baseline]
    counts = {s.value: 0 for s in S}
    for v in views:
        counts[v.status.value] += 1
    if status is not None:
        views = [v for v in views if v.status == status]
    page = views[offset : offset + limit]
    eq, tech = _maps(db, page)
    return WorkOrderListResponse(items=[WorkOrderOut(**_out_kwargs(db, ctx, v, eq, tech)) for v in page], total=len(views), counts_by_status=counts)


# ------------------------------------------------------------------ writes
def _audit_payload(db: Session, w: WorkOrder, status: WorkOrderStatus, tech: int | None) -> dict[str, Any]:
    e = db.get(Equipment, w.equipment_id)
    t = db.get(Technician, tech) if tech else None
    return {"status": status.value, "equipment": e.code if e else w.equipment_id, "technician": t.code if t else None, "priority": w.priority}


def _history(db: Session, ctx: DemoContext, wo: WorkOrder, frm: WorkOrderStatus | None, to: WorkOrderStatus, note: str | None) -> None:
    db.add(
        WorkOrderStatusHistory(
            work_order_id=wo.id, session_id=ctx.session_id, from_status=frm.value if frm else None, to_status=to.value,
            actor_role=ctx.role.value, changed_at=ctx.as_of, note=note,
        )
    )


def _set_alert_status(db: Session, ctx: DemoContext, alert_id: int | None, to_status: str, note: str) -> None:
    """Session-scoped alert status change (ADR-014). The baseline alert row is never touched."""
    if alert_id is None:
        return
    a = db.get(Alert, alert_id)
    if a is None:
        return
    cur = effective_alert_status(a, ctx.as_of, load_alert_overrides(db, ctx, [alert_id]).get(alert_id, []))
    if cur is None or cur == to_status:
        return
    db.add(
        AlertStatusChange(alert_id=alert_id, session_id=ctx.session_id, from_status=cur, to_status=to_status, actor_role=ctx.role.value, note=note, changed_at=ctx.as_of)
    )
    write_audit(db, ctx, "alert.status_change", "alert", a.code, {"status": cur}, {"status": to_status, "reason": note})


def _resolve_for_write(db: Session, ctx: DemoContext, work_order_id: int) -> tuple[WorkOrder, WOView]:
    """Return the mutable session row (creating the copy-on-write copy of a seeded order) and its view."""
    require_session(ctx)
    v = find_view(db, ctx, work_order_id)
    if not v.writable_now:
        raise ApiError(
            409, "clock_before_record",
            "The demo clock (as_of) is earlier than the last recorded change of this work order. Move the clock to the same time or later to modify it.",
            {"status_at_clock": v.status.value, "latest_status": v.latest_status.value},
        )
    if v.is_baseline:
        if v.status in TERMINAL:
            raise ApiError(409, "invalid_transition", f"Work order is {v.status.value} (terminal) and cannot be changed.", {"from": v.status.value, "allowed": []})
        _quota(db, ctx)
        w = v.row
        clone = WorkOrder(
            code=f"{w.code}-tmp-{uuid.uuid4().hex[:8]}", session_id=ctx.session_id, cloned_from_id=w.id, equipment_id=w.equipment_id, title=w.title,
            description=w.description, priority=w.priority, status=v.status.value, source_type=w.source_type, alert_id=w.alert_id,
            recommendation_id=w.recommendation_id, anomaly_event_id=w.anomaly_event_id, assigned_technician_id=w.assigned_technician_id,
            created_by_role=w.created_by_role, created_at=w.created_at, demo_as_of=w.demo_as_of, due_at=w.due_at, resolved_at=None,
            resolution_notes=w.resolution_notes, estimated_downtime_h=w.estimated_downtime_h, data_kind="user_input",
        )
        db.add(clone)
        db.flush()
        clone.code = f"{w.code}-C{clone.id}"
        for h in v.history:  # copy of the baseline history so the session copy is self-contained
            db.add(
                WorkOrderStatusHistory(
                    work_order_id=clone.id, session_id=ctx.session_id, from_status=h.from_status, to_status=h.to_status,
                    actor_role=h.actor_role, changed_at=h.changed_at, note=h.note,
                )
            )
        db.flush()
        write_audit(db, ctx, "work_order.copy_on_write", "work_order", clone.code, {"baseline": w.code, "status": v.status.value}, {"copy": clone.code, "reason": "first change by this session (ADR-014)"})
        return clone, find_view(db, ctx, clone.id)
    return v.row, v


def _quota(db: Session, ctx: DemoContext) -> None:
    n = db.execute(select(func.count()).select_from(WorkOrder).where(WorkOrder.session_id == ctx.session_id)).scalar_one()
    if n >= MAX_SESSION_WORK_ORDERS:
        raise ApiError(409, "session_quota_exceeded", f"This demo session already holds {n} work orders (limit {MAX_SESSION_WORK_ORDERS}). Reset the session to continue.", {"limit": MAX_SESSION_WORK_ORDERS})


def create_work_order(db: Session, ctx: DemoContext, body: WorkOrderCreateRequest, commit: bool = True) -> WorkOrderOut:
    sid = require_session(ctx)
    if not body.confirm:
        raise ApiError(422, "confirmation_required", "Creating a work order changes a business record: send confirm=true after the engineer review.", {"field": "confirm"})
    eq = db.get(Equipment, body.equipment_id)
    if eq is None:
        not_found("equipment", body.equipment_id)
    src = body.source_type
    if src == WorkOrderSource.alert and body.alert_id is None:
        raise ApiError(422, "alert_id_required", "source_type=alert needs alert_id")
    if src == WorkOrderSource.recommendation and body.recommendation_id is None:
        raise ApiError(422, "recommendation_id_required", "source_type=recommendation needs recommendation_id")
    if body.alert_id is not None:
        src = WorkOrderSource.alert
    elif body.recommendation_id is not None:
        src = WorkOrderSource.recommendation
    alert = None
    if body.alert_id is not None:
        alert = db.get(Alert, body.alert_id)
        if alert is None or _utc(alert.raised_at) > ctx.as_of:
            not_found("alert", body.alert_id)
        if alert.equipment_id is not None and alert.equipment_id != body.equipment_id:
            raise ApiError(422, "alert_equipment_mismatch", "The alert belongs to a different equipment.", {"alert_equipment_id": alert.equipment_id})
        cur = effective_alert_status(alert, ctx.as_of, load_alert_overrides(db, ctx, [alert.id]).get(alert.id, []))
        if cur not in OPEN_ALERT_STATES:
            raise ApiError(409, "alert_closed", f"Alert {alert.code} is already {cur} at the demo clock.", {"alert_status": cur})
    rec_row_id = None
    if body.recommendation_id is not None:
        from app.services.maintenance_reco import ensure_catalog_row, resolve_recommendation  # noqa: PLC0415 - import cycle

        rec = resolve_recommendation(db, ctx, body.recommendation_id)
        if rec.equipment_id is not None and rec.equipment_id != body.equipment_id:
            raise ApiError(422, "recommendation_equipment_mismatch", "The recommendation belongs to a different equipment.", {"recommendation_equipment_id": rec.equipment_id})
        rec_row_id = ensure_catalog_row(db, ctx, rec)
    if body.anomaly_event_id is not None and db.get(AnomalyEvent, body.anomaly_event_id) is None:
        not_found("anomaly_event", body.anomaly_event_id)
    # one active order per (equipment, alert|recommendation) in this session
    for v in load_visible(db, ctx, body.equipment_id):
        if v.status in ACTIVE and ((body.alert_id and v.row.alert_id == body.alert_id) or (body.recommendation_id and v.row.recommendation_id in (body.recommendation_id, rec_row_id))):
            raise ApiError(409, "duplicate_work_order", f"An active work order ({v.row.code}) already exists for this alert/recommendation.", {"work_order_id": v.row.id, "code": v.row.code})
    _quota(db, ctx)
    ym = f"{ctx.local_as_of:%Y%m}"
    wo = WorkOrder(
        code=f"WO-{ym}-tmp-{uuid.uuid4().hex[:8]}", session_id=sid, equipment_id=body.equipment_id, title=body.title.strip(), description=body.description,
        priority=body.priority.value, status=S.open.value, source_type=src.value, alert_id=body.alert_id, recommendation_id=rec_row_id,
        anomaly_event_id=body.anomaly_event_id, created_by_role=ctx.role.value, created_at=ctx.as_of, demo_as_of=ctx.as_of, due_at=body.due_at,
        estimated_downtime_h=body.estimated_downtime_h, data_kind="user_input",
    )
    db.add(wo)
    db.flush()
    wo.code = f"WO-{ym}-{wo.id:04d}"
    _history(db, ctx, wo, None, S.open, "Work order created after engineer review (human-confirmed)")
    db.flush()
    write_audit(db, ctx, "work_order.create", "work_order", wo.code, None, {**_audit_payload(db, wo, S.open, None), "source": src.value, "alert": alert.code if alert else None, "recommendation_id": rec_row_id, "confirm": True})
    if alert is not None:
        _set_alert_status(db, ctx, alert.id, "in_progress", f"Work order {wo.code} created")
    if commit:
        db.commit()
    return view_to_out(db, ctx, find_view(db, ctx, wo.id))


def assign_work_order(db: Session, ctx: DemoContext, work_order_id: int, body: WorkOrderAssignRequest) -> WorkOrderOut:
    w, v = _resolve_for_write(db, ctx, work_order_id)
    if v.status not in {S.open, S.assigned, S.on_hold}:
        raise ApiError(409, "invalid_transition", f"A technician can only be assigned while the order is open, assigned or on hold (now {v.status.value}).", {"from": v.status.value, "allowed": ["open", "assigned", "on_hold"]})
    tech = db.get(Technician, body.technician_id)
    if tech is None or not tech.is_active:
        not_found("technician", body.technician_id)
    before = _audit_payload(db, w, v.status, v.technician_id)
    to = S.assigned if v.status == S.open else v.status
    w.assigned_technician_id = tech.id
    w.status = to.value
    note = (body.note or "").strip() or ("Technician assigned" if v.technician_id is None else "Technician re-assigned")
    _history(db, ctx, w, v.status, to, f"{note} ({tech.code})")
    db.flush()
    write_audit(db, ctx, "work_order.assign", "work_order", w.code, before, _audit_payload(db, w, to, tech.id))
    db.commit()
    return view_to_out(db, ctx, find_view(db, ctx, w.id))


def transition_work_order(db: Session, ctx: DemoContext, work_order_id: int, body: WorkOrderTransitionRequest) -> WorkOrderOut:
    require_session(ctx)
    v0 = find_view(db, ctx, work_order_id)
    to = body.to_status
    allowed = TRANSITIONS[v0.status]
    if to not in allowed:  # validate before any copy-on-write side effect
        raise ApiError(
            409, "invalid_transition", f"Invalid transition {v0.status.value} -> {to.value}. Allowed from {v0.status.value}: {sorted(s.value for s in allowed) or 'none (terminal)'}.",
            {"from": v0.status.value, "to": to.value, "allowed": sorted(s.value for s in allowed)},
        )
    if to == S.resolved and not (body.resolution_notes or "").strip():
        raise ApiError(422, "resolution_notes_required", "resolution_notes is required when resolving a work order (it becomes the maintenance record).", {"field": "resolution_notes"})
    if to in NEEDS_TECHNICIAN and v0.technician_id is None and v0.row.assigned_technician_id is None:
        raise ApiError(422, "technician_required", f"Assign a technician before moving to {to.value} (POST /work-orders/{{id}}/assign).", {"field": "technician_id"})
    w, v = _resolve_for_write(db, ctx, work_order_id)
    before = _audit_payload(db, w, v.status, w.assigned_technician_id)
    w.status = to.value
    note = (body.note or "").strip() or None
    event_id = None
    if to == S.resolved:
        w.resolution_notes = body.resolution_notes.strip()
        w.resolved_at = ctx.as_of
        downtime = body.downtime_min if body.downtime_min is not None else (w.estimated_downtime_h or 0.0) * 60.0
        from datetime import timedelta  # noqa: PLC0415

        ev = MaintenanceEvent(
            equipment_id=w.equipment_id, work_order_id=w.id, session_id=ctx.session_id,
            event_type="preventive" if w.source_type == "preventive" else "corrective",
            start_ts=ctx.as_of - timedelta(minutes=downtime), end_ts=ctx.as_of, downtime_min=downtime,
            planned=w.source_type in {"recommendation", "preventive"}, description=w.resolution_notes, technician_id=w.assigned_technician_id,
            data_kind="user_input",
        )
        db.add(ev)
        db.flush()
        event_id = ev.id
        note = note or "Maintenance record written"
        _set_alert_status(db, ctx, w.alert_id, "resolved", f"Work order {w.code} resolved")
    elif to == S.cancelled:
        _set_alert_status(db, ctx, w.alert_id, "acknowledged", f"Work order {w.code} cancelled; alert still needs attention")
    _history(db, ctx, w, v.status, to, note)
    db.flush()
    after = _audit_payload(db, w, to, w.assigned_technician_id)
    if event_id:
        after["maintenance_event_id"] = event_id
    write_audit(db, ctx, "work_order.transition", "work_order", w.code, before, after)
    db.commit()
    return view_to_out(db, ctx, find_view(db, ctx, w.id))


# ------------------------------------------------------------------ audit trail
def _loads(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        val = json.loads(raw)
    except ValueError:
        return {"raw": raw[:500]}
    return val if isinstance(val, dict) else {"value": val}


def audit_trail(db: Session, ctx: DemoContext, work_order_id: int) -> AuditTrailResponse:
    v = find_view(db, ctx, work_order_id)
    codes = {v.row.code}
    if v.row.cloned_from_id:
        base = db.get(WorkOrder, v.row.cloned_from_id)
        if base:
            codes.add(base.code)
    rows = list(
        db.execute(
            select(AuditLog).where(AuditLog.entity_type == "work_order", AuditLog.entity_id.in_(codes), session_filter(AuditLog.session_id, ctx)).order_by(AuditLog.id)
        ).scalars()
    )
    linked: set[str] = set()
    if v.row.alert_id:
        a = db.get(Alert, v.row.alert_id)
        if a:
            linked.add(a.code)
    if linked and ctx.session_id:  # session-scoped effects on the linked alert (ADR-014)
        rows += list(
            db.execute(select(AuditLog).where(AuditLog.entity_type == "alert", AuditLog.entity_id.in_(linked), AuditLog.session_id == ctx.session_id).order_by(AuditLog.id)).scalars()
        )
    if ctx.session_id and v.row.recommendation_id:
        from app.models import AiRecommendation  # noqa: PLC0415

        rc = db.get(AiRecommendation, v.row.recommendation_id)
        if rc:
            rows += list(
                db.execute(select(AuditLog).where(AuditLog.entity_type == "recommendation", AuditLog.entity_id == rc.code, AuditLog.session_id == ctx.session_id).order_by(AuditLog.id)).scalars()
            )
    rows = [r for r in rows if _utc(r.demo_as_of or r.ts) <= ctx.as_of]
    rows.sort(key=lambda r: r.id)
    ok = verify_chain_cached(db)
    return AuditTrailResponse(
        entity_type="work_order",
        entity_id=v.row.code,
        items=[
            AuditEntry(
                id=r.id, ts=_utc(r.ts), role=Role(r.role), actor=r.actor, action=r.action, entity_type=r.entity_type, entity_id=r.entity_id,
                before=_loads(r.before_json), after=_loads(r.after_json), hash=r.hash, prev_hash=r.prev_hash,
            )
            for r in rows
        ],
        chain_verified=ok,
    )


__all__ = [
    "ACTIVE", "TERMINAL", "TRANSITIONS", "WOView", "active_work_order_counts", "assign_work_order", "audit_trail", "create_work_order",
    "find_view", "list_work_orders", "load_visible", "maintenance_status_map", "transition_work_order", "view_to_detail", "view_to_out",
]
