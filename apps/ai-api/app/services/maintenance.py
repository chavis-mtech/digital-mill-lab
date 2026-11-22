"""Equipment registry, sensor series, maintenance history, downtime analysis and impact what-if (DML-051/052/057/058).

Owner: backend-b. Health states and the risk index come from `maintenance_health` (one shared definition with the
process twin). Every read respects the demo clock: no sample, event or alert with a timestamp after `as_of` is used.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from statistics import median
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import ApiError, bad_request, not_found
from app.models import (
    Alert,
    AnomalyEvent,
    Equipment,
    Facility,
    MaintenanceEvent,
    ProcessHourly,
    Sensor,
    SensorReading,
    Technician,
)
from app.models.enums import EquipmentType, HealthState, StageCode
from app.schemas.common import Assumption, FactTag, Formula, NormalRange, Period, Provenance, Quantity, Series, SeriesPoint
from app.schemas.maintenance import (
    DowntimeAnalysisResponse,
    DowntimeBucket,
    EquipmentDetail,
    EquipmentHealth,
    EquipmentListResponse,
    EquipmentSummary,
    ImpactScenario,
    MaintenanceEventOut,
    MaintenanceHistoryResponse,
    MaintenanceImpactRequest,
    MaintenanceImpactResponse,
    SensorInfo,
    SensorLimits,
    SensorSeriesResponse,
    SeriesMarker,
    TechnicianListResponse,
    TechnicianOut,
)
from app.services.demo_context import DemoContext, provenance, session_filter
from app.services.kpi_common import price_map, price_on
from app.services.maintenance_health import (
    HEALTH_RULES_VERSION,
    Assessment,
    health_out,
    load_assessments,
    risk_band,
)
from app.services.workorders import load_visible, maintenance_status_map

IMPACT_VERSION = "impact-formulas@1.0"
MAX_SERIES_POINTS = 20_000
RESOLUTION_ORDER = ["raw", "10min", "hour", "day"]
BUCKET_S = {"10min": 600, "hour": 3600, "day": 86400}


def _utc(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def _prov(source: str, ctx: DemoContext, kind: str = "synthetic_actual", model_version: str | None = None) -> Provenance:
    return Provenance(**provenance(kind, source, ctx, model_version))


# ------------------------------------------------------------------ registry
def _summary(a: Assessment, ms: dict[int, tuple[str, list[int]]]) -> EquipmentSummary:
    return EquipmentSummary(
        id=a.equipment_id, code=a.code, name=a.name, equipment_type=a.equipment_type, process_stage_code=StageCode(a.stage_code), criticality=a.criticality,
        health_state=a.state, risk_score=a.risk_score, open_work_orders=a.active_work_orders, active_alerts=len(a.open_alerts),
        maintenance_status=ms.get(a.equipment_id, ("none", []))[0], triggered_by=a.triggered_by[:4], risk_band=risk_band(a.risk_score),
    )


def list_equipment(
    db: Session, ctx: DemoContext, stage_code: str | None, equipment_type: str | None, health_state: HealthState | None, sort: str = "stage"
) -> EquipmentListResponse:
    if stage_code is not None and stage_code.upper() not in {s.value for s in StageCode}:
        bad_request("invalid_stage_code", "Unknown stage_code", {"allowed": [s.value for s in StageCode]})
    if equipment_type is not None and equipment_type.lower() not in {t.value for t in EquipmentType}:
        bad_request("invalid_equipment_type", "Unknown equipment_type", {"allowed": [t.value for t in EquipmentType]})
    ms = maintenance_status_map(db, ctx)
    assessments = list(load_assessments(db, ctx).values())
    counts = {s.value: 0 for s in HealthState}
    for a in assessments:
        counts[a.state.value] += 1
    items = assessments
    if stage_code:
        items = [a for a in items if a.stage_code == stage_code.upper()]
    if equipment_type:
        items = [a for a in items if a.equipment_type == equipment_type.lower()]
    if health_state:
        items = [a for a in items if a.state == health_state]
    if sort == "risk":
        items = sorted(items, key=lambda a: (-a.risk_score, a.code))
    out = [_summary(a, ms) for a in items]
    return EquipmentListResponse(
        items=out, total=len(out), counts_by_state=counts, as_of=ctx.as_of,
        provenance=_prov("sensor_readings + alerts + work orders (rule-based health criteria)", ctx, model_version=HEALTH_RULES_VERSION),
        health_rules_version=HEALTH_RULES_VERSION,
    )


def _one(db: Session, ctx: DemoContext, equipment_id: int) -> Assessment:
    res = load_assessments(db, ctx, [equipment_id])
    if equipment_id not in res:
        not_found("equipment", equipment_id)
    return res[equipment_id]


def equipment_health(db: Session, ctx: DemoContext, equipment_id: int) -> EquipmentHealth:
    a = _one(db, ctx, equipment_id)
    h = health_out(a, ctx)
    st, ids = maintenance_status_map(db, ctx).get(equipment_id, ("none", []))
    h.maintenance_status, h.active_work_order_ids = st, ids
    return h


def equipment_detail(db: Session, ctx: DemoContext, equipment_id: int) -> EquipmentDetail:
    a = _one(db, ctx, equipment_id)
    eq = db.get(Equipment, equipment_id)
    h = health_out(a, ctx)
    st, ids = maintenance_status_map(db, ctx).get(equipment_id, ("none", []))
    h.maintenance_status, h.active_work_order_ids = st, ids
    sensors = []
    for s in a.sensors:
        latest = None
        if s.latest is not None:
            latest = Quantity(value=round(s.latest[1], 3), unit=s.unit, provenance=_prov(f"sensor_readings:{s.code}", ctx))
        nr = None
        if s.normal_min is not None or s.normal_max is not None:
            nr = NormalRange(low=s.normal_min, high=s.normal_max, unit=s.unit, basis="sensor engineering range (sensors.normal_min / normal_max)")
        sensors.append(SensorInfo(id=s.sensor_id, code=s.code, name=s.name, sensor_type=s.sensor_type, unit=s.unit, latest=latest, normal_range=nr, warn_limit=s.warn, crit_limit=s.crit))
    sv = a.service
    return EquipmentDetail(
        id=a.equipment_id, code=a.code, name=a.name, equipment_type=a.equipment_type, process_stage_code=StageCode(a.stage_code), criticality=a.criticality,
        manufacturer=eq.manufacturer, install_date=eq.install_date, rated_power_kw=eq.rated_power_kw, sensors=sensors, health=h, running_hours=a.running_hours,
        last_maintenance_at=a.last_maintenance_ts, maintenance_status=st, active_work_order_ids=ids,
        days_since_last_service=None if sv.last_event_ts is None else round((ctx.as_of - sv.last_event_ts).total_seconds() / 86400, 1), service_interval=sv.note,
    )


# ------------------------------------------------------------------ sensor series
def _to_utc_input(ts: datetime, ctx: DemoContext) -> datetime:
    return ts.replace(tzinfo=ZoneInfo(ctx.timezone)).astimezone(UTC) if ts.tzinfo is None else ts.astimezone(UTC)


def sensor_series(
    db: Session, ctx: DemoContext, equipment_id: int, sensor_codes: list[str] | None, start: datetime | None, end: datetime | None, resolution: str, agg: str = "mean"
) -> SensorSeriesResponse:
    eq = db.get(Equipment, equipment_id)
    if eq is None:
        not_found("equipment", equipment_id)
    sensors = list(db.execute(select(Sensor).where(Sensor.equipment_id == equipment_id).order_by(Sensor.id)).scalars())
    if sensor_codes:
        known = {s.code for s in sensors}
        bad = [c for c in sensor_codes if c not in known]
        if bad:
            bad_request("unknown_sensor_code", "Sensor code(s) not on this equipment", {"unknown": bad, "allowed": sorted(known)})
        sensors = [s for s in sensors if s.code in set(sensor_codes)]
    end_ts = min(_to_utc_input(end, ctx), ctx.as_of) if end else ctx.as_of  # never past the demo clock
    start_ts = _to_utc_input(start, ctx) if start else end_ts - timedelta(days=7)
    start_ts = max(start_ts, ctx.window_start)
    if start_ts >= end_ts:
        bad_request("invalid_range", "start must be before end (end is clipped to the demo clock)", {"start": start_ts.isoformat(), "end": end_ts.isoformat()})
    span = (end_ts - start_ts).total_seconds()
    effective = resolution
    note = None

    def est(res: str) -> float:
        total = 0.0
        for s in sensors:
            step = max(s.sampling_seconds, BUCKET_S.get(res, 0))
            total += span / step
        return total

    while est(effective) > MAX_SERIES_POINTS and effective != "day":
        effective = RESOLUTION_ORDER[RESOLUTION_ORDER.index(effective) + 1]
    if effective != resolution:
        note = f"Requested resolution '{resolution}' would return more than {MAX_SERIES_POINTS} points; downsampled to '{effective}'."
    bucket = BUCKET_S.get(effective)
    off = int(datetime.now(ZoneInfo(ctx.timezone)).utcoffset().total_seconds()) if effective == "day" else 0
    series: list[Series] = []
    prov = _prov("sensor_readings (downsampled server-side)", ctx)
    for s in sensors:
        rows = db.execute(
            select(SensorReading.ts, SensorReading.value).where(
                SensorReading.sensor_id == s.id, SensorReading.ts >= start_ts, SensorReading.ts <= end_ts, SensorReading.quality == "good"
            ).order_by(SensorReading.ts)
        ).all()
        if bucket is None:
            pts = [SeriesPoint(t=_utc(t), v=round(v, 4)) for t, v in rows]
        else:
            groups: dict[int, list[float]] = defaultdict(list)
            for t, v in rows:
                groups[int((_utc(t).timestamp() + off) // bucket)].append(v)
            pts = []
            for k in sorted(groups):
                vals = groups[k]
                v = max(vals) if agg == "max" else sum(vals) / len(vals)
                pts.append(SeriesPoint(t=datetime.fromtimestamp(k * bucket - off, UTC), v=round(v, 4)))
        series.append(Series(key=s.code, label=s.name, unit=s.unit, points=pts, provenance=prov))
    ranges = {
        s.code: NormalRange(low=s.normal_min, high=s.normal_max, unit=s.unit, basis="sensor engineering range (sensors.normal_min / normal_max)")
        for s in sensors if s.normal_min is not None or s.normal_max is not None
    }
    limits = {s.code: SensorLimits(warn_limit=s.warn_limit, crit_limit=s.crit_limit, low_is_bad=bool(s.low_is_bad)) for s in sensors if s.warn_limit is not None or s.crit_limit is not None}
    anomalies: list[SeriesMarker] = []
    try:
        for e in db.execute(
            select(AnomalyEvent).where(AnomalyEvent.equipment_id == equipment_id, AnomalyEvent.start_ts <= end_ts, AnomalyEvent.start_ts <= ctx.as_of).order_by(AnomalyEvent.start_ts)
        ).scalars():
            if e.end_ts is not None and _utc(e.end_ts) < start_ts:
                continue
            anomalies.append(
                SeriesMarker(
                    kind="anomaly", id=e.id, code=e.code, start_ts=_utc(e.start_ts), end_ts=_utc(e.end_ts) if e.end_ts and _utc(e.end_ts) <= ctx.as_of else None,
                    peak_ts=_utc(e.peak_ts) if e.peak_ts and _utc(e.peak_ts) <= ctx.as_of else None, severity=e.severity, score=e.score, label=e.detector,
                )
            )
    except Exception:  # noqa: BLE001 - table may be absent in an unseeded DB; markers are optional
        db.rollback()
    alert_markers = []
    marker_alerts = db.execute(
        select(Alert).where(Alert.equipment_id == equipment_id, Alert.raised_at >= start_ts, Alert.raised_at <= end_ts).order_by(Alert.raised_at)
    ).scalars().all()
    from app.services.kpi_alerts import ml_views  # noqa: PLC0415 - lazy import (QA-16)

    marker_views = ml_views(db, ctx.as_of, list(marker_alerts))
    for al in marker_alerts:
        try:
            sc = json.loads(al.evidence_json or "{}").get("sensor_code")
        except ValueError:
            sc = None
        resolved = _utc(al.resolved_at) if al.resolved_at and _utc(al.resolved_at) <= ctx.as_of else None
        alert_markers.append(SeriesMarker(kind="alert", id=al.id, code=al.code, start_ts=_utc(al.raised_at), end_ts=resolved, severity=marker_views.get(al.id, (al.severity, al.title))[0], label=marker_views.get(al.id, (al.severity, al.title))[1], sensor_code=sc))
    return SensorSeriesResponse(
        equipment_id=equipment_id, resolution=effective, series=series, normal_ranges=ranges, start=start_ts, end=end_ts, requested_resolution=resolution,
        aggregation=agg if bucket else "none", limits=limits, anomaly_markers=anomalies, alert_markers=alert_markers, note=note,
    )


# ------------------------------------------------------------------ history / downtime
def _period_days(period: Period) -> int:
    if period == Period.today:
        return 1
    if period == Period.last_7d:
        return 7
    if period == Period.last_30d:
        return 30
    bad_request("unsupported_period", "period=custom is not supported here; use today, 7d or 30d")


def _event_out(e: MaintenanceEvent, as_of: datetime) -> MaintenanceEventOut:
    end = _utc(e.end_ts) if e.end_ts else None
    downtime = e.downtime_min
    if end is not None and end > as_of:  # ongoing at the demo clock: do not show the future end
        downtime = max(0.0, (as_of - _utc(e.start_ts)).total_seconds() / 60.0)
        end = None
    cost = None if e.parts_cost_thb is None and e.labour_cost_thb is None else (e.parts_cost_thb or 0) + (e.labour_cost_thb or 0)
    return MaintenanceEventOut(
        id=e.id, event_type=e.event_type, start_ts=_utc(e.start_ts), end_ts=end, downtime_min=round(downtime, 1), planned=bool(e.planned),
        description=e.description, work_order_id=e.work_order_id, cost_thb=cost,
    )


def history(db: Session, ctx: DemoContext, equipment_id: int, period: Period) -> MaintenanceHistoryResponse:
    if db.get(Equipment, equipment_id) is None:
        not_found("equipment", equipment_id)
    days = _period_days(period)
    start, end = ctx.period_bounds(days)
    rows = db.execute(
        select(MaintenanceEvent).where(
            MaintenanceEvent.equipment_id == equipment_id, MaintenanceEvent.start_ts <= end, func.coalesce(MaintenanceEvent.end_ts, MaintenanceEvent.start_ts) >= start,
            session_filter(MaintenanceEvent.session_id, ctx),
        ).order_by(MaintenanceEvent.start_ts.desc(), MaintenanceEvent.id.desc())
    ).scalars().all()
    items = [_event_out(e, ctx.as_of) for e in rows]
    total_h = sum(i.downtime_min for i in items) / 60.0
    failures = [i for i in items if i.event_type == "breakdown"]
    unplanned_h = sum(i.downtime_min for i in items if not i.planned) / 60.0
    window_h = (end - start).total_seconds() / 3600.0
    mtbf = round((window_h - unplanned_h) / len(failures), 1) if failures else None
    mttr = round(sum(i.downtime_min for i in failures) / 60.0 / len(failures), 2) if failures else None
    costs = [i.cost_thb for i in items if i.cost_thb is not None]
    return MaintenanceHistoryResponse(
        equipment_id=equipment_id, items=items, total_downtime_h=round(total_h, 2), mtbf_h=mtbf, mttr_h=mttr, period=period.value, window_start=start, window_end=end,
        failures=len(failures), total_cost_thb=round(sum(costs), 0) if costs else None,
        mtbf_basis="calendar basis: (window hours - unplanned downtime hours) / breakdown events; running hours are not available for every machine",
        provenance=_prov("maintenance_events", ctx),
    )


def _distribute(start: datetime, end: datetime, tz: ZoneInfo):
    """Yield (local_date, local_hour, minutes) for an interval, split at local-hour boundaries."""
    cur = start.astimezone(tz)
    stop = end.astimezone(tz)
    while cur < stop:
        nxt = min(cur.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1), stop)
        yield cur.date(), cur.hour, (nxt - cur).total_seconds() / 60.0
        cur = nxt


def downtime_analysis(db: Session, ctx: DemoContext, period: Period) -> DowntimeAnalysisResponse:
    days = _period_days(period)
    start, end = ctx.period_bounds(days)
    tz = ZoneInfo(ctx.timezone)
    rows = db.execute(
        select(MaintenanceEvent, Equipment.code, Equipment.name).join(Equipment, Equipment.id == MaintenanceEvent.equipment_id).where(
            MaintenanceEvent.start_ts <= end, func.coalesce(MaintenanceEvent.end_ts, MaintenanceEvent.start_ts) >= start, session_filter(MaintenanceEvent.session_id, ctx)
        )
    ).all()
    by_eq: dict[str, list[float]] = defaultdict(lambda: [0.0, 0, ""])
    by_cause: dict[str, list[float]] = defaultdict(lambda: [0.0, 0])
    by_hour: dict[int, list[float]] = defaultdict(lambda: [0.0, 0])
    by_day: dict = defaultdict(float)
    total_min = 0.0
    for e, code, name in rows:
        s0, e0 = max(_utc(e.start_ts), start), min(_utc(e.end_ts) if e.end_ts else _utc(e.start_ts), end)
        mins = max(0.0, (e0 - s0).total_seconds() / 60.0)
        if e.end_ts is not None and e.downtime_min and _utc(e.end_ts) > _utc(e.start_ts):
            mins = min(mins, e.downtime_min) if mins > e.downtime_min else mins
        total_min += mins
        by_eq[code][0] += mins
        by_eq[code][1] += 1
        by_eq[code][2] = name
        by_cause[e.event_type][0] += mins
        by_cause[e.event_type][1] += 1
        seen_hours = set()
        for d, h, m in _distribute(s0, e0, tz):
            by_hour[h][0] += m
            by_day[d] += m
            seen_hours.add(h)
        for h in seen_hours:
            by_hour[h][1] += 1
    # plant availability from the hourly mill state (complete hours only)
    cutoff = ctx.as_of - timedelta(hours=1)
    run, down = db.execute(
        select(func.coalesce(func.sum(ProcessHourly.running_minutes), 0.0), func.coalesce(func.sum(ProcessHourly.downtime_min), 0.0)).where(ProcessHourly.ts >= start, ProcessHourly.ts <= cutoff)
    ).one()
    avail = round(100.0 * (1 - down / (run + down)), 2) if (run + down) > 0 else None
    pts = []
    d = start.astimezone(tz).date()
    last = min(end, ctx.as_of).astimezone(tz).date()
    while d <= last:
        pts.append(SeriesPoint(t=datetime.combine(d, datetime.min.time(), tzinfo=tz).astimezone(UTC), v=round(by_day.get(d, 0.0) / 60.0, 3)))
        d += timedelta(days=1)
    mk = lambda items, lab: [DowntimeBucket(key=k, label=lab(k, v), downtime_h=round(v[0] / 60.0, 2), events=int(v[1])) for k, v in sorted(items.items(), key=lambda kv: -kv[1][0])]  # noqa: E731
    return DowntimeAnalysisResponse(
        total_downtime_h=round(total_min / 60.0, 2), availability_pct=avail,
        by_equipment=mk(by_eq, lambda k, v: f"{k} - {v[2]}"), by_cause=mk(by_cause, lambda k, v: k.replace("_", " ").capitalize()),
        by_hour_of_day=[DowntimeBucket(key=f"{h:02d}", label=f"{h:02d}:00-{h:02d}:59", downtime_h=round(by_hour[h][0] / 60.0, 2) if h in by_hour else 0.0, events=int(by_hour[h][1]) if h in by_hour else 0) for h in range(24)],
        series=Series(key="downtime_h_per_day", label="Maintenance downtime per mill day", unit="h", points=pts, provenance=_prov("maintenance_events", ctx)),
        provenance=_prov("maintenance_events (equipment downtime) + process_hourly (plant availability = 1 - downtime/(running+downtime))", ctx),
    )


# ------------------------------------------------------------------ technicians
def technicians(db: Session, ctx: DemoContext) -> TechnicianListResponse:
    load: dict[int, int] = defaultdict(int)
    from app.services.workorders import ACTIVE  # noqa: PLC0415

    for v in load_visible(db, ctx):
        if v.status in ACTIVE and v.technician_id:
            load[v.technician_id] += 1
    rows = db.execute(select(Technician).where(Technician.is_active.is_(True)).order_by(Technician.id)).scalars()
    return TechnicianListResponse(
        items=[TechnicianOut(id=t.id, code=t.code, display_name=t.display_name, skill=t.skill, shift_code=t.shift_code, open_assignments=load.get(t.id, 0)) for t in rows]
    )


# ------------------------------------------------------------------ impact what-if (AI-C06)
def _recent_mill_stats(db: Session, ctx: DemoContext, days: int = 7) -> dict:
    cutoff = ctx.as_of - timedelta(hours=1)  # only complete hours
    start = max(ctx.window_start, cutoff - timedelta(days=days))
    rows = db.execute(
        select(ProcessHourly.ffb_processed_t, ProcessHourly.cpo_t, ProcessHourly.running_minutes, ProcessHourly.downtime_min, ProcessHourly.ffb_waiting_t).where(
            ProcessHourly.ts > start, ProcessHourly.ts <= cutoff
        )
    ).all()
    if not rows:
        raise ApiError(422, "insufficient_data", "No complete mill hours before the demo clock to derive defaults; provide throughput_tph and oer_pct explicitly.")
    ffb = sum(r[0] or 0 for r in rows)
    cpo = sum(r[1] or 0 for r in rows)
    run_h = sum(r[2] or 0 for r in rows) / 60.0
    return {
        "hours": len(rows), "ffb_t": ffb, "cpo_t": cpo, "run_h": run_h,
        "throughput_tph": ffb / run_h if run_h > 0 else 0.0, "oer_pct": 100.0 * cpo / ffb if ffb > 0 else None,
        "idle_share": sum(1 for r in rows if (r[0] or 0) < 6.0) / len(rows),  # hours below 10% of the 60 t/h rated capacity
        "ramp_t": sum(r[4] or 0 for r in rows[-24:]) / max(1, len(rows[-24:])),
    }


def _capacity_loss(db: Session, eq: Equipment | None, capacity_tph: float, throughput: float, override: float | None) -> tuple[float, str]:
    """(lost t/h while the equipment is down, basis). Series-critical -> all; parallel group -> shortfall vs remaining capacity."""
    if override is not None:
        return throughput * override, f"user-entered capacity_loss_fraction = {override:g}"
    if eq is None:
        return throughput, "no equipment selected: the whole mill is assumed stopped"
    if eq.criticality != "A":
        return 0.0, f"criticality {eq.criticality}: not on the critical production path in this model, so lost throughput is 0 unless you set capacity_loss_fraction"
    n = db.execute(
        select(func.count()).select_from(Equipment).where(Equipment.process_stage_id == eq.process_stage_id, Equipment.equipment_type == eq.equipment_type, Equipment.is_active.is_(True))
    ).scalar_one()
    if n <= 1:
        return throughput, f"{eq.code} is the only {eq.equipment_type} on the critical path: all throughput is lost while it is down"
    remaining = capacity_tph * (n - 1) / n
    lost = max(0.0, throughput - remaining)
    return lost, f"{n} parallel {eq.equipment_type} units share the {capacity_tph:g} t/h mill capacity; with one down {remaining:g} t/h remains, so lost = max(0, {throughput:.1f} - {remaining:g})"


def _default_costs(db: Session, ctx: DemoContext, eq: Equipment | None) -> tuple[float | None, float | None]:
    """(planned, unplanned) median repair cost (parts + labour) of past events of the same equipment type, <= as_of."""
    q = select(MaintenanceEvent.event_type, MaintenanceEvent.planned, MaintenanceEvent.parts_cost_thb, MaintenanceEvent.labour_cost_thb).join(Equipment, Equipment.id == MaintenanceEvent.equipment_id).where(
        MaintenanceEvent.end_ts <= ctx.as_of, session_filter(MaintenanceEvent.session_id, ctx), MaintenanceEvent.event_type.in_(["corrective", "breakdown", "overhaul"])
    )
    if eq is not None:
        q = q.where(Equipment.equipment_type == eq.equipment_type)
    planned, unplanned = [], []
    for _t, pl, parts, lab in db.execute(q).all():
        if parts is None and lab is None:
            continue
        (planned if pl else unplanned).append((parts or 0) + (lab or 0))
    return (median(planned) if planned else None), (median(unplanned) if unplanned else None)


def _impact_calc(
    *, downtime_h: float, lost_tph: float, oer: float, price_thb_kg: float, planned: bool, idle_share: float, spare_tph: float, recovery_h: float, cost: float
) -> dict:
    gross = downtime_h * lost_tph
    avoided = gross * idle_share if planned else 0.0
    net = gross - avoided
    recovered = min(net, recovery_h * spare_tph)
    lost_ffb = net - recovered
    lost_cpo = lost_ffb * oer / 100.0
    lost_value = lost_cpo * 1000.0 * price_thb_kg
    return {"gross": gross, "avoided": avoided, "net": net, "recovered": recovered, "lost_ffb": lost_ffb, "lost_cpo": lost_cpo, "lost_value": lost_value, "total": lost_value + cost}


def impact(db: Session, ctx: DemoContext, body: MaintenanceImpactRequest) -> MaintenanceImpactResponse:
    eq = None
    if body.equipment_id is not None:
        eq = db.get(Equipment, body.equipment_id)
        if eq is None:
            not_found("equipment", body.equipment_id)
    stats = _recent_mill_stats(db, ctx)
    cap = db.execute(select(Facility.capacity_tph).limit(1)).scalar_one_or_none() or 60.0
    throughput = body.throughput_tph if body.throughput_tph is not None else stats["throughput_tph"]
    oer = body.oer_pct if body.oer_pct is not None else stats["oer_pct"]
    if oer is None:
        raise ApiError(422, "insufficient_data", "Cannot derive a default OER; provide oer_pct.")
    price_kg = body.cpo_price_thb_per_kg
    price_src = "user input"
    if price_kg is None:
        price_kg = price_on(price_map(db, "cpo", ctx.business_date), ctx.business_date)
        price_src = f"prices.cpo on {ctx.business_date} (illustrative synthetic series)"
        if price_kg is None:
            raise ApiError(422, "insufficient_data", "No CPO price before the demo clock; provide cpo_price_thb_per_kg.")
    lost_tph, basis = _capacity_loss(db, eq, cap, throughput, body.capacity_loss_fraction)
    spare = max(0.0, cap - throughput)
    rec_h = body.recovery_hours or 0.0
    p_cost, u_cost = _default_costs(db, ctx, eq)
    if body.maintenance_cost_thb is not None:
        cost_planned = cost_unplanned = body.maintenance_cost_thb
        cost_src = "user input (used for both scenarios)"
    else:
        cost_planned = p_cost if p_cost is not None else (u_cost or 0.0)
        cost_unplanned = u_cost if u_cost is not None else (p_cost or 0.0)
        cost_src = "median parts+labour of past corrective/breakdown events of the same equipment type in the synthetic history (0 if none)"
    common = dict(downtime_h=body.downtime_hours, lost_tph=lost_tph, oer=oer, price_thb_kg=price_kg, idle_share=stats["idle_share"], spare_tph=spare, recovery_h=rec_h)
    plan = _impact_calc(planned=True, cost=cost_planned, **common)
    rtf = _impact_calc(planned=False, cost=cost_unplanned, **common)
    sel, sel_cost = (plan, cost_planned) if body.planned else (rtf, cost_unplanned)
    if body.maintenance_cost_thb is not None:
        sel_cost = body.maintenance_cost_thb

    def sc(key: str, label: str, c: dict, cost: float, desc: str) -> ImpactScenario:
        return ImpactScenario(key=key, label=label, lost_ffb_processing_t=round(c["lost_ffb"], 2), lost_cpo_opportunity_t=round(c["lost_cpo"], 3), lost_value_thb=round(c["lost_value"], 0),
                              maintenance_cost_thb=round(cost, 0), total_impact_thb=round(c["lost_value"] + cost, 0), description=desc)

    comparison = [
        sc("planned_stop", "Planned stop", plan, cost_planned, f"Scheduled into low-intake hours: {stats['idle_share'] * 100:.0f}% of the last 7 days' hours the mill was idle anyway, so that share of the stop displaces no production."),
        sc("run_to_failure", "Run to failure (unplanned breakdown)", rtf, cost_unplanned, "Unplanned stop during production: all downtime hours displace production; only spare capacity can recover the backlog."),
    ]
    ex = eq.code if eq else "mill"
    formulas = [
        Formula(key="lost_tph", label=f"Throughput lost while {ex} is down", expression="lost_tph = f(equipment criticality, parallel group, throughput, capacity)", inputs={"throughput_tph": round(throughput, 3), "mill_capacity_tph": cap, "capacity_loss_fraction": body.capacity_loss_fraction, "basis": basis}, result=round(lost_tph, 3), unit="t FFB/h"),
        Formula(key="gross_lost_ffb_t", label="FFB not processed during the stop", expression="gross_lost_ffb_t = downtime_h x lost_tph", inputs={"downtime_h": body.downtime_hours, "lost_tph": round(lost_tph, 3)}, result=round(sel["gross"], 3), unit="t FFB"),
        Formula(key="avoided_ffb_t", label="Loss avoided by timing a planned stop into idle hours", expression="avoided_ffb_t = gross_lost_ffb_t x idle_hour_share (planned only)", inputs={"gross_lost_ffb_t": round(sel["gross"], 3), "idle_hour_share": round(stats["idle_share"], 4), "planned": str(body.planned)}, result=round(sel["avoided"], 3), unit="t FFB"),
        Formula(key="recovered_ffb_t", label="Backlog recovered with spare capacity", expression="recovered_ffb_t = min(net_lost_ffb_t, recovery_hours x spare_capacity_tph)", inputs={"net_lost_ffb_t": round(sel["net"], 3), "recovery_hours": rec_h, "spare_capacity_tph": round(spare, 3)}, result=round(sel["recovered"], 3), unit="t FFB"),
        Formula(key="lost_ffb_processing_t", label="Lost FFB processing", expression="lost_ffb_processing_t = net_lost_ffb_t - recovered_ffb_t", inputs={"net_lost_ffb_t": round(sel["net"], 3), "recovered_ffb_t": round(sel["recovered"], 3)}, result=round(sel["lost_ffb"], 3), unit="t FFB"),
        Formula(key="lost_cpo_opportunity_t", label="Lost CPO production opportunity", expression="lost_cpo_t = lost_ffb_processing_t x OER / 100", inputs={"lost_ffb_processing_t": round(sel["lost_ffb"], 3), "oer_pct": round(oer, 3)}, result=round(sel["lost_cpo"], 4), unit="t CPO"),
        Formula(key="lost_value_thb", label="Lost value (illustrative price)", expression="lost_value_thb = lost_cpo_t x 1000 x cpo_price_thb_per_kg", inputs={"lost_cpo_t": round(sel["lost_cpo"], 4), "cpo_price_thb_per_kg": round(price_kg, 3)}, result=round(sel["lost_value"], 0), unit="THB"),
        Formula(key="total_impact_thb", label="Total impact", expression="total_impact_thb = lost_value_thb + maintenance_cost_thb", inputs={"lost_value_thb": round(sel["lost_value"], 0), "maintenance_cost_thb": round(sel_cost, 0)}, result=round(sel["lost_value"] + sel_cost, 0), unit="THB"),
    ]
    A = Assumption
    assumptions = [
        A(key="throughput_tph", label="Throughput while running", value=round(throughput, 2), unit="t FFB/h", tag=FactTag.synthetic_demonstration_data, source="process_hourly, last 7 days to the demo clock (ratio of sums)" if body.throughput_tph is None else "user input"),
        A(key="oer_pct", label="Oil extraction rate", value=round(oer, 3), unit="% of FFB", tag=FactTag.synthetic_demonstration_data, source="process_hourly, last 7 days (ratio of sums)" if body.oer_pct is None else "user input"),
        A(key="cpo_price_thb_per_kg", label="CPO price", value=round(price_kg, 3), unit="THB/kg", tag=FactTag.synthetic_demonstration_data, source=price_src),
        A(key="mill_capacity_tph", label="Rated mill capacity", value=cap, unit="t FFB/h", tag=FactTag.synthetic_demonstration_data, source="facilities.capacity_tph", editable=False),
        A(key="capacity_loss_basis", label="How much throughput is lost while the equipment is down", value=basis, tag=FactTag.engineering_assumption, source="parallel-group / criticality rule in services/maintenance.py (override with capacity_loss_fraction)"),
        A(key="idle_hour_share", label="Share of hours the mill is idle anyway (planned stops hide in these)", value=round(stats["idle_share"], 4), tag=FactTag.synthetic_demonstration_data, source="process_hourly, last 7 days: hours below 6 t FFB (10% of rated capacity)"),
        A(key="spare_capacity_tph", label="Spare capacity available to recover backlog", value=round(spare, 2), unit="t FFB/h", tag=FactTag.engineering_assumption, source="rated capacity - current throughput"),
        A(key="supply_available", label="FFB supply is available to refill the backlog", value="yes", tag=FactTag.engineering_assumption, source="if the mill is supply-constrained output is deferred rather than lost - this estimate is then an upper bound"),
        A(key="maintenance_cost", label="Maintenance cost (parts + labour)", value=round(sel_cost, 0), unit="THB", tag=FactTag.synthetic_demonstration_data, source=cost_src),
        A(key="ffb_quality_penalty", label="FFB waiting-time quality penalty (FFA)", value="not modelled", tag=FactTag.engineering_assumption, source="a long stop raises FFA of waiting fruit; ignored here"),
    ]
    required = [
        "Real equipment dependency data (P&ID / criticality analysis): which stops actually throttle the line and by how much.",
        "Measured ramp stock and intake schedule: is the mill capacity- or supply-constrained at the time of the stop?",
        "Historical failure and repair-cost records (CMMS) and spare-part lead times for this equipment type.",
        "Planned-stop windows and crew availability from the production plan.",
        "Contracted CPO price / penalties and the quality (FFA) impact of waiting fruit.",
        "Downtime reason codes from MES/SCADA to separate equipment downtime from starvation and utility stops.",
    ]
    rec_text = (
        f"Planned stop: scheduled into low-intake hours ({stats['idle_share'] * 100:.0f}% of recent hours idle) so only {(1 - stats['idle_share']) * 100:.0f}% of the stop displaces production."
        if body.planned
        else f"Run to failure: unplanned stop of {body.downtime_hours:g} h; backlog recovery limited to {spare:.1f} t/h of spare capacity x {rec_h:g} recovery hours."
    )
    return MaintenanceImpactResponse(
        lost_ffb_processing_t=round(sel["lost_ffb"], 2), lost_cpo_opportunity_t=round(sel["lost_cpo"], 3), lost_value_thb=round(sel["lost_value"], 0),
        maintenance_cost_thb=round(sel_cost, 0), total_impact_thb=round(sel["lost_value"] + sel_cost, 0), recovery_scenario=rec_text, formulas=formulas, assumptions=assumptions,
        required_real_data=required, provenance=_prov("process_hourly + prices + maintenance_events; formulas echoed", ctx, "what_if", IMPACT_VERSION),
        comparison=comparison, equipment_code=eq.code if eq else None,
    )

