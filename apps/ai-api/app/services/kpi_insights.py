"""AI insight summary (DML-040) and bottleneck overview (DML-036). Owner: backend-a.

INSIGHTS - `generated_by = "deterministic_rules"`. Each item is produced by a rule over MEASURED facts at as_of;
nothing comes from scenario design-intent text, and no causal claim is made ("possible contributing factors").
"Today" = mill business day up to as_of; reference = the 28 complete days before today (ratio of sums for ratios,
mean / s.d. of daily values for spread).
  R1 OER     today OER vs trailing 28-day OER; fires when the gap exceeds 0.3 pp (KPI_DEFINITIONS 4.4 amber).
             Business impact (what_if estimate) lost CPO = FFB processed today x gap / 100, valued at the day's CPO price.
             Possible contributing factors = process signals whose tonnage-weighted value today deviates from the
             reference days' mean by more than 2 s.d. of the daily values (in the loss-increasing direction).
  R2 Alerts  every active alert of severity high/critical -> one item (evidence from the alert rule).
  R3 Energy  today kWh/t vs reference kWh/t; fires above +5% AND > 2 s.d. of daily kWh/t (with production context).
  R4 Logistics today mean wait-to-weigh vs reference; fires above 15 min (amber) or > 2x reference; adds trucks
             waiting at as_of.
  R5 Downtime today downtime hours > 0 with unplanned/planned split from maintenance_events overlapping today.
Items are sorted by severity, then rule order. Suggested decisions are advisory prompts for a human.

BOTTLENECKS - per main process stage over the period (hours complete <= as_of):
  capacity (t FFB/h) from the equipment register: reception = unloading bays x unloading rate x 60 (DOMAIN_PARAMETERS);
  sterilization = vessels x 20 t / ((mean cycle + 10 min loading) / 60) using the MEASURED mean cycle;
  threshing / digestion / pressing = SUM(rated_capacity) of the stage's t/h-rated equipment; clarification has no
  FFB-equivalent rating in the register (reported as None); CPO storage = tank fill % from the level sensors.
  actual_tph = SUM(ffb_processed_t) / running hours; utilisation = actual / capacity x 100;
  downtime_h = SUM(maintenance_events.downtime_min) of the stage's equipment within the period.
  The bottleneck is the stage with the highest utilisation; a stage >= 85% is flagged too. If the mill was starved
  (hours with no running and an empty ramp) the reason says supply, not equipment, limited output.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Equipment, ProcessStage, Sensor
from app.models.logistics import TruckTrip
from app.models.maintenance import MaintenanceEvent
from app.schemas.common import Period
from app.services.demo_context import DemoContext, provenance
from app.services.kpi_alerts import SEV_ORDER, list_alerts
from app.services.kpi_common import Window, iso_utc, local_midnight, param, period_windows, price_map, price_on, rnd, safe_div
from app.services.kpi_data import add_bucket, load_energy, load_hourly, load_weigh_ins
from app.services.kpi_health import latest_value_by_code

# signal, label, unit, direction that increases losses (+1 higher is worse, -1 lower is worse)
FACTOR_SIGNALS = [
    ("ffb_ripe_pct", "Ripe share of FFB processed", "%", -1),
    ("sterilizer_cycle_min", "Sterilizer cycle", "min", -1),
    ("steam_pressure_bar", "Sterilizer steam header pressure", "bar", -1),
    ("digester_temp_c", "Digester temperature", "degC", -1),
    ("clarifier_temp_c", "Clarifier temperature", "degC", -1),
    ("avg_wait_to_process_h", "FFB wait-to-process", "h", +1),
    ("oil_loss_press_fibre_pct", "Press-fibre oil loss", "% FFB", +1),
    ("oil_loss_sludge_pct", "Sludge oil loss", "% FFB", +1),
    ("oil_loss_efb_pct", "EFB oil loss", "% FFB", +1),
    ("oil_loss_nut_pct", "Nut oil loss", "% FFB", +1),
]


def _weighted_daily(h: pd.DataFrame, ctx: DemoContext, col: str) -> pd.Series:
    d = add_bucket(h[h["ffb_processed_t"] > 0], "ts", ctx, "day")
    d = d.assign(_w=d[col] * d["ffb_processed_t"])
    g = d.dropna(subset=[col]).groupby("bucket")[["_w", "ffb_processed_t"]].sum()
    return g["_w"] / g["ffb_processed_t"]


def _ev(metric: str, label: str, observed, expected, unit: str, w: Window, note: str | None = None, nr=None) -> dict[str, Any]:
    return {"metric": metric, "label": label, "observed": rnd(observed, 3), "expected": rnd(expected, 3), "normal_range": nr, "unit": unit,
            "window_start": w.start, "window_end": w.end, "entity": None, "note": note}  # fmt: skip


def insights(db: Session, ctx: DemoContext) -> dict[str, Any]:
    today = Window(max(local_midnight(ctx, ctx.business_date), ctx.window_start), ctx.as_of)
    ref = Window(max(today.start - timedelta(days=28), ctx.window_start), today.start)
    ht = load_hourly(db, today)
    hr = load_hourly(db, ref)
    items: list[dict[str, Any]] = []
    sev_rank = {s: i for i, s in enumerate(SEV_ORDER)}

    # R1 OER
    ffb_t = float(ht["ffb_processed_t"].sum()) if not ht.empty else 0.0
    if ffb_t > 50 and not hr.empty and hr["ffb_processed_t"].sum() > 0:
        oer_t = float(ht["cpo_t"].sum() / ffb_t * 100)
        oer_r = float(hr["cpo_t"].sum() / hr["ffb_processed_t"].sum() * 100)
        daily_oer = _weighted_daily(hr, ctx, "oer_pct")
        gap = oer_r - oer_t
        if gap > 0.3:
            lost = ffb_t * gap / 100.0
            p = price_on(price_map(db, "cpo"), ctx.business_date)
            evidence = [_ev("oer_pct", "OER today vs trailing 28-day OER", oer_t, oer_r, "%", today,
                            f"Daily OER s.d. over the reference days: {daily_oer.std():.2f} pp.",
                            {"low": rnd(oer_r - 2 * daily_oer.std(), 3), "high": rnd(oer_r + 2 * daily_oer.std(), 3), "unit": "%",
                             "basis": "trailing 28-day OER +/- 2 s.d. of daily OER"})]  # fmt: skip
            factors = []
            for col, label, unit, bad in FACTOR_SIGNALS:
                if col not in ht or ht[col].dropna().empty:
                    continue
                tw = ht[ht["ffb_processed_t"] > 0]
                obs = float((tw[col] * tw["ffb_processed_t"]).sum() / tw.loc[tw[col].notna(), "ffb_processed_t"].sum())
                ds = _weighted_daily(hr, ctx, col)
                if len(ds) < 7 or ds.std() == 0:
                    continue
                z = (obs - ds.mean()) / ds.std()
                if z * bad > 2:
                    factors.append(label)
                    evidence.append(_ev(col, label, obs, float(ds.mean()), unit, today, f"{z:+.1f} s.d. vs the reference days' daily values"))
            sev = "high" if gap > 0.8 else "medium"
            items.append({
                "headline": f"OER {oer_t:.2f}% today is {gap:.2f} pp below the trailing 28-day {oer_r:.2f}%",
                "detail": f"Estimated CPO not recovered so far today: {lost:.1f} t (= {ffb_t:.0f} t FFB x {gap:.2f} pp)"
                + (f", about {lost * 1000 * p / 1e6:.2f} M THB at the illustrative price" if p else "")
                + ". " + ("Possible contributing factors (measured deviations, not proven causes): " + ", ".join(factors) + "."
                          if factors else "No single process signal deviates by more than 2 s.d.; check lab samples and FFB mix."),
                "severity": sev, "evidence": evidence, "suggested_team": "production",
                "suggested_decision": "Decide whether production engineering should verify ripeness mix, sterilizer and loss samples this shift.",
                "related": [], "rule": "R1_oer_gap",
            })  # fmt: skip

    # R2 active high/critical alerts
    for a in list_alerts(db, ctx, active_only=True, limit=200)["items"]:
        if a["severity"] not in ("critical", "high"):
            continue
        rel = [a["equipment"]] if a["equipment"] else []
        items.append({
            "headline": f"Active {a['severity']} alert: {a['title']}",
            "detail": f"Raised {iso_utc(a['raised_at']).astimezone(ctx.local_as_of.tzinfo):%Y-%m-%d %H:%M} (mill time), status {a['status']}. "
            + ("Threshold rule only - verify on site; an alert is not a diagnosis." if a["source"] == "rule" else
               "Statistical (ML) anomaly detection - advisory, verify on site; an anomaly is not a proven cause."),
            "severity": a["severity"], "evidence": a["evidence"], "suggested_team": a["suggested_team"],
            "suggested_decision": f"Decide whether {a['suggested_team']} inspects "
            + (a["equipment"]["code"] if a["equipment"] else "the affected area") + " before continued operation (advisory).",
            "related": rel + [{"type": "alert", "id": a["id"], "code": a["code"], "label": a["title"]}], "rule": "R2_active_alert",
        })  # fmt: skip

    # R3 energy (production-adjusted statistical baseline, app/services/energy.py)
    from app.services.energy import expected_today  # noqa: PLC0415

    m = expected_today(db, ctx)
    if m and m["abnormal"]:
        et = load_energy(db, today)
        k_t = safe_div(m["actual_kwh"], m["ffb_processed_t"])
        items.append({
            "headline": f"Electricity {m['actual_kwh']:.0f} kWh today vs {m['expected_kwh']:.0f} kWh expected for the same production "
            f"(+{(m['actual_kwh'] / m['expected_kwh'] - 1) * 100:.0f}%, z = {m['z_score']:.1f})",
            "detail": f"FFB processed today {m['ffb_processed_t']:.0f} t ({k_t:.1f} kWh/t); idle consumption today {float(et['idle_kwh'].sum()):.0f} kWh. "
            "Expected kWh comes from a regression on the previous 28 days, so low throughput alone does not trigger this.",
            "severity": m["severity"], "evidence": [_ev("electricity_kwh", "Electricity today vs production-adjusted expectation", m["actual_kwh"], m["expected_kwh"], "kWh", today, m["basis"])],
            "suggested_team": "production (utilities / energy)", "suggested_decision": "Decide whether to review idle running and boiler/turbine efficiency.",
            "related": [], "rule": "R3_energy",
        })  # fmt: skip

    # R4 logistics
    qt, qr = load_weigh_ins(db, today), load_weigh_ins(db, ref)
    waiting = db.execute(
        select(TruckTrip.id).where(TruckTrip.arrival_ts <= ctx.as_of, (TruckTrip.weigh_in_ts.is_(None)) | (TruckTrip.weigh_in_ts > ctx.as_of))
    ).all()
    if not qt.empty and not qr.empty:
        w_t, w_r = float(qt["wait_min"].mean()), float(qr["wait_min"].mean())
        max_t = float(qt["wait_min"].max())
        if w_t > 15 or (w_t > 2 * w_r and w_t > 8) or max_t > 60 or len(waiting) >= 12:
            items.append({
                "headline": f"Truck wait-to-weigh {w_t:.0f} min today vs {w_r:.0f} min reference; {len(waiting)} trucks waiting now",
                "detail": f"Max wait today {float(qt['wait_min'].max()):.0f} min over {len(qt)} trucks weighed in. A flow problem to analyse, never an accusation.",
                "severity": "high" if (w_t > 60 or max_t > 60) else "medium",
                "evidence": [_ev("truck_wait_to_weigh_min", "Mean wait-to-weigh", w_t, w_r, "min", today), _ev("trucks_waiting", "Trucks waiting at as_of", len(waiting), None, "trucks", today)],
                "suggested_team": "logistics", "suggested_decision": "Decide whether to open slot scheduling (see the queue simulation) or call suppliers to stagger arrivals.",
                "related": [], "rule": "R4_logistics",
            })  # fmt: skip

    # R5 downtime
    if not ht.empty and ht["downtime_min"].sum() > 0:
        dh = float(ht["downtime_min"].sum() / 60)
        ev_rows = db.execute(
            select(MaintenanceEvent.planned, MaintenanceEvent.downtime_min, Equipment.code)
            .join(Equipment, Equipment.id == MaintenanceEvent.equipment_id)
            .where(MaintenanceEvent.start_ts >= today.start, MaintenanceEvent.start_ts <= today.end, MaintenanceEvent.session_id.is_(None))
        ).all()  # fmt: skip
        unplanned = [c for p, m, c in ev_rows if not p and m > 0]
        items.append({
            "headline": f"Plant stopped {dh:.1f} h today",
            "detail": ("Unplanned stops recorded on: " + ", ".join(sorted(set(unplanned))) + "." if unplanned else "No unplanned stop recorded; consistent with planned stops.")
            + " Starved hours (no FFB) are not counted as downtime.",
            "severity": "medium" if unplanned else "low", "evidence": [_ev("plant_downtime_h", "Plant downtime", dh, None, "h", today)],
            "suggested_team": "maintenance", "suggested_decision": "Decide whether the recovery plan needs extra processing hours.",
            "related": [], "rule": "R5_downtime",
        })  # fmt: skip

    items.sort(key=lambda i: sev_rank.get(i["severity"], 9))
    if items:
        summary = (f"As of {ctx.local_as_of:%Y-%m-%d %H:%M} mill time: {len(items)} finding(s) from computed KPIs and active alerts. "
                   f"Highest priority: {items[0]['headline']}. Suggested first team: {items[0]['suggested_team']}.")  # fmt: skip
    else:
        summary = (f"As of {ctx.local_as_of:%Y-%m-%d %H:%M} mill time: no KPI deviates beyond its threshold and no high/critical alert is active "
                   "(OER within 0.3 pp of its 28-day baseline, energy and truck waits within range).")  # fmt: skip
    for i in items:
        i.pop("rule", None)
    return {
        "generated_by": "deterministic_rules",
        "summary": summary,
        "items": items,
        "provenance": provenance("synthetic_actual", "process_hourly + energy_consumption + truck_trips + alerts (rules R1-R5)", ctx),
        "method": "Deterministic templates over measured deltas (app/services/kpi_insights.py docstring). No LLM, no design-intent text, no causal claims.",
    }


# ---------------------------------------------------------------------------- bottlenecks
def bottlenecks(db: Session, ctx: DemoContext, period: Period) -> dict[str, Any]:
    cur, _ = period_windows(ctx, period)
    h = load_hourly(db, cur)
    run_h = float(h["running_minutes"].sum() / 60) if not h.empty else 0.0
    ffb = float(h["ffb_processed_t"].sum()) if not h.empty else 0.0
    actual = safe_div(ffb, run_h)
    starved_h = float(((h["running_minutes"] == 0) & (h["downtime_min"] == 0)).sum()) if not h.empty else 0.0
    ramp_max = float(h["ffb_waiting_t"].max()) if not h.empty else None
    cyc = h.loc[h["running_minutes"] > 0, "sterilizer_cycle_min"].dropna()
    stages = {s.code: s for s in db.execute(select(ProcessStage)).scalars()}
    eqs = list(db.execute(select(Equipment).where(Equipment.is_active.is_(True))).scalars())
    by_stage: dict[int, list[Equipment]] = {}
    for e in eqs:
        by_stage.setdefault(e.process_stage_id, []).append(e)
    down = {}
    for sid, m in db.execute(
        select(Equipment.process_stage_id, MaintenanceEvent.downtime_min).join(Equipment, Equipment.id == MaintenanceEvent.equipment_id)
        .where(MaintenanceEvent.start_ts >= cur.start, MaintenanceEvent.start_ts <= cur.end, MaintenanceEvent.session_id.is_(None))
    ).all():
        down[sid] = down.get(sid, 0.0) + (m or 0.0) / 60.0

    def rated(code: str) -> float | None:
        vals = [e.rated_capacity for e in by_stage.get(stages[code].id, []) if e.rated_capacity and (e.rated_capacity_unit or "").startswith("t") and "/h" in (e.rated_capacity_unit or "")]
        return float(sum(vals)) if vals else None

    caps: dict[str, tuple[float | None, str]] = {
        "FFB_RECEPTION": (param("unloading_bays") * param("unloading_rate_t_per_min_per_bay") * 60.0,
                          "unloading bays x unloading rate (DOMAIN_PARAMETERS); actual = FFB received per hour of the window"),
        "STERILIZATION": (
            (len([e for e in by_stage.get(stages["STERILIZATION"].id, []) if e.equipment_type == "sterilizer"]) * 20.0 / ((float(cyc.mean()) + 10.0) / 60.0))
            if len(cyc) else None, f"vessels x 20 t / ((measured mean cycle {cyc.mean():.1f} min + 10 min) / 60)" if len(cyc) else "no running hours"),
        "DIGESTION": (rated("DIGESTION"), "sum of rated digester capacity"),
        "PRESSING": (rated("PRESSING"), "sum of rated screw-press capacity (derating not included)"),
        "CLARIFICATION": (None, "no FFB-equivalent capacity rating in the equipment register"),
    }  # fmt: skip
    # threshing: use threshers only (the conveyor is in series, not parallel)
    thr = [e.rated_capacity for e in by_stage.get(stages["THRESHING"].id, []) if e.equipment_type == "thresher" and e.rated_capacity]
    caps["THRESHING"] = (float(sum(thr)) if thr else None, "sum of rated thresher capacity")
    received = float(h["ffb_received_t"].sum()) if not h.empty else 0.0
    out = []
    for code in ["FFB_RECEPTION", "STERILIZATION", "THRESHING", "DIGESTION", "PRESSING", "CLARIFICATION", "CPO_STORAGE"]:
        st = stages[code]
        cap, basis = caps.get(code, (None, ""))
        act = actual
        if code == "FFB_RECEPTION":
            act = safe_div(received, cur.hours)
        util = safe_div(act, cap, 100.0)
        reason = basis
        if code == "CPO_STORAGE":
            levels = latest_value_by_code(db, ctx, [s.code for s in db.execute(select(Sensor).where(Sensor.code.like("TNK-%-LVL"))).scalars()])
            vals = [v for v in levels.values() if v is not None]
            util = float(np.mean(vals)) if vals else None
            cap, act = 3 * param("cpo_storage_tank_capacity_t"), None
            reason = "mean tank fill % from TNK-0x-LVL sensors at as_of; capacity = 3 tanks x 1,500 t"
        out.append({"stage_code": code, "label": st.name_en, "utilisation_pct": rnd(util, 1), "capacity_tph": rnd(cap, 2) if code != "CPO_STORAGE" else None,
                    "actual_tph": rnd(act, 2), "downtime_h": rnd(down.get(st.id, 0.0), 2), "is_bottleneck": False, "reason": reason})  # fmt: skip
    flow = [o for o in out if o["stage_code"] not in ("FFB_RECEPTION", "CPO_STORAGE") and o["utilisation_pct"] is not None]
    if flow:
        top = max(flow, key=lambda o: o["utilisation_pct"])
        for o in flow:
            if o is top or o["utilisation_pct"] >= 85:
                o["is_bottleneck"] = True
                o["reason"] = f"Highest utilisation of rated capacity ({o['utilisation_pct']:.0f}%). " + o["reason"] if o is top else f">= 85% of rated capacity. {o['reason']}"
    supply_note = (f"Mill starved {starved_h:.0f} h in the period (no FFB, not downtime) - supply limited output in those hours. " if starved_h else "") + (
        f"Max ramp stock {ramp_max:.0f} t." if ramp_max is not None else "")
    for o in out:
        if o["stage_code"] == "FFB_RECEPTION":
            o["reason"] = supply_note + " " + o["reason"]
    return {"stages": out, "provenance": provenance("synthetic_actual", "process_hourly + equipment + maintenance_events + sensor_readings", ctx),
            "method": "See app/services/kpi_insights.py docstring (BOTTLENECKS)."}  # fmt: skip
