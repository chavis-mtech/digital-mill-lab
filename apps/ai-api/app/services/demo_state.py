"""Demo sandbox state: session reset, admin reset-all, idle-session retention and the simulated-live tick. Owner: backend-b.

Reset deletes ONLY business rows scoped to the session (ADR-006): work orders (+ history, maintenance records),
recommendation decisions, alert / anomaly status changes, saved scenarios, copilot sessions + messages. The append-only
audit log is never touched - the reset itself is audited (ADR-013). Seeded baseline rows and visitor-independent catalog
rows (`ai_recommendations`) stay.

Retention (ADR-006 "bounded growth"): `purge_idle_sessions()` deletes the rows of sessions whose last audit entry is older than
`max_idle_hours`. Run it from cron / the container entrypoint: `python -m app.services.demo_state --purge-idle-hours 72`.

Tick (ADR-005): the server holds no clock. The client sends its current as_of; the response carries the next as_of
(advanced by step_minutes, looping inside the scenario window - or the dataset window - when it reaches the end) and a few
headline values for the two moments. Everything is labelled SIMULATION.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import (
    Alert,
    AlertStatusChange,
    AnomalyStatusChange,
    AuditLog,
    BusinessScenario,
    CopilotMessage,
    CopilotSession,
    Equipment,
    MaintenanceEvent,
    ProcessHourly,
    RecommendationDecision,
    ScenarioRun,
    WorkOrder,
    WorkOrderStatusHistory,
)
from app.schemas.common import KpiValue, Provenance, TrendDirection
from app.schemas.demo import ResetAllResponse, SessionResetResponse, TickRequest, TickResponse
from app.services.audit import write_audit
from app.services.demo_context import DemoContext, require_session

# Deletion order respects foreign keys (children first).
SESSION_TABLES = [
    RecommendationDecision, AlertStatusChange, AnomalyStatusChange, BusinessScenario, CopilotMessage, CopilotSession,
    MaintenanceEvent, WorkOrderStatusHistory, WorkOrder,
]


def _utc(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def latest_data_ts(db: Session) -> datetime | None:
    try:
        ts = db.execute(select(func.max(ProcessHourly.ts))).scalar_one_or_none()
    except SQLAlchemyError:
        db.rollback()
        return None
    return _utc(ts) + timedelta(hours=1) if ts else None


def _delete(db: Session, model, where) -> int:
    try:
        return db.execute(delete(model).where(where)).rowcount or 0
    except SQLAlchemyError:  # a table another agent owns may not exist in a stripped-down DB
        db.rollback()
        raise


def reset_session(db: Session, ctx: DemoContext) -> SessionResetResponse:
    sid = require_session(ctx)
    deleted = {m.__tablename__: _delete(db, m, m.session_id == sid) for m in SESSION_TABLES}
    now = datetime.now(UTC)
    write_audit(db, ctx, "demo.session_reset", "demo_session", sid, None, {"deleted": deleted, "audit_log": "kept (append-only)"})
    db.commit()
    return SessionResetResponse(session_id=sid, deleted=deleted, reset_at=now)


def reset_all(db: Session, ctx: DemoContext) -> ResetAllResponse:
    sessions: set[str] = set()
    for m in SESSION_TABLES:
        sessions |= {s for s in db.execute(select(m.session_id).where(m.session_id.is_not(None)).distinct()).scalars()}
    deleted = {m.__tablename__: _delete(db, m, m.session_id.is_not(None)) for m in SESSION_TABLES}
    now = datetime.now(UTC)
    write_audit(db, ctx, "demo.reset_all", "demo_session", "*", None, {"sessions_cleared": len(sessions), "deleted": deleted, "audit_log": "kept (append-only)"})
    db.commit()
    return ResetAllResponse(sessions_cleared=len(sessions), deleted=deleted, reset_at=now)


def purge_idle_sessions(db: Session, max_idle_hours: float = 72.0, now: datetime | None = None) -> dict[str, int]:
    """Retention job: delete the rows of sessions with no audit activity for max_idle_hours (audit rows stay)."""
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(hours=max_idle_hours)
    last = db.execute(select(AuditLog.session_id, func.max(AuditLog.ts)).where(AuditLog.session_id.is_not(None)).group_by(AuditLog.session_id)).all()
    idle = [sid for sid, ts in last if _utc(ts) < cutoff]
    totals = {m.__tablename__: 0 for m in SESSION_TABLES}
    for i in range(0, len(idle), 200):
        chunk = idle[i : i + 200]
        for m in SESSION_TABLES:
            totals[m.__tablename__] += _delete(db, m, m.session_id.in_(chunk))
    if idle:
        write_audit(db, None, "demo.retention_purge", "demo_session", "*", None, {"sessions": len(idle), "max_idle_hours": max_idle_hours, "deleted": totals})
    db.commit()
    return totals


# ------------------------------------------------------------------ simulated live tick
def _snapshot(db: Session, ctx: DemoContext, t: datetime) -> dict:
    last = db.execute(select(ProcessHourly.ts, ProcessHourly.throughput_tph).where(ProcessHourly.ts <= t - timedelta(hours=1)).order_by(ProcessHourly.ts.desc()).limit(1)).first()
    rows = db.execute(
        select(ProcessHourly.ffb_processed_t, ProcessHourly.cpo_t).where(ProcessHourly.ts <= t - timedelta(hours=1), ProcessHourly.ts > t - timedelta(hours=5))
    ).all()
    f, c = sum(r[0] or 0 for r in rows), sum(r[1] or 0 for r in rows)
    open_alerts = db.execute(select(func.count()).select_from(Alert).where(Alert.raised_at <= t, (Alert.resolved_at.is_(None)) | (Alert.resolved_at > t))).scalar_one()
    return {"throughput": float(last[1]) if last else None, "oer4": 100.0 * c / f if f > 0 else None, "alerts": float(open_alerts)}


def _kpi(key: str, label: str, unit: str, cur: float | None, prev: float | None, nxt: datetime, source: str, good: TrendDirection) -> KpiValue:
    d = None if cur is None or prev is None else round(cur - prev, 3)
    return KpiValue(
        key=key, label=label, value=None if cur is None else round(cur, 3), unit=unit, previous=None if prev is None else round(prev, 3), delta=d,
        delta_pct=None if d is None or not prev else round(100 * d / prev, 2), good_direction=good,
        provenance=Provenance(kind="synthetic_actual", source=source, as_of=nxt, model_version=None),
    )


def tick(db: Session, ctx: DemoContext, body: TickRequest) -> TickResponse:
    start, end = ctx.window_start, ctx.window_end
    if ctx.scenario_id is not None:
        run = db.execute(select(ScenarioRun).where(ScenarioRun.code == ctx.scenario_id.value)).scalar_one_or_none()
        if run is not None:
            start, end = max(_utc(run.start_ts), ctx.window_start), min(_utc(run.end_ts), ctx.window_end)
    prev = ctx.as_of
    nxt = prev + timedelta(minutes=body.step_minutes)
    wrapped = False
    if prev < start or prev >= end or nxt >= end:
        nxt, wrapped = start, True
    a, b = _snapshot(db, ctx, prev), _snapshot(db, ctx, nxt)
    headline = [
        _kpi("throughput_tph", "Throughput (last complete hour)", "t/h", b["throughput"], a["throughput"], nxt, "process_hourly", TrendDirection.up),
        _kpi("oer_4h_pct", "OER (rolling 4 complete hours)", "%", b["oer4"], a["oer4"], nxt, "process_hourly (ratio of sums)", TrendDirection.up),
        _kpi("active_alerts", "Active alerts", "alerts", b["alerts"], a["alerts"], nxt, "alerts", TrendDirection.down),
    ]
    if ctx.scenario_id is not None and run is not None and run.primary_equipment_id:
        eq = db.get(Equipment, run.primary_equipment_id)
        from app.services.maintenance_health import load_assessments  # noqa: PLC0415

        base = ctx.model_copy(update={"session_id": None})
        ra = load_assessments(db, base.model_copy(update={"as_of": prev}), [eq.id], active_wo={}).get(eq.id)
        rb = load_assessments(db, base.model_copy(update={"as_of": nxt}), [eq.id], active_wo={}).get(eq.id)
        if ra and rb:
            headline.append(_kpi("primary_equipment_risk_index", f"{eq.code} relative risk index (not a probability)", "index 0-100", rb.risk_score, ra.risk_score, nxt, "rule-based risk index", TrendDirection.down))
    new_ids = [] if wrapped else list(db.execute(select(Alert.id).where(Alert.raised_at > prev, Alert.raised_at <= nxt).order_by(Alert.raised_at)).scalars())
    return TickResponse(
        previous_as_of=prev, next_as_of=nxt, wrapped=wrapped, headline=headline, new_alert_ids=new_ids, step_minutes=body.step_minutes,
        scenario_id=ctx.scenario_id.value if ctx.scenario_id else None, window_start=start, window_end=end,
    )


def main() -> None:  # pragma: no cover - thin CLI for cron / entrypoint
    from app.config import get_settings  # noqa: PLC0415
    from app.db.session import get_sessionmaker  # noqa: PLC0415

    ap = argparse.ArgumentParser(description="Demo session retention")
    ap.add_argument("--purge-idle-hours", type=float, required=True)
    args = ap.parse_args()
    with get_sessionmaker(get_settings().database_url)() as db:
        print(purge_idle_sessions(db, args.purge_idle_hours))


if __name__ == "__main__":  # pragma: no cover
    main()
