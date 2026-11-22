"""Industrial Digital Twin Lite - process stages driven by the same synthetic state (DML-079/080). Owner: backend-a.

Stage status = worst computed equipment health in the stage (kpi_health: sensor limits + open work orders),
so the twin, the maintenance screens and the alerts agree. Flows and headline KPIs come from the last complete
process_hourly row before as_of; stage electricity from the stage sub-meters (energy_consumption.process_stage_id).
Sterilization has no electrical sub-meter reading (steam-driven), so its electricity is 0 by design of the data.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import not_found
from app.models.ai import AiRecommendation, RecommendationDecision
from app.models.core import Equipment, ProcessStage, Sensor
from app.models.readings import SensorReading
from app.services.demo_context import DemoContext, provenance
from app.services.kpi_alerts import list_alerts
from app.services.kpi_common import Window, iso_utc, kpi_value, rnd
from app.services.kpi_data import load_energy, load_hourly
from app.services.kpi_health import equipment_health, worst
from app.services.production import process_variables

SRC = "process_hourly"
MAIN_FLOW = [
    ("FFB_RECEPTION", "STERILIZATION", "FFB", "ffb_processed_t"),
    ("STERILIZATION", "THRESHING", "sterilized FFB", "ffb_processed_t"),
    ("THRESHING", "DIGESTION", "fruitlets", "ffb_processed_t"),
    ("DIGESTION", "PRESSING", "mash", "ffb_processed_t"),
    ("PRESSING", "CLARIFICATION", "crude oil", None),
    ("CLARIFICATION", "CPO_STORAGE", "CPO", "cpo_t"),
    ("PRESSING", "KERNEL_RECOVERY", "press cake (fibre + nuts)", None),
    ("BOILER_STEAM", "STERILIZATION", "steam", "boiler_steam_t"),
    ("BOILER_STEAM", "POWER", "steam", None),
    ("CLARIFICATION", "POME_TREATMENT", "sludge / POME", None),
]
# headline KPI per stage: (key, label, column in process_hourly, unit, good_direction)
HEADLINE = {
    "FFB_RECEPTION": ("ffb_waiting_t", "Ramp stock", "ffb_waiting_t", "t", "down"),
    "STERILIZATION": ("sterilizer_cycle_min", "Sterilizer cycle", "sterilizer_cycle_min", "min", "flat"),
    "THRESHING": ("throughput_tph", "Throughput", "throughput_tph", "t/h", "up"),
    "DIGESTION": ("digester_temp_c", "Digester temperature", "digester_temp_c", "degC", "flat"),
    "PRESSING": ("oil_loss_press_fibre_pct", "Press-fibre oil loss", "oil_loss_press_fibre_pct", "% FFB", "down"),
    "CLARIFICATION": ("clarifier_temp_c", "Clarifier temperature", "clarifier_temp_c", "degC", "flat"),
    "CPO_STORAGE": ("cpo_t", "CPO to storage (last hour)", "cpo_t", "t", "up"),
    "KERNEL_RECOVERY": ("ker_pct", "KER (last hour)", "ker_pct", "%", "up"),
    "BOILER_STEAM": ("boiler_steam_t", "Boiler steam (last hour)", "boiler_steam_t", "t/h", "flat"),
}
STAGE_VARS = {
    "FFB_RECEPTION": ["ffb_waiting_t", "avg_wait_to_process_h"],
    "STERILIZATION": ["sterilizer_cycle_min", "steam_pressure_bar"],
    "THRESHING": ["throughput_tph"],
    "DIGESTION": ["digester_temp_c"],
    "PRESSING": ["press_load_a", "press_cone_pressure_bar", "oil_loss_total_pct"],
    "CLARIFICATION": ["clarifier_temp_c", "oer_pct"],
    "CPO_STORAGE": ["oer_pct"],
    "KERNEL_RECOVERY": [],
    "BOILER_STEAM": ["boiler_steam_t", "steam_pressure_bar"],
}
STAGE_TRENDS = {
    "FFB_RECEPTION": ["ffb_waiting_t", "ffb_received_t"],
    "STERILIZATION": ["sterilizer_cycle_min", "steam_pressure_bar"],
    "THRESHING": ["throughput_tph"],
    "DIGESTION": ["digester_temp_c"],
    "PRESSING": ["oil_loss_press_fibre_pct", "press_load_a"],
    "CLARIFICATION": ["clarifier_temp_c", "oil_loss_sludge_pct"],
    "CPO_STORAGE": ["cpo_t", "oer_pct"],
    "KERNEL_RECOVERY": ["kernel_t", "ker_pct"],
    "BOILER_STEAM": ["boiler_steam_t"],
}


def _stage_rows(db: Session) -> list[ProcessStage]:
    return list(db.execute(select(ProcessStage).order_by(ProcessStage.sequence)).scalars())


def _active_alert_counts(db: Session, ctx: DemoContext) -> tuple[dict[str, int], list[dict]]:
    res = list_alerts(db, ctx, active_only=True, limit=500)
    counts: dict[str, int] = {}
    eq = {e.id: e.process_stage_id for e in db.execute(select(Equipment)).scalars()}
    stages = {s.id: s.code for s in _stage_rows(db)}
    for a in res["items"]:
        code = a["process_stage_code"]
        if code is None and a["equipment"]:
            code = stages.get(eq.get(a["equipment"]["id"]))
        if code:
            counts[code] = counts.get(code, 0) + 1
    return counts, res["items"]


def _stage_state(ctx: DemoContext, st: ProcessStage, eq_by_stage: dict, health: dict, hour: dict | None, alert_counts: dict) -> dict[str, Any]:
    eqs = eq_by_stage.get(st.id, [])
    status = worst([health[e.id]["state"] for e in eqs if e.id in health]) if eqs else "normal"
    head = None
    if st.code in HEADLINE and hour is not None:
        key, label, col, unit, good = HEADLINE[st.code]
        head = kpi_value(ctx, key, label, hour.get(col), unit, SRC, good_direction=good)
    tph = None
    if hour is not None and st.kind == "main" and st.code not in ("CPO_STORAGE",):
        tph = rnd(hour.get("throughput_tph") if (hour.get("running_minutes") or 0) > 0 else 0.0, 3)
    return {
        "code": st.code, "name_en": st.name_en, "name_th": st.name_th, "sequence": st.sequence, "kind": st.kind, "status": status,
        "throughput_tph": tph, "headline_kpi": head, "active_alerts": alert_counts.get(st.code, 0), "equipment_count": len(eqs),
    }  # fmt: skip


def list_stages(db: Session, ctx: DemoContext) -> dict[str, Any]:
    stages = _stage_rows(db)
    eqs = list(db.execute(select(Equipment).where(Equipment.is_active.is_(True))).scalars())
    by_stage: dict[int, list[Equipment]] = {}
    for e in eqs:
        by_stage.setdefault(e.process_stage_id, []).append(e)
    health = equipment_health(db, ctx)
    hour, _ = process_variables(db, ctx, keys=[])
    counts, _ = _active_alert_counts(db, ctx)
    states = [_stage_state(ctx, s, by_stage, health, hour, counts) for s in stages]
    edges = []
    for src, tgt, mat, col in MAIN_FLOW:
        flow = None
        if hour is not None and col:
            flow = rnd(hour.get(col), 3)
        edges.append({"source": src, "target": tgt, "material": mat, "flow_tph": flow})
    return {
        "ts": iso_utc(hour["ts"]) if hour else ctx.as_of,
        "stages": states,
        "edges": edges,
        "provenance": provenance("synthetic_actual", "process_hourly + sensor_readings + alerts + work_orders", ctx),
        "health_rule": "Stage status = worst equipment health; equipment health from sensor warn/crit limits (latest reading <= as_of) "
        "and open work orders (see app/services/kpi_health.py).",
    }


def stage_detail(db: Session, ctx: DemoContext, stage_code: str) -> dict[str, Any]:
    st = db.execute(select(ProcessStage).where(ProcessStage.code == stage_code)).scalar_one_or_none()
    if st is None:
        not_found("process_stage", stage_code)
    eqs = list(db.execute(select(Equipment).where(Equipment.process_stage_id == st.id).order_by(Equipment.code)).scalars())
    health = equipment_health(db, ctx)
    hour, variables = process_variables(db, ctx, keys=STAGE_VARS.get(stage_code, []))
    counts, active = _active_alert_counts(db, ctx)
    stage_state = _stage_state(ctx, st, {st.id: eqs}, health, hour, counts)
    eq_ids = {e.id for e in eqs}
    alerts_eq: dict[int, int] = {}
    for a in active:
        if a["equipment"] and a["equipment"]["id"] in eq_ids:
            alerts_eq[a["equipment"]["id"]] = alerts_eq.get(a["equipment"]["id"], 0) + 1
    equipment = [{
        "id": e.id, "code": e.code, "name": e.name, "equipment_type": e.equipment_type, "process_stage_code": stage_code,
        "criticality": e.criticality, "health_state": health[e.id]["state"], "risk_score": health[e.id]["risk_score"],
        "open_work_orders": health[e.id]["open_work_orders"], "active_alerts": alerts_eq.get(e.id, 0),
    } for e in eqs if e.id in health]  # fmt: skip

    # sensor variables (latest value vs engineering limits, same rule as kpi_health)
    sensors = list(db.execute(select(Sensor).where(Sensor.equipment_id.in_(eq_ids)).order_by(Sensor.code)).scalars()) if eq_ids else []
    for s in sensors:
        if s.sensor_type in ("state", "running_hours"):
            continue
        hrec = health.get(s.equipment_id, {})
        lv = hrec.get("readings", {}).get(s.id)
        state = hrec.get("levels", {}).get(s.id)  # backend-b's assessed level (persistence + running inhibit)
        trend = []
        if lv:
            trend = [rnd(v, 3) for (v,) in db.execute(
                select(SensorReading.value).where(SensorReading.sensor_id == s.id, SensorReading.ts > ctx.as_of - timedelta(hours=24),
                                                  SensorReading.ts <= ctx.as_of).order_by(SensorReading.ts)
            ).all()][-144:]  # fmt: skip
        variables.append({
            "key": s.code, "label": s.name,
            "value": {"value": rnd(lv[1], 3) if lv else None, "unit": s.unit, "provenance": provenance("synthetic_actual", "sensor_readings", ctx)},
            "normal_range": {"low": s.normal_min, "high": s.normal_max, "unit": s.unit,
                             "basis": f"sensor engineering range; warn {s.warn_limit}, crit {s.crit_limit}" + (" (low is bad)" if s.low_is_bad else "")},
            "status": state or "normal",
            "trend_24h": trend,
        })  # fmt: skip

    # KPIs and trends (24 h hourly)
    w = Window(max(ctx.as_of - timedelta(hours=24), ctx.window_start), ctx.as_of)
    h = load_hourly(db, w)
    kpis = []
    if not h.empty:
        ffb = float(h["ffb_processed_t"].sum())
        run_h = float(h["running_minutes"].sum() / 60.0)
        kpis.append(kpi_value(ctx, "ffb_processed_24h_t", "FFB processed (last 24 h)", ffb, "t", SRC))
        kpis.append(kpi_value(ctx, "running_h_24h", "Running hours (last 24 h)", run_h, "h", SRC))
        if stage_code in ("PRESSING", "CLARIFICATION", "CPO_STORAGE", "STERILIZATION", "DIGESTION", "THRESHING"):
            kpis.append(kpi_value(ctx, "oer_24h_pct", "OER (last 24 h)", float(h["cpo_t"].sum() / ffb * 100) if ffb else None, "%", SRC))
        if stage_code == "KERNEL_RECOVERY":
            kpis.append(kpi_value(ctx, "ker_24h_pct", "KER (last 24 h)", float(h["kernel_t"].sum() / ffb * 100) if ffb else None, "%", SRC))
    e = load_energy(db, w, stage_id=st.id)
    if not e.empty:
        kwh = float(e["electricity_kwh"].sum())
        kpis.append(kpi_value(ctx, "stage_kwh_24h", "Stage electricity (sub-meter, last 24 h)", kwh, "kWh", "energy_consumption (stage)", good_direction="down"))
    trends = []
    for col in STAGE_TRENDS.get(stage_code, []):
        if h.empty or col not in h:
            continue
        trends.append({"key": col, "label": col.replace("_", " "), "unit": "",
                       "points": [{"t": iso_utc(t.to_pydatetime()), "v": rnd(v, 4) if pd.notna(v) else None} for t, v in zip(h["ts"], h[col], strict=True)],
                       "provenance": provenance("synthetic_actual", SRC, ctx)})  # fmt: skip

    alerts = list_alerts(db, ctx, stage_code=stage_code, limit=20)["items"]
    alerts = [a for a in alerts if a["status"] in ("new", "acknowledged", "in_progress") or a["raised_at"] > ctx.as_of - timedelta(days=7)]
    return {
        "stage": stage_state,
        "equipment": equipment,
        "variables": variables,
        "kpis": kpis,
        "trends": trends,
        "alerts": alerts,
        "recommendations": _recommendations(db, ctx, st.id, eq_ids, stage_code),
    }


def _recommendations(db: Session, ctx: DemoContext, stage_id: int, eq_ids: set[int], stage_code: str) -> list[dict[str, Any]]:
    """Advisory AI recommendations (written by the ML pipeline) visible at as_of; effective status per session."""
    q = select(AiRecommendation).where(AiRecommendation.created_at <= ctx.as_of)
    rows = [r for r in db.execute(q).scalars() if r.process_stage_id == stage_id or (r.equipment_id in eq_ids)]
    if not rows:
        return []
    decisions: dict[int, RecommendationDecision] = {}
    if ctx.session_id:
        for d in db.execute(
            select(RecommendationDecision).where(RecommendationDecision.session_id == ctx.session_id).order_by(RecommendationDecision.decided_at)
        ).scalars():
            decisions[d.recommendation_id] = d
    eq = {e.id: e for e in db.execute(select(Equipment).where(Equipment.id.in_(eq_ids))).scalars()} if eq_ids else {}
    out = []
    for r in sorted(rows, key=lambda x: x.risk_score or 0, reverse=True)[:10]:
        d = decisions.get(r.id)
        e = eq.get(r.equipment_id) if r.equipment_id else None
        try:
            evidence = json.loads(r.evidence_json) if r.evidence_json else []
            evidence = evidence if isinstance(evidence, list) else []
        except ValueError:
            evidence = []
        out.append({
            "id": r.id, "code": r.code, "rec_type": r.rec_type, "title": r.title, "rationale": r.rationale, "priority": r.priority,
            "risk_score": r.risk_score, "advisory": True, "status": d.decision if d else r.status,
            "equipment": {"type": "equipment", "id": e.id, "code": e.code, "label": e.name} if e else None,
            "process_stage_code": stage_code, "anomaly_event_id": r.anomaly_event_id,
            "evidence": [x for x in evidence if isinstance(x, dict) and {"metric", "label", "unit"} <= set(x)],
            "created_at": iso_utc(r.created_at), "decided_by_role": d.approver_role if d else None,
            "decided_at": iso_utc(d.decided_at) if d else None, "work_order_id": d.work_order_id if d else None, "model_version": None,
        })  # fmt: skip
    return out
