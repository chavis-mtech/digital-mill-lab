"""Unified alerts: effective status at the demo clock, prioritisation, evidence, session-scoped status changes.

Owner: backend-a (API: /api/v1/alerts, also feeds executive KPIs, insights, process twin).

Effective status at `as_of` (ADR-005 + ADR-014):
  1. An alert exists for the caller only if `raised_at <= as_of`.
  2. Baseline status at as_of: `resolved` if `resolved_at <= as_of`; a seeded row whose final status is
     `resolved` but whose `resolved_at` lies after as_of is still `new` at that moment; otherwise the stored status.
  3. If the caller's demo session recorded status changes (`alert_status_changes`, session-scoped), the latest one
     wins (copy-on-write: the seeded row is never updated).
  `resolved_at` is only returned when it is <= as_of (no future leak). Active = new | acknowledged | in_progress.

Priority score (0-100, a ranking aid - NOT a probability):
  score = 100 x (0.60 x S + 0.25 x I + 0.15 x R) x (1.0 if active else 0.3)
  S severity weight: critical 1.0, high 0.75, medium 0.5, low 0.25, info 0.1
  I business-impact weight: estimated lost CPO (recomputed from process_hourly) / 5 t, capped at 1; otherwise the
    equipment criticality (A 1.0, B 0.6, C 0.3); logistics 0.5; anything else 0.4
  R recency: exp(-age_h / 48), age = as_of - raised_at
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found
from app.ml.events import score01, severity_for
from app.models.ai import Alert, AlertStatusChange, AnomalyEvent
from app.models.core import Equipment, ProcessStage, Sensor
from app.models.production import ProcessHourly
from app.models.readings import SensorReading
from app.services.audit import write_audit
from app.services.demo_context import DemoContext, provenance, require_session
from app.services.kpi_common import iso_utc, price_map, price_on, rnd, to_local

SEV_W = {"critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25, "info": 0.1}
SEV_ORDER = ["critical", "high", "medium", "low", "info"]
ACTIVE = {"new", "acknowledged", "in_progress"}
TERMINAL = {"resolved", "dismissed"}
CRIT_W = {"A": 1.0, "B": 0.6, "C": 0.3}
MODULE_TEAM = {
    "maintenance": "maintenance",
    "production": "production",
    "energy": "production (utilities / energy)",
    "logistics": "logistics",
    "quality": "QC / laboratory",
}
ALLOWED_TRANSITIONS = {
    "new": {"acknowledged", "in_progress", "resolved", "dismissed"},
    "acknowledged": {"in_progress", "resolved", "dismissed"},
    "in_progress": {"resolved", "dismissed"},
    "resolved": set(),
    "dismissed": set(),
}


def _session_latest(db: Session, session_id: str | None, alert_ids: list[int] | None = None) -> dict[int, AlertStatusChange]:
    if not session_id:
        return {}
    q = select(AlertStatusChange).where(AlertStatusChange.session_id == session_id)
    if alert_ids is not None:
        q = q.where(AlertStatusChange.alert_id.in_(alert_ids))
    out: dict[int, AlertStatusChange] = {}
    for ch in db.execute(q.order_by(AlertStatusChange.changed_at, AlertStatusChange.id)).scalars():
        out[ch.alert_id] = ch
    return out


def baseline_status(a: Alert, at: datetime) -> str:
    if a.resolved_at is not None and iso_utc(a.resolved_at) <= at:
        return "resolved"
    if a.status == "resolved":
        return "new"
    return a.status


def effective_status(a: Alert, at: datetime, latest: dict[int, AlertStatusChange]) -> str:
    ch = latest.get(a.id)
    return ch.to_status if ch is not None else baseline_status(a, at)


def visible_resolved_at(a: Alert, at: datetime, latest: dict[int, AlertStatusChange]) -> datetime | None:
    ch = latest.get(a.id)
    if ch is not None and ch.to_status in TERMINAL:
        return iso_utc(ch.changed_at) if a.resolved_at is None or iso_utc(a.resolved_at) > at else iso_utc(a.resolved_at)
    if a.resolved_at is not None and iso_utc(a.resolved_at) <= at:
        return iso_utc(a.resolved_at)
    return None


def load_alerts(db: Session, at: datetime) -> list[Alert]:
    return list(db.execute(select(Alert).where(Alert.raised_at <= at).order_by(Alert.raised_at.desc(), Alert.id.desc())).scalars())


def active_alerts(db: Session, at: datetime, session_id: str | None) -> list[tuple[Alert, str]]:
    alerts = load_alerts(db, at)
    latest = _session_latest(db, session_id, [a.id for a in alerts])
    out = []
    for a in alerts:
        st = effective_status(a, at, latest)
        if st in ACTIVE:
            out.append((a, st))
    return out


def ml_views(db: Session, at: datetime, alerts: list[Alert]) -> dict[int, tuple[str, str]]:
    """(severity, title) of ML alerts as their linked anomaly looked AT THE DEMO CLOCK (QA-16).

    The training pipeline stores one alert row per anomaly episode with the severity (and, for queue windows, the
    'up to N trucks' count) of the episode PEAK, which can lie hours after `raised_at`; showing it at an earlier
    as_of leaked the future and contradicted /ai/anomalies, which truncates the trajectory at as_of. Same rule here:
    trajectory points complete at as_of (t + 1 h <= as_of, else t <= as_of), score01(peak raw, threshold).
    """
    ids = {a.anomaly_event_id for a in alerts if a.anomaly_event_id is not None and a.source != "rule"}
    if not ids:
        return {}
    evs = {e.id: e for e in db.execute(select(AnomalyEvent).where(AnomalyEvent.id.in_(ids))).scalars()}
    out: dict[int, tuple[str, str]] = {}
    hour = timedelta(hours=1)
    for a in alerts:
        e = evs.get(a.anomaly_event_id) if a.anomaly_event_id is not None and a.source != "rule" else None
        if e is None:
            continue
        ev = _json(e.evidence_json)
        thr = ev.get("threshold_raw")
        pts = [(iso_utc(datetime.fromisoformat(p["t"])), p.get("raw") or 0.0) for p in ev.get("trajectory", []) if p.get("t")]
        traj = [r for t, r in pts if t + hour <= at] or [r for t, r in pts if t <= at]
        if not thr or not traj:
            continue
        peak = max(traj)
        title = a.title
        if e.detector == "queue_window":
            title = f"Sustained queue anomaly: up to {int(peak)} trucks beyond the usual wait within 3 h"
        out[a.id] = (severity_for(float(score01(peak, float(thr)))), title)
    return out


def is_maintenance_alert(a: Alert) -> bool:
    """Control-tower KPI 'Active Maintenance Alerts': maintenance-module alerts or any alert tied to equipment."""
    return a.module == "maintenance" or a.equipment_id is not None


# ---------------------------------------------------------------------------- evidence & impact
def _json(text: str | None) -> dict[str, Any]:
    if not text:
        return {}
    try:
        v = json.loads(text)
        return v if isinstance(v, dict) else {}
    except ValueError:
        return {}


def _sensor_worst(db: Session, sensor_id: int, start: datetime, end: datetime, direction: str) -> float | None:
    agg = func.min(SensorReading.value) if direction == "below" else func.max(SensorReading.value)
    return db.execute(
        select(agg).where(SensorReading.sensor_id == sensor_id, SensorReading.ts >= start, SensorReading.ts <= end)
    ).scalar_one_or_none()


def build_evidence(db: Session, a: Alert, at: datetime, resolved_at: datetime | None, detailed: bool) -> list[dict[str, Any]]:
    """Evidence objects from the alert's rule evidence (observed vs limit). Values after as_of are never used."""
    ev = _json(a.evidence_json)
    raised = iso_utc(a.raised_at)
    end = resolved_at or at
    items: list[dict[str, Any]] = []
    rule = ev.get("rule", "rule")
    if "sensor_code" in ev:
        sensor = db.execute(select(Sensor).where(Sensor.code == ev["sensor_code"])).scalar_one_or_none()
        unit = sensor.unit if sensor else ""
        nr = ev.get("normal_range")
        normal_range = (
            {"low": nr[0], "high": nr[1], "unit": unit, "basis": "sensor normal range (sensors.normal_min / normal_max)"}
            if isinstance(nr, list) and len(nr) == 2
            else None
        )
        items.append({
            "metric": ev["sensor_code"], "label": f"{ev['sensor_code']} at alert time ({rule})", "observed": ev.get("observed"),
            "expected": ev.get("limit"), "normal_range": normal_range, "unit": unit, "window_start": raised, "window_end": raised,
            "entity": {"type": "sensor", "id": sensor.id, "code": sensor.code, "label": sensor.name} if sensor else None,
            "note": f"{ev.get('debounce_samples', 3)} consecutive samples {ev.get('direction', 'above')} the limit. "
            "Threshold rule only - an alert is a prompt for human verification, not a diagnosis.",
        })  # fmt: skip
        if detailed and sensor is not None:
            worst = _sensor_worst(db, sensor.id, raised, end, ev.get("direction", "above"))
            items.append({
                "metric": f"{ev['sensor_code']}_worst", "label": "Worst reading since the alert was raised (up to as_of / resolution)",
                "observed": rnd(worst, 3), "expected": ev.get("limit"), "normal_range": normal_range, "unit": unit,
                "window_start": raised, "window_end": end, "entity": None, "note": "Computed from sensor_readings <= as_of.",
            })  # fmt: skip
    elif "observed_oer_pct" in ev:
        items.append({
            "metric": "oer_pct_4h", "label": f"{ev.get('window_h', 4)}-hour OER vs trailing 28-day baseline",
            "observed": ev.get("observed_oer_pct"), "expected": ev.get("baseline_oer_pct"), "normal_range": None, "unit": "%",
            "window_start": raised, "window_end": raised, "entity": None,
            "note": f"Gap {ev.get('gap_pp')} pp. Possible contributing factors (FFB ripeness, sterilizer cycle, press/clarifier losses) need verification.",
        })  # fmt: skip
    elif "observed_min" in ev:
        items.append({"metric": "truck_wait_to_weigh_min", "label": "Truck wait-to-weigh at alert time", "observed": ev.get("observed_min"),
                      "expected": ev.get("limit_min"), "normal_range": None, "unit": "min", "window_start": raised, "window_end": raised,
                      "entity": None, "note": "Flow problem to analyse, never an accusation."})  # fmt: skip
    elif "observed_h" in ev:
        items.append({"metric": "ffb_wait_to_process_h", "label": "FFB wait-to-process (ramp stock / throughput)", "observed": ev.get("observed_h"),
                      "expected": ev.get("limit_h"), "normal_range": None, "unit": "h", "window_start": raised, "window_end": raised,
                      "entity": None, "note": f"Ramp stock {ev.get('ramp_stock_t')} t at alert time."})  # fmt: skip
    elif "observed" in ev:
        unit = {"daily_kwh_per_t_medium": "kWh/t", "daily_steam_per_t_medium": "t/t", "queue_len_ge_12": "trucks"}.get(rule, "")
        if rule.startswith("queue_len"):
            unit = "trucks"
        items.append({"metric": rule, "label": a.title, "observed": ev.get("observed"), "expected": ev.get("limit"), "normal_range": None,
                      "unit": unit, "window_start": raised, "window_end": raised, "entity": None, "note": "Rule threshold at alert time."})  # fmt: skip
    return items


def estimate_impact(db: Session, ctx: DemoContext, a: Alert, at: datetime, resolved_at: datetime | None) -> dict[str, Any] | None:
    """Business impact for OER-type alerts, recomputed from process_hourly up to min(resolution, as_of).

    lost_cpo_t = sum_h ffb_processed_t(h) x max(0, baseline_oer - oer_h) / 100 over the alert hours
    lost_value_thb = lost_cpo_t x 1000 x CPO price (THB/kg, prices table, alert day)  -> what_if / estimate.
    Equipment / logistics alerts get no CPO estimate here (would need a downtime what-if: /maintenance/impact).
    """
    ev = _json(a.evidence_json)
    if "baseline_oer_pct" not in ev:
        return None
    from datetime import timedelta  # noqa: PLC0415

    baseline = float(ev["baseline_oer_pct"])
    raised = iso_utc(a.raised_at)
    start = raised - timedelta(hours=float(ev.get("window_h", 4)))
    end = min(resolved_at or at, at)
    rows = db.execute(
        select(ProcessHourly.ffb_processed_t, ProcessHourly.oer_pct).where(
            ProcessHourly.ts >= start, ProcessHourly.ts <= end - timedelta(hours=1)
        )
    ).all()
    ffb = sum(r[0] or 0 for r in rows)
    lost = sum((r[0] or 0) * max(0.0, baseline - (r[1] or baseline)) / 100.0 for r in rows)
    prices = price_map(db, "cpo")
    p = price_on(prices, to_local(ctx, raised).date())
    value = lost * 1000.0 * p if p is not None else None
    return {
        "lost_cpo_t": rnd(lost, 3),
        "lost_value_thb": rnd(value, 0),
        "downtime_h": None,
        "formulas": [
            {"key": "lost_cpo_t", "label": "Lost CPO during the alert hours (estimate)",
             "expression": "lost_cpo_t = sum_h ffb_processed_t(h) * max(0, baseline_oer_pct - oer_pct(h)) / 100",
             "inputs": {"baseline_oer_pct": baseline, "ffb_processed_t": rnd(ffb, 2), "hours": len(rows)}, "result": rnd(lost, 3), "unit": "t"},
            {"key": "lost_value_thb", "label": "Value of lost CPO (illustrative price)",
             "expression": "lost_value_thb = lost_cpo_t * 1000 * cpo_price_thb_per_kg",
             "inputs": {"lost_cpo_t": rnd(lost, 3), "cpo_price_thb_per_kg": rnd(p, 3)}, "result": rnd(value, 0), "unit": "THB"},
        ],  # fmt: skip
        "assumptions_note": "Estimate on synthetic data; the baseline is the trailing 28-day OER recorded by the alert rule; "
        "CPO price is an illustrative synthetic series. Not any company's financial results.",
        "provenance": provenance("what_if", "process_hourly + prices (alert impact estimate)", ctx),
    }


def priority_score(
    a: Alert, at: datetime, status: str, criticality: str | None, lost_cpo_t: float | None, severity: str | None = None
) -> float:
    s = SEV_W.get(severity or a.severity, 0.25)
    if lost_cpo_t is not None:
        i = min(1.0, lost_cpo_t / 5.0)
    elif criticality:
        i = CRIT_W.get(criticality, 0.6)
    elif a.module == "logistics":
        i = 0.5
    else:
        i = 0.4
    age_h = max(0.0, (at - iso_utc(a.raised_at)).total_seconds() / 3600.0)
    r = math.exp(-age_h / 48.0)
    score = 100.0 * (0.60 * s + 0.25 * i + 0.15 * r)
    if status not in ACTIVE:
        score *= 0.3
    return round(score, 1)


# ---------------------------------------------------------------------------- serialisation
def _maps(db: Session) -> tuple[dict[int, Equipment], dict[int, str]]:
    eq = {e.id: e for e in db.execute(select(Equipment)).scalars()}
    stages = {s.id: s.code for s in db.execute(select(ProcessStage)).scalars()}
    return eq, stages


def to_out(
    db: Session, ctx: DemoContext, a: Alert, at: datetime, latest: dict[int, AlertStatusChange],
    eq: dict[int, Equipment], stages: dict[int, str], detailed: bool = False, ml: dict[int, tuple[str, str]] | None = None,
) -> dict[str, Any]:  # fmt: skip
    status = effective_status(a, at, latest)
    severity, title = (ml or {}).get(a.id, (a.severity, a.title))
    resolved_at = visible_resolved_at(a, at, latest)
    e = eq.get(a.equipment_id) if a.equipment_id else None
    impact = estimate_impact(db, ctx, a, at, resolved_at)
    return {
        "id": a.id,
        "code": a.code,
        "source": a.source,
        "module": a.module,
        "severity": severity,
        "status": status,
        "title": title,
        "message": a.message,
        "raised_at": iso_utc(a.raised_at),
        "resolved_at": resolved_at,
        "equipment": {"type": "equipment", "id": e.id, "code": e.code, "label": e.name} if e else None,
        "process_stage_code": stages.get(a.process_stage_id) if a.process_stage_id else None,
        "anomaly_event_id": a.anomaly_event_id,
        "recommendation_id": a.recommendation_id,
        "priority_score": priority_score(a, at, status, e.criticality if e else None, impact["lost_cpo_t"] if impact else None, severity),
        "suggested_team": MODULE_TEAM.get(a.module),
        "evidence": build_evidence(db, a, at, resolved_at, detailed),
        "impact": impact,
        "scenario_code": a.scenario_code,
    }


def list_alerts(
    db: Session, ctx: DemoContext, *, module: str | None = None, severity: str | None = None, status: str | None = None,
    equipment_id: int | None = None, stage_code: str | None = None, active_only: bool = False, limit: int = 50, offset: int = 0,
) -> dict[str, Any]:  # fmt: skip
    at = ctx.as_of
    alerts = load_alerts(db, at)
    latest = _session_latest(db, ctx.session_id, [a.id for a in alerts])
    eq, stages = _maps(db)
    stage_ids = {v: k for k, v in stages.items()}
    ml = ml_views(db, at, alerts)
    sel = []
    for a in alerts:
        st = effective_status(a, at, latest)
        if module and a.module != module:
            continue
        if severity and ml.get(a.id, (a.severity,))[0] != severity:
            continue
        if status and st != status:
            continue
        if active_only and st not in ACTIVE:
            continue
        if equipment_id and a.equipment_id != equipment_id:
            continue
        if stage_code:
            sid = stage_ids.get(stage_code)
            e = eq.get(a.equipment_id) if a.equipment_id else None
            if a.process_stage_id != sid and not (e and e.process_stage_id == sid):
                continue
        sel.append(a)
    outs = [to_out(db, ctx, a, at, latest, eq, stages, ml=ml) for a in sel]
    outs.sort(key=lambda o: (o["status"] in ACTIVE, o["priority_score"] or 0, o["raised_at"]), reverse=True)
    counts = {s: 0 for s in SEV_ORDER}
    for o in outs:
        counts[o["severity"]] = counts.get(o["severity"], 0) + 1
    return {"items": outs[offset : offset + limit], "total": len(outs), "counts_by_severity": counts, "as_of": at}


def get_alert(db: Session, ctx: DemoContext, alert_id: int) -> dict[str, Any]:
    a = db.get(Alert, alert_id)
    if a is None or iso_utc(a.raised_at) > ctx.as_of:
        not_found("alert", alert_id)  # an alert raised after the demo clock does not exist yet
    latest = _session_latest(db, ctx.session_id, [a.id])
    eq, stages = _maps(db)
    return to_out(db, ctx, a, ctx.as_of, latest, eq, stages, detailed=True, ml=ml_views(db, ctx.as_of, [a]))


def change_status(db: Session, ctx: DemoContext, alert_id: int, to_status: str, note: str | None) -> dict[str, Any]:
    """Session-scoped status change (copy-on-write, ADR-014) + audit row in the same transaction (ADR-013)."""
    session_id = require_session(ctx)
    a = db.get(Alert, alert_id)
    if a is None or iso_utc(a.raised_at) > ctx.as_of:
        not_found("alert", alert_id)
    latest = _session_latest(db, session_id, [a.id])
    current = effective_status(a, ctx.as_of, latest)
    if to_status == "new":
        raise ApiError(422, "invalid_transition", "An alert cannot be moved back to 'new'.", {"from": current, "to": to_status})
    if to_status not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ApiError(
            409, "invalid_transition", f"Cannot change alert status from '{current}' to '{to_status}'.",
            {"from": current, "to": to_status, "allowed": sorted(ALLOWED_TRANSITIONS.get(current, set()))},
        )  # fmt: skip
    ch = AlertStatusChange(alert_id=a.id, session_id=session_id, from_status=current, to_status=to_status, actor_role=ctx.role.value, note=note)
    db.add(ch)
    db.flush()
    write_audit(db, ctx, "alert.status_change", "alert", a.id, before={"status": current}, after={"status": to_status, "note": note})
    db.commit()
    return get_alert(db, ctx, alert_id)
