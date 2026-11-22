"""Equipment health for the process twin - an ADAPTER over backend-b's health engine. Owner: backend-a.

There is ONE health scale in the product: `app/services/maintenance_health.py` (backend-b, AI-C01). The twin does not
compute a parallel scale; it calls `maintenance_health.load_assessments(db, ctx)` and reshapes the result. The
shared sensor rule (both agents): Normal < warn; Warning >= warn; Critical >= crit (reversed for low_is_bad),
on readings <= as_of, with backend-b's 3-sample persistence and mill-running inhibit for low-is-bad process tags.
Equipment state precedence and the 'maintenance_required' criterion (service interval) are backend-b's - see that
module's docstring. Stage state = worst equipment state in the stage (order normal < warning <
maintenance_required < critical).

`sensor_state` below is the same single-sample classification, kept for unit tests and for display of the latest
value of sensors backend-b could not assess (fallback only).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.maintenance import WorkOrder, WorkOrderStatusHistory
from app.services.demo_context import DemoContext
from app.services.kpi_common import iso_utc

STATE_RANK = {"normal": 0, "warning": 1, "maintenance_required": 2, "critical": 3}
OPEN_WO = {"open", "assigned", "in_progress", "on_hold"}


def sensor_state(value: float | None, warn: float | None, crit: float | None, low_is_bad: bool) -> str | None:
    """Single-sample classification by the shared rule; None when the sensor has no limits or no value."""
    if value is None or (warn is None and crit is None):
        return None
    if low_is_bad:
        if crit is not None and value <= crit:
            return "critical"
        if warn is not None and value <= warn:
            return "warning"
        return "normal"
    if crit is not None and value >= crit:
        return "critical"
    if warn is not None and value >= warn:
        return "warning"
    return "normal"


def worst(states: list[str | None]) -> str:
    s = [str(x) for x in states if x]
    return max(s, key=lambda x: STATE_RANK.get(x, 0)) if s else "normal"


def open_work_orders(db: Session, ctx: DemoContext, at: datetime) -> dict[int, int]:
    """Open work orders per equipment at the demo clock (baseline history <= at, plus the caller's session rows)."""
    counts: dict[int, int] = defaultdict(int)
    hist: dict[int, str] = {}
    for wo_id, to_status in db.execute(
        select(WorkOrderStatusHistory.work_order_id, WorkOrderStatusHistory.to_status)
        .where(WorkOrderStatusHistory.session_id.is_(None), WorkOrderStatusHistory.changed_at <= at)
        .order_by(WorkOrderStatusHistory.changed_at, WorkOrderStatusHistory.id)
    ).all():
        hist[wo_id] = to_status
    session_rows: list[WorkOrder] = []
    cloned: set[int] = set()
    if ctx.session_id:
        session_rows = list(db.execute(select(WorkOrder).where(WorkOrder.session_id == ctx.session_id)).scalars())
        cloned = {w.cloned_from_id for w in session_rows if w.cloned_from_id}
    for wo in db.execute(select(WorkOrder).where(WorkOrder.session_id.is_(None), WorkOrder.created_at <= at)).scalars():
        if wo.id not in cloned and hist.get(wo.id) in OPEN_WO:
            counts[wo.equipment_id] += 1
    for wo in session_rows:
        if wo.demo_as_of is not None and iso_utc(wo.demo_as_of) > at:
            continue
        if wo.status in OPEN_WO:
            counts[wo.equipment_id] += 1
    return dict(counts)


def _val(x: Any) -> Any:
    return getattr(x, "value", x)


def equipment_health(db: Session, ctx: DemoContext) -> dict[int, dict[str, Any]]:
    """Per equipment id: state, criteria, risk_score, open work orders, latest reading + level per sensor."""
    from app.services import maintenance_health as mh  # noqa: PLC0415  (lazy: maintenance_health imports sensor_state from here)

    assessments = mh.load_assessments(db, ctx)
    wos = open_work_orders(db, ctx, ctx.as_of)
    out: dict[int, dict[str, Any]] = {}
    for eid, a in assessments.items():
        out[eid] = {
            "state": _val(a.state),
            "criteria": [c.model_dump(mode="json") if hasattr(c, "model_dump") else dict(c) for c in a.criteria],
            "risk_score": a.risk_score,
            "open_work_orders": wos.get(eid, 0),
            "readings": {s.sensor_id: s.latest for s in a.sensors},
            "levels": {s.sensor_id: (_val(s.level) if s.level is not None else None) for s in a.sensors},
            "reasons": {s.sensor_id: s.reason for s in a.sensors},
        }
    return out


def latest_value_by_code(db: Session, ctx: DemoContext, codes: list[str]) -> dict[str, float | None]:
    """Latest good reading <= as_of (6 h lookback) for the given sensor codes (display values, e.g. tank level)."""
    from datetime import timedelta  # noqa: PLC0415

    from sqlalchemy import func  # noqa: PLC0415

    from app.models.core import Sensor  # noqa: PLC0415
    from app.models.readings import SensorReading  # noqa: PLC0415

    ids = dict(db.execute(select(Sensor.id, Sensor.code).where(Sensor.code.in_(codes))).all())
    if not ids:
        return {}
    sub = (
        select(SensorReading.sensor_id, func.max(SensorReading.ts).label("mts"))
        .where(SensorReading.sensor_id.in_(list(ids)), SensorReading.ts > ctx.as_of - timedelta(hours=6), SensorReading.ts <= ctx.as_of)
        .group_by(SensorReading.sensor_id)
        .subquery()
    )
    rows = db.execute(
        select(SensorReading.sensor_id, SensorReading.value).join(sub, (SensorReading.sensor_id == sub.c.sensor_id) & (SensorReading.ts == sub.c.mts))
    ).all()
    found = {ids[sid]: float(v) for sid, v in rows}
    return {c: found.get(c) for c in codes}
