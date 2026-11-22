"""Equipment health (AI-C01) and the rule-based failure-risk index (AI-C03). Owner: backend-b.

Everything here is a *documented rule set over synthetic readings at the demo clock* - no machine learning, no
randomness, nothing hard-coded per equipment. Every state is returned together with the criteria and the readings
that produced it (evidence), so an engineer can verify the logic by hand. Samples with ts > as_of are never read.

HEALTH STATE - ONE definition for the whole product (shared with the process twin, ``services/kpi_health.py``)
---------------------------------------------------------------------------------------------------------------
Per sensor with limits (``sensors.warn_limit`` / ``crit_limit`` / ``low_is_bad``), evaluated on the LATEST good reading
inside the last 6 h: Normal < warn; Warning >= warn; Critical >= crit (reverse for ``low_is_bad``: Warning <= warn,
Critical <= crit). ``low_is_bad`` process tags (digester/clarifier temperature, boiler drum and steam-header pressure)
read low by design when the mill is stopped, so they are only evaluated while the mill ran in the last complete hour.
Equipment state = worst sensor state, with Maintenance Required when an active work order (open / assigned /
in progress / on hold) exists for the equipment at ``as_of`` in the caller's session. Order:
normal < warning < maintenance_required < critical (a critical reading outranks an open work order).

Evidence that does NOT change the state (so the twin and the maintenance screens can never disagree) but feeds the risk
index and the recommendations, and is shown as informational criteria (``affects_state = false``): the last 3 samples
(is the breach sustained?), the ISO 10816-3 style vibration zone (B/C boundary = warn limit, C/D = crit limit), the
service interval (running hours when a running-hours counter exists, else calendar days since the last non-breakdown
maintenance event) and unresolved alerts.

FAILURE-RISK INDEX (0-100) - a RELATIVE RANKING SCORE, NOT A PROBABILITY
------------------------------------------------------------------------
score = sum of five weighted sub-scores (weights sum to 100):
  condition     40  worst sensor: Critical 1.0; Warning 0.5 + 0.5 * (v - warn)/(crit - warn); Normal 0 up to normal_max,
                    then 0 -> 0.5 linearly between normal_max and warn
  trend         25  7-day linear trend of the daily P90 of vibration/temperature/current (bad direction). Needs >= 4
                    days, R^2 >= 0.5 and a rise >= 10% of normal_max over 6 days. score = clip(1 - days_to_crit/30, 0, 1)
                    (days_to_crit = linear extrapolation - NOT a forecast)
  service       10  running-hours / calendar usage of the service interval: 0 below 50%, 1 at 100%
  alerts        15  unresolved alerts: critical 1.0, high 0.7, medium 0.4, low 0.2
  corroboration 10  distinct sensor TYPES at Warning or worse: 1 -> 0.3, 2 -> 0.7, >= 3 -> 1.0
Limits: weights and break-points are engineering judgement, not fitted to failures; the score is not calibrated on
failure data, so 80 does not mean "80% likely to fail". Use it only to rank equipment against each other.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import (
    Alert,
    AlertStatusChange,
    AnomalyEvent,
    Equipment,
    MaintenanceEvent,
    ProcessStage,
    Sensor,
    SensorReading,
)
from app.models.enums import HealthState
from app.schemas.maintenance import EquipmentHealth, HealthCriterion, RiskComponent
from app.services.demo_context import DemoContext, provenance, session_filter
from app.services.kpi_data import last_complete_hour
from app.services.kpi_health import sensor_state as shared_sensor_state

HEALTH_RULES_VERSION = "health-rules@1.0"
RISK_INDEX_VERSION = "risk-index@1.0"

EVIDENCE_SAMPLES = 3  # last N good samples shown as evidence ("is the breach sustained?")
LOOKBACK_H = 6
TREND_DAYS = 7
TREND_MIN_DAYS = 4
TREND_MIN_R2 = 0.5
TREND_MIN_RISE_FRAC = 0.10
TREND_HORIZON_DAYS = 30.0
FLATLINE_SAMPLES = 8

LIMIT_TYPES = {"vibration", "temperature", "current", "pressure", "load", "flow", "level"}
TREND_TYPES = {"vibration", "temperature", "current"}

# Engineering assumptions (adjustable): service intervals. Calendar days for equipment without a running-hours counter.
ROTATING_TYPES = {
    "screw_press", "pump", "motor", "digester", "thresher", "conveyor", "centrifuge", "other_rotating", "kernel_plant",
    "generator", "turbine",
}
SERVICE_INTERVAL_DAYS = {t: 35 for t in ROTATING_TYPES} | {
    "boiler": 75, "sterilizer": 75, "clarifier_tank": 75, "storage_tank": 75, "weighbridge": 75,
}
# Running-hours basis (only equipment that owns a running_hours sensor). 35 d x ~16.8 h/d ~ 590 h for presses.
SERVICE_INTERVAL_RUNNING_H = {"screw_press": 600.0, "boiler": 1800.0, "turbine": 1800.0, "generator": 250.0}
SERVICE_INTERVAL_TAG = "Engineering Assumption (adjustable): PM round cadence ~weekly in the seeded work orders; flagged after ~5 weeks"

# ISO 10816-3 zone A/B boundary by B/C (= warn) boundary: Group 2 rigid 2.8 -> 1.4, Group 2 flexible 4.5 -> 2.3.
ISO_AB_BY_WARN = {2.8: 1.4, 4.5: 2.3}

RISK_WEIGHTS = {"condition": 40.0, "trend": 25.0, "service": 10.0, "alerts": 15.0, "corroboration": 10.0}
ALERT_SUBSCORE = {"critical": 1.0, "high": 0.7, "medium": 0.4, "low": 0.2, "info": 0.0}
OPEN_ALERT_STATES = {"new", "acknowledged", "in_progress"}

RISK_MEANING = (
    "Relative ranking index (0-100) computed from threshold, trend, service-interval and alert rules over synthetic data. "
    "It is NOT a calibrated failure probability and was not fitted to real failures - use it only to rank equipment."
)
RISK_LIMITS = (
    "Weights and break-points are engineering judgement; no real failure history exists to calibrate them. A high score means "
    "'several documented rules point the same way', not a predicted failure time. Verify on site before acting."
)
RISK_METHOD = (
    "score = 40 x condition + 25 x trend + 10 x service + 15 x alerts + 10 x corroboration (each sub-score 0-1); "
    "see app/services/maintenance_health.py for the exact break-points."
)
STATE_RULE = (
    "Shared definition with the process twin: Critical = any sensor's latest reading at/over its critical limit; Maintenance "
    "Required = an active work order exists (and no sensor is critical); Warning = any sensor's latest reading at/over its warn "
    "limit; otherwise Normal (low-is-bad sensors reversed and only evaluated while the mill runs). Service interval, open alerts "
    "and trends are shown as evidence and feed the risk index but do not change the state."
)

_SEV = {HealthState.normal: 0, HealthState.warning: 1, HealthState.maintenance_required: 2, HealthState.critical: 3}


# ------------------------------------------------------------------ pure rules (unit-tested)
def classify(value: float, warn: float | None, crit: float | None, low_is_bad: bool) -> HealthState:
    """Normal < warn; Warning >= warn; Critical >= crit (reverse for low_is_bad). Delegates to the process twin's function."""
    return HealthState(shared_sensor_state(value, warn, crit, low_is_bad) or "normal")


def worst(a: HealthState, b: HealthState) -> HealthState:
    return a if _SEV[a] >= _SEV[b] else b


def iso_zone(value: float, warn: float | None, crit: float | None) -> str | None:
    """ISO 10816-3 style zone from the sensor limits (B/C = warn, C/D = crit)."""
    if warn is None or crit is None:
        return None
    ab = ISO_AB_BY_WARN.get(round(warn, 1))
    if value >= crit:
        return "D"
    if value >= warn:
        return "C"
    if ab is not None and value < ab:
        return "A"
    return "B" if ab is not None else "A/B"


def percentile(values: list[float], q: float) -> float:
    s = sorted(values)
    k = max(0, min(len(s) - 1, math.ceil(q * len(s)) - 1))
    return s[k]


def linear_fit(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """Ordinary least squares. Returns (slope, intercept, r2)."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return 0.0, my, 0.0
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    slope = sxy / sxx
    intercept = my - slope * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys, strict=True))
    r2 = 0.0 if ss_tot == 0 else max(0.0, 1 - ss_res / ss_tot)
    return slope, intercept, r2


def risk_band(score: float) -> str:
    return "low" if score < 25 else "elevated" if score < 50 else "high" if score < 75 else "very_high"


def clip01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


# ------------------------------------------------------------------ data holders
@dataclass
class SensorAssessment:
    sensor_id: int
    code: str
    name: str
    sensor_type: str
    unit: str
    normal_min: float | None
    normal_max: float | None
    warn: float | None
    crit: float | None
    low_is_bad: bool
    sampling_seconds: int
    samples: list[tuple[datetime, float]] = field(default_factory=list)  # newest last, <= as_of, all good
    window: list[tuple[datetime, float]] = field(default_factory=list)  # the evaluated samples (persistence window)
    latest: tuple[datetime, float] | None = None
    level: HealthState | None = None  # None = not assessable
    reason: str | None = None
    iso: str | None = None
    trend_slope_per_day: float | None = None
    trend_r2: float | None = None
    trend_days_to_crit: float | None = None
    trend_rising: bool = False
    trend_score: float = 0.0
    flatline: bool = False

    @property
    def has_limits(self) -> bool:
        return self.warn is not None or self.crit is not None


@dataclass
class AlertInfo:
    id: int
    code: str
    severity: str
    title: str
    raised_at: datetime
    status: str


@dataclass
class ServiceInfo:
    basis: str  # running_hours | calendar_days | not_assessable
    interval: float | None
    used: float | None
    unit: str
    last_event_ts: datetime | None
    last_event_type: str | None
    overdue: bool | None
    note: str


@dataclass
class Assessment:
    equipment_id: int
    code: str
    name: str
    equipment_type: str
    stage_code: str
    criticality: str
    manufacturer: str | None
    rated_power_kw: float | None
    sensors: list[SensorAssessment]
    open_alerts: list[AlertInfo]
    service: ServiceInfo
    running_hours: float | None
    last_maintenance_ts: datetime | None
    sensor_state: HealthState
    alert_state: HealthState
    state: HealthState
    triggered_by: list[str]
    criteria: list[HealthCriterion]
    risk_score: float
    risk_components: list[RiskComponent]
    anomaly_score: float | None
    data_quality_notes: list[str]
    as_of: datetime
    active_work_orders: int = 0


# ------------------------------------------------------------------ loaders
def _utc(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def effective_alert_status(row: Alert, as_of: datetime, overrides: list[AlertStatusChange]) -> str | None:
    """Status of an alert at the demo clock, or None if it did not exist yet.

    Baseline: raised_at <= as_of; resolved only if resolved_at <= as_of (the stored status is the end-state of the
    whole timeline, so it is NOT used for resolved alerts). Session copy-on-write rows (ADR-014) override the baseline
    from their changed_at (demo clock) onwards.
    """
    if _utc(row.raised_at) > as_of:
        return None
    if row.resolved_at is not None:
        status = "resolved" if _utc(row.resolved_at) <= as_of else "new"
    else:
        status = row.status
    chosen = None
    for ch in overrides:  # already ordered (changed_at, id)
        if _utc(ch.changed_at) <= as_of:
            chosen = ch.to_status
    return chosen or status


def load_alert_overrides(db: Session, ctx: DemoContext, alert_ids: list[int]) -> dict[int, list[AlertStatusChange]]:
    if not alert_ids or ctx.session_id is None:
        return {}
    rows = db.execute(
        select(AlertStatusChange)
        .where(AlertStatusChange.alert_id.in_(alert_ids), AlertStatusChange.session_id == ctx.session_id)
        .order_by(AlertStatusChange.changed_at, AlertStatusChange.id)
    ).scalars()
    out: dict[int, list[AlertStatusChange]] = {}
    for r in rows:
        out.setdefault(r.alert_id, []).append(r)
    return out


def load_open_alerts(db: Session, ctx: DemoContext, equipment_ids: list[int]) -> dict[int, list[AlertInfo]]:
    """Unresolved alerts per equipment at the demo clock (session decisions applied)."""
    if not equipment_ids:
        return {}
    rows = db.execute(
        select(Alert).where(Alert.equipment_id.in_(equipment_ids), Alert.raised_at <= ctx.as_of).order_by(Alert.raised_at, Alert.id)
    ).scalars().all()
    overrides = load_alert_overrides(db, ctx, [r.id for r in rows])
    # QA-16: the stored severity/title of an ML alert describe the episode PEAK (possibly after as_of); use the view at the clock.
    from app.services.kpi_alerts import ml_views  # noqa: PLC0415 - lazy: kpi_alerts imports the health definitions of this module

    views = ml_views(db, ctx.as_of, list(rows))
    out: dict[int, list[AlertInfo]] = {}
    for r in rows:
        status = effective_alert_status(r, ctx.as_of, overrides.get(r.id, []))
        if status in OPEN_ALERT_STATES and r.equipment_id is not None:
            sev, title = views.get(r.id, (r.severity, r.title))
            out.setdefault(r.equipment_id, []).append(AlertInfo(r.id, r.code, sev, title, _utc(r.raised_at), status))
    return out


def _hour_floor(ts: datetime) -> datetime:
    return ts.replace(minute=0, second=0, microsecond=0)


def _load_trend(db: Session, ctx: DemoContext, sensor_ids: list[int], tz: ZoneInfo) -> dict[int, dict[int, list[float]]]:
    """Daily value lists (local mill days, last TREND_DAYS) per sensor id."""
    if not sensor_ids:
        return {}
    first_day = ctx.local_as_of.date() - timedelta(days=TREND_DAYS - 1)
    start = datetime.combine(first_day, time.min, tzinfo=tz).astimezone(UTC)
    start = max(start, ctx.window_start)
    base = datetime.combine(first_day, time.min, tzinfo=tz).astimezone(UTC).timestamp()
    out: dict[int, dict[int, list[float]]] = {}
    rows = db.execute(
        select(SensorReading.sensor_id, SensorReading.ts, SensorReading.value).where(
            SensorReading.sensor_id.in_(sensor_ids), SensorReading.ts >= start, SensorReading.ts <= ctx.as_of, SensorReading.quality == "good"
        )
    )
    for sid, ts, val in rows:
        day = int((_utc(ts).timestamp() - base) // 86400)
        out.setdefault(sid, {}).setdefault(day, []).append(val)
    return out


def _fit_trend(sa: SensorAssessment, days: dict[int, list[float]]) -> None:
    pts = [(d, percentile(v, 0.9)) for d, v in sorted(days.items()) if len(v) >= 6]
    if len(pts) < TREND_MIN_DAYS:
        return
    xs = [float(d) for d, _ in pts]
    ys = [v for _, v in pts]
    slope, intercept, r2 = linear_fit(xs, ys)
    sa.trend_slope_per_day = round(slope, 5)
    sa.trend_r2 = round(r2, 3)
    bad = -slope if sa.low_is_bad else slope
    scale = abs(sa.normal_max) if sa.normal_max else (abs(sa.warn) if sa.warn else 1.0)
    rise6 = bad * 6.0
    sa.trend_rising = bad > 0 and r2 >= TREND_MIN_R2 and rise6 >= TREND_MIN_RISE_FRAC * scale
    if not sa.trend_rising:
        return
    limit = sa.crit if sa.crit is not None else sa.warn
    if limit is None:
        return
    fitted_last = slope * xs[-1] + intercept
    remaining = (fitted_last - limit) if sa.low_is_bad else (limit - fitted_last)
    days_to = 0.0 if remaining <= 0 else remaining / bad
    sa.trend_days_to_crit = round(days_to, 1)
    sa.trend_score = clip01(1.0 - days_to / TREND_HORIZON_DAYS)


def _evaluate_sensor(sa: SensorAssessment, mill_running: bool) -> None:
    """State of one sensor on its latest good reading (<= as_of, <= 6 h old) - identical to kpi_health.equipment_health."""
    samples = sa.samples
    sa.latest = samples[-1] if samples else None
    sa.window = samples[-EVIDENCE_SAMPLES:]
    if sa.sensor_type in {"running_hours", "state", "rpm"} or not sa.has_limits:
        sa.reason = "no limits configured" if sa.sensor_type not in {"running_hours", "state", "rpm"} else "not a limit-checked signal"
        return
    if sa.latest is None:
        sa.reason = f"no good reading in the last {LOOKBACK_H} h"
        return
    if sa.low_is_bad and not mill_running:
        sa.reason = "inhibited: mill not running (low-is-bad process tag is only evaluated while the mill runs)"
        return
    sa.level = classify(sa.latest[1], sa.warn, sa.crit, sa.low_is_bad)
    if sa.sensor_type == "vibration":
        sa.iso = iso_zone(sa.latest[1], sa.warn, sa.crit)
    if len(samples) >= FLATLINE_SAMPLES and sa.sensor_type in {"vibration", "temperature", "current", "pressure"}:
        tail = [v for _, v in samples[-FLATLINE_SAMPLES:]]
        sa.flatline = max(tail) - min(tail) < 1e-9 and (sa.normal_max or 0) > 0 and tail[0] > 0.05 * (sa.normal_max or 1)


def _service_info(
    eq: Equipment, rh_now: float | None, rh_at_last: float | None, last_event: MaintenanceEvent | None, as_of: datetime
) -> ServiceInfo:
    if last_event is None or last_event.end_ts is None:
        return ServiceInfo("not_assessable", None, None, "", None, None, None, "No maintenance record for this equipment in the data window, so the interval is not assessable (data gap, not a finding).")
    last_ts = _utc(last_event.end_ts)
    days = (as_of - last_ts).total_seconds() / 86400.0
    rh_interval = SERVICE_INTERVAL_RUNNING_H.get(eq.equipment_type)
    if rh_interval is not None and rh_now is not None and rh_at_last is not None:
        used = max(0.0, rh_now - rh_at_last)
        return ServiceInfo(
            "running_hours", rh_interval, round(used, 1), "h", last_ts, last_event.event_type, used > rh_interval,
            f"{used:.0f} running hours since the last {last_event.event_type} event; interval {rh_interval:.0f} h ({SERVICE_INTERVAL_TAG}).",
        )
    interval = SERVICE_INTERVAL_DAYS.get(eq.equipment_type)
    if interval is None:
        return ServiceInfo("not_assessable", None, None, "", last_ts, last_event.event_type, None, "No service interval defined for this equipment type.")
    return ServiceInfo(
        "calendar_days", float(interval), round(days, 1), "d", last_ts, last_event.event_type, days > interval,
        f"{days:.0f} days since the last {last_event.event_type} event; interval {interval} d ({SERVICE_INTERVAL_TAG}).",
    )


def _criteria_for(
    sensors: list[SensorAssessment], service: ServiceInfo, alerts: list[AlertInfo], active_wo: int
) -> tuple[list[HealthCriterion], list[str]]:
    crit_rows: list[HealthCriterion] = []
    triggered: list[str] = []
    ordered = sorted(sensors, key=lambda s: (-_SEV[s.level] if s.level else 1, s.code))
    for s in ordered:
        if not s.has_limits or s.sensor_type in {"running_hours", "state", "rpm"}:
            continue
        cmp_hi = "<=" if s.low_is_bad else ">="
        w = [v for _, v in s.window]
        for tier, lim, state in (("warn", s.warn, HealthState.warning), ("crit", s.crit, HealthState.critical)):
            if lim is None:
                continue
            breached = s.level is not None and _SEV[s.level] >= _SEV[state]
            in_breach = sum(1 for v in w if classify(v, s.warn if tier == "warn" else None, s.crit if tier == "crit" else None, s.low_is_bad) != HealthState.normal)
            crit_rows.append(
                HealthCriterion(
                    sensor_code=s.code,
                    rule=f"latest reading of {s.code} {cmp_hi} {tier} limit {lim:g} {s.unit} -> {state.value.capitalize()}",
                    observed=None if s.latest is None else round(s.latest[1], 3),
                    limit=lim,
                    unit=s.unit,
                    breached=breached,
                    state_if_breached=state,
                    kind="sensor_limit",
                    observed_ts=None if s.latest is None else _utc(s.latest[0]),
                    samples_evaluated=len(w),
                    samples_in_breach=in_breach if w else None,
                    window_min=None if not w else round(min(w), 3),
                    window_max=None if not w else round(max(w), 3),
                    iso_zone=s.iso,
                    note=s.reason if s.level is None else None,
                    affects_state=True,
                )
            )
            if breached and tier == ("crit" if s.level == HealthState.critical else "warn"):
                triggered.append(f"{s.code} {cmp_hi} {tier} limit {lim:g} {s.unit} (latest {s.latest[1]:.2f})")
    crit_rows.append(
        HealthCriterion(
            sensor_code="active_work_order",
            rule="an active work order (open / assigned / in progress / on hold) exists for this equipment in this session -> Maintenance Required",
            observed=float(active_wo),
            limit=1.0,
            unit="work orders",
            breached=active_wo > 0,
            state_if_breached=HealthState.maintenance_required,
            kind="open_work_order",
            affects_state=True,
        )
    )
    if active_wo > 0:
        triggered.append(f"{active_wo} active work order(s)")
    if service.basis != "not_assessable":
        crit_rows.append(
            HealthCriterion(
                sensor_code="service_interval",
                rule=f"{'running hours' if service.basis == 'running_hours' else 'calendar days'} since last service > interval {service.interval:g} {service.unit} (informational)",
                observed=service.used,
                limit=service.interval,
                unit=service.unit,
                breached=bool(service.overdue),
                state_if_breached=HealthState.maintenance_required,
                kind="service_interval",
                observed_ts=service.last_event_ts,
                note=service.note,
                affects_state=False,
            )
        )
    for a in alerts[:5]:
        sev_state = HealthState.critical if a.severity == "critical" else HealthState.warning if a.severity in {"high", "medium"} else HealthState.normal
        crit_rows.append(
            HealthCriterion(
                sensor_code=a.code,
                rule=f"unresolved {a.severity} alert {a.code} (informational; feeds the risk index)",
                observed=None,
                limit=None,
                unit="alert",
                breached=sev_state != HealthState.normal,
                state_if_breached=sev_state,
                kind="open_alert",
                observed_ts=a.raised_at,
                note=a.title,
                affects_state=False,
            )
        )
    return crit_rows, triggered


def _risk(
    sensors: list[SensorAssessment], service: ServiceInfo, alerts: list[AlertInfo]
) -> tuple[float, list[RiskComponent]]:
    assessed = [s for s in sensors if s.level is not None]
    # condition
    cond, cond_basis = 0.0, "no assessable sensor"
    for s in assessed:
        v = s.latest[1] if s.latest else None
        if v is None:
            continue
        if s.level == HealthState.critical:
            sub = 1.0
        elif s.level == HealthState.warning:
            if s.crit is not None and s.warn is not None and s.crit != s.warn:
                frac = clip01((v - s.warn) / (s.crit - s.warn))
            else:
                frac = 0.0
            sub = 0.5 + 0.5 * frac
        else:
            nm = s.normal_min if s.low_is_bad else s.normal_max
            lim = s.warn
            if nm is not None and lim is not None and lim != nm:
                sub = 0.5 * clip01((v - nm) / (lim - nm))
            else:
                sub = 0.0
        if sub >= cond:
            cond, cond_basis = sub, f"{s.code} is {s.level.value} (latest {v:.2f} {s.unit})"
    # trend
    trend, trend_basis = 0.0, "no sensor shows a statistically clear adverse 7-day trend"
    for s in sensors:
        if s.trend_score > trend:
            trend = s.trend_score
            trend_basis = f"{s.code} rising {s.trend_slope_per_day:+.3f} {s.unit}/day (R2 {s.trend_r2}); linear days-to-limit {s.trend_days_to_crit}"
    # service
    if service.overdue is None or service.interval in (None, 0):
        svc, svc_basis = 0.0, service.note
    else:
        u = service.used / service.interval
        svc = clip01((u - 0.5) / 0.5)
        svc_basis = f"{u * 100:.0f}% of the service interval used ({service.used:g}/{service.interval:g} {service.unit})"
    # alerts
    al, al_basis = 0.0, "no unresolved alert"
    for a in alerts:
        sc = ALERT_SUBSCORE.get(a.severity, 0.0)
        if sc > al:
            al, al_basis = sc, f"unresolved {a.severity} alert {a.code}"
    # corroboration
    types = {s.sensor_type for s in assessed if s.level in (HealthState.warning, HealthState.critical)}
    corr = 0.0 if not types else 0.3 if len(types) == 1 else 0.7 if len(types) == 2 else 1.0
    corr_basis = f"{len(types)} sensor type(s) at Warning or worse: {', '.join(sorted(types)) or '-'}"
    comps = []
    total = 0.0
    for key, label, sub, basis in (
        ("condition", "Worst sensor condition", cond, cond_basis),
        ("trend", "Adverse 7-day trend (linear, not a forecast)", trend, trend_basis),
        ("service", "Service interval used", svc, svc_basis),
        ("alerts", "Unresolved alerts", al, al_basis),
        ("corroboration", "Corroborating sensor types", corr, corr_basis),
    ):
        pts = RISK_WEIGHTS[key] * sub
        total += pts
        comps.append(RiskComponent(key=key, label=label, weight=RISK_WEIGHTS[key], sub_score=round(sub, 3), points=round(pts, 2), basis=basis))
    return round(total, 1), comps


# ------------------------------------------------------------------ main entry points
def load_assessments(
    db: Session, ctx: DemoContext, equipment_ids: list[int] | None = None, active_wo: dict[int, int] | None = None
) -> dict[int, Assessment]:
    """Assess equipment at the demo clock. One bulk read per table (no per-equipment query loops).

    ``active_wo`` = active work orders per equipment id at the clock (computed lazily from services.workorders if omitted).
    """
    if active_wo is None:
        from app.services.workorders import active_work_order_counts  # noqa: PLC0415 - avoids an import cycle

        active_wo = active_work_order_counts(db, ctx)
    tz = ZoneInfo(ctx.timezone)
    stmt = select(Equipment, ProcessStage.code).join(ProcessStage, ProcessStage.id == Equipment.process_stage_id).where(Equipment.is_active.is_(True))
    if equipment_ids is not None:
        stmt = stmt.where(Equipment.id.in_(equipment_ids))
    eq_rows = db.execute(stmt.order_by(ProcessStage.sequence, Equipment.id)).all()
    if not eq_rows:
        return {}
    ids = [e.id for e, _ in eq_rows]
    sensors = db.execute(select(Sensor).where(Sensor.equipment_id.in_(ids)).order_by(Sensor.id)).scalars().all()
    by_eq: dict[int, list[SensorAssessment]] = {}
    for s in sensors:
        by_eq.setdefault(s.equipment_id, []).append(
            SensorAssessment(s.id, s.code, s.name, s.sensor_type, s.unit, s.normal_min, s.normal_max, s.warn_limit, s.crit_limit, bool(s.low_is_bad), s.sampling_seconds)
        )
    sensor_ids = [s.sensor_id for lst in by_eq.values() for s in lst]
    since = ctx.as_of - timedelta(hours=LOOKBACK_H)
    readings: dict[int, list[tuple[datetime, float]]] = {}
    for sid, ts, val in db.execute(
        select(SensorReading.sensor_id, SensorReading.ts, SensorReading.value)
        .where(SensorReading.sensor_id.in_(sensor_ids), SensorReading.ts > since, SensorReading.ts <= ctx.as_of, SensorReading.quality == "good")
        .order_by(SensorReading.sensor_id, SensorReading.ts)
    ):
        readings.setdefault(sid, []).append((_utc(ts), val))
    hour = last_complete_hour(db, ctx.as_of)
    mill_running = bool(hour and (hour["running_minutes"] or 0) > 0)  # same gate as the process twin
    trend_ids = [s.sensor_id for lst in by_eq.values() for s in lst if s.sensor_type in TREND_TYPES]
    trend_days = _load_trend(db, ctx, trend_ids, tz)
    alerts = load_open_alerts(db, ctx, ids)

    # last service event (non-breakdown) per equipment, baseline + this session, finished by as_of
    ev_rows = db.execute(
        select(MaintenanceEvent)
        .where(MaintenanceEvent.equipment_id.in_(ids), MaintenanceEvent.end_ts.is_not(None), MaintenanceEvent.end_ts <= ctx.as_of, session_filter(MaintenanceEvent.session_id, ctx))
        .order_by(MaintenanceEvent.end_ts.desc(), MaintenanceEvent.id.desc())
    ).scalars().all()
    last_service: dict[int, MaintenanceEvent] = {}
    last_any: dict[int, datetime] = {}
    for ev in ev_rows:
        last_any.setdefault(ev.equipment_id, _utc(ev.end_ts))
        if ev.event_type != "breakdown":
            last_service.setdefault(ev.equipment_id, ev)

    # anomaly model output (table is filled by the ML pipeline; empty is fine)
    anomaly: dict[int, float] = {}
    try:
        for eid, score in db.execute(
            select(AnomalyEvent.equipment_id, AnomalyEvent.score).where(
                AnomalyEvent.equipment_id.in_(ids), AnomalyEvent.start_ts <= ctx.as_of,
                or_(AnomalyEvent.end_ts.is_(None), AnomalyEvent.end_ts >= ctx.as_of - timedelta(hours=6)),
            )
        ):
            anomaly[eid] = max(anomaly.get(eid, 0.0), float(score))
    except SQLAlchemyError:
        db.rollback()

    out: dict[int, Assessment] = {}
    for eq, stage_code in eq_rows:
        sas = by_eq.get(eq.id, [])
        for sa in sas:
            sa.samples = readings.get(sa.sensor_id, [])
            _evaluate_sensor(sa, mill_running)
            if sa.sensor_type in TREND_TYPES and sa.has_limits:
                _fit_trend(sa, trend_days.get(sa.sensor_id, {}))
        rh_sensor = next((s for s in sas if s.sensor_type == "running_hours"), None)
        rh_now = rh_sensor.samples[-1][1] if rh_sensor and rh_sensor.samples else None
        le = last_service.get(eq.id)
        rh_at_last = None
        if rh_sensor is not None and le is not None and le.end_ts is not None:
            rh_at_last = db.execute(
                select(SensorReading.value).where(SensorReading.sensor_id == rh_sensor.sensor_id, SensorReading.ts <= le.end_ts)
                .order_by(SensorReading.ts.desc()).limit(1)
            ).scalar_one_or_none()
        service = _service_info(eq, rh_now, rh_at_last, le, ctx.as_of)
        open_alerts = alerts.get(eq.id, [])
        sensor_state = HealthState.normal
        for sa in sas:
            if sa.level is not None:
                sensor_state = worst(sensor_state, sa.level)
        n_wo = active_wo.get(eq.id, 0)
        state = worst(sensor_state, HealthState.maintenance_required) if n_wo > 0 else sensor_state
        alert_state = HealthState.normal
        for a in open_alerts:
            if a.severity == "critical":
                alert_state = worst(alert_state, HealthState.critical)
            elif a.severity in {"high", "medium"}:
                alert_state = worst(alert_state, HealthState.warning)
        criteria, triggered = _criteria_for(sas, service, open_alerts, n_wo)
        score, comps = _risk(sas, service, open_alerts)
        notes = []
        for sa in sas:
            if sa.flatline:
                notes.append(f"{sa.code}: last {FLATLINE_SAMPLES} samples are identical (flat-line) - verify the instrument before acting on this sensor.")
            if sa.has_limits and sa.level is None and sa.reason and "mill not running" not in sa.reason:
                notes.append(f"{sa.code}: {sa.reason}.")
        out[eq.id] = Assessment(
            equipment_id=eq.id, code=eq.code, name=eq.name, equipment_type=eq.equipment_type, stage_code=stage_code,
            criticality=eq.criticality, manufacturer=eq.manufacturer, rated_power_kw=eq.rated_power_kw, sensors=sas,
            open_alerts=open_alerts, service=service, running_hours=rh_now, last_maintenance_ts=last_any.get(eq.id),
            sensor_state=sensor_state, alert_state=alert_state, state=state, triggered_by=triggered, criteria=criteria,
            risk_score=score, risk_components=comps, anomaly_score=anomaly.get(eq.id), data_quality_notes=notes, as_of=ctx.as_of,
            active_work_orders=n_wo,
        )
    return out


def health_out(a: Assessment, ctx: DemoContext) -> EquipmentHealth:
    return EquipmentHealth(
        equipment_id=a.equipment_id,
        state=a.state,
        criteria=a.criteria,
        anomaly_score=a.anomaly_score,
        risk_score=a.risk_score,
        risk_meaning=RISK_MEANING,
        provenance=provenance("synthetic_actual", "sensor_readings + alerts + maintenance_events (rule-based health criteria)", ctx, f"{HEALTH_RULES_VERSION}; {RISK_INDEX_VERSION}"),
        equipment_code=a.code,
        as_of=ctx.as_of,
        state_rule=STATE_RULE,
        triggered_by=a.triggered_by,
        risk_components=a.risk_components,
        risk_method=RISK_METHOD,
        risk_limits=RISK_LIMITS,
        risk_band=risk_band(a.risk_score),
        data_quality_notes=a.data_quality_notes,
        health_rules_version=HEALTH_RULES_VERSION,
    )


def rank_failure_risk(db: Session, ctx: DemoContext, limit: int = 10) -> list[Assessment]:
    """Equipment ranked by the relative risk index (for /ai/failure-risk, the copilot and the executive view)."""
    items = list(load_assessments(db, ctx).values())
    items.sort(key=lambda a: (-a.risk_score, a.criticality, a.code))
    return items[:limit]
