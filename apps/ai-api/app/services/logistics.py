"""Logistics & Weighbridge Intelligence (DML-059/060/061/064). Owner: backend-a.

Truck timeline (truck_trips): arrival -> queue -> weigh_in -> grading -> unload_start -> unload_end -> weigh_out -> exit.
The stored `status` is the FINAL status (all 'exited'); the status at the demo clock is derived from the timestamps,
and timestamps after as_of are hidden (a truck still on site at as_of has no exit yet).

  wait_to_weigh_min  = weigh_in_ts - arrival_ts           (KPI-13; completed spells = weigh-in inside the window)
  turnaround_min     = exit_ts - arrival_ts               (KPI-14; trucks that exited inside the window)
  queue length at t  = trucks with arrival <= t < weigh_in (waiting for the weighbridge)
  bridge utilisation = (weigh-ins + weigh-outs in window) x weighbridge_service_min_per_event / (weighbridges x minutes)
  unloading utilisation = SUM(unload_end - unload_start) / (unloading_bays x minutes)    (measured busy time)
  ffb_received_t     = SUM(ffb_deliveries.accepted_kg)/1000 (accepted net, KPI-01)
Review flags on tickets are DATA-QUALITY prompts for a human, never accusations:
  net_above_class_max   net > truck-class max payload x 1.15 (DOMAIN_PARAMETERS truck_payload_*_t max, CHK-07)
  tare_deviation        |tare - median tare of the same masked plate (history <= as_of)| > 15%
  long_wait             wait-to-weigh > 60 min
  high_deduction        grading deduction > 10%
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found
from app.models.logistics import FfbDelivery, Plantation, Supplier, TruckTrip, WeighbridgeTicket
from app.schemas.common import Period
from app.services.demo_context import DemoContext, provenance
from app.services.kpi_common import (
    Window,
    iso_utc,
    kpi_value,
    local_midnight,
    param,
    param_meta,
    period_windows,
    rnd,
    safe_div,
    status_above,
)

SRC = "truck_trips"
TRIP_COLS = ["id", "code", "supplier_id", "plate_masked", "truck_type", "arrival_ts", "queue_start_ts", "weigh_in_ts", "grading_ts",
             "unload_start_ts", "unload_end_ts", "weigh_out_ts", "exit_ts"]  # fmt: skip
CLASS_MAX_KEY = {"pickup": "truck_payload_pickup_t", "six-wheel": "truck_payload_6wheel_t", "ten-wheel": "truck_payload_10wheel_t",
                 "trailer": "truck_payload_trailer_t"}  # fmt: skip


def load_trips(db: Session, start: datetime, end: datetime, field: str = "arrival_ts") -> pd.DataFrame:
    col = getattr(TruckTrip, field)
    rows = db.execute(select(*[getattr(TruckTrip, c) for c in TRIP_COLS]).where(col >= start, col <= end).order_by(TruckTrip.arrival_ts)).all()
    df = pd.DataFrame(rows, columns=TRIP_COLS)
    for c in TRIP_COLS:
        if c.endswith("_ts"):
            df[c] = pd.to_datetime(df[c], utc=True)
    return df


def mask_future(df: pd.DataFrame, as_of: datetime) -> pd.DataFrame:
    """Hide timestamps after the demo clock (ADR-005)."""
    df = df.copy()
    t = pd.Timestamp(as_of)
    for c in TRIP_COLS:
        if c.endswith("_ts"):
            df[c] = df[c].where(df[c] <= t)
    return df


def stage_at(row: pd.Series) -> str:
    if pd.isna(row["weigh_in_ts"]):
        return "queued"
    if pd.isna(row["grading_ts"]):
        return "weighing_in"
    if pd.isna(row["unload_start_ts"]):
        return "grading"
    if pd.isna(row["unload_end_ts"]):
        return "unloading"
    if pd.isna(row["weigh_out_ts"]):
        return "weighing_out"
    if pd.isna(row["exit_ts"]):
        return "exiting"
    return "exited"


def queue_length_series(df: pd.DataFrame, start: datetime, end: datetime, step_min: int = 15) -> list[dict[str, Any]]:
    """Trucks waiting for the weighbridge (arrival <= t < weigh_in) sampled every step_min minutes."""
    arr = df["arrival_ts"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy(dtype="datetime64[ns]") if not df.empty else np.array([], dtype="datetime64[ns]")
    win = df["weigh_in_ts"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy(dtype="datetime64[ns]") if not df.empty else arr
    win = np.where(np.isnat(win), np.datetime64("2262-01-01", "ns"), win)  # not yet weighed in = still waiting
    out = []
    t = pd.Timestamp(start).floor(f"{step_min}min")
    while t <= pd.Timestamp(end):
        tt = np.datetime64(t.tz_convert("UTC").tz_localize(None), "ns")
        out.append({"t": t.to_pydatetime(), "v": float(((arr <= tt) & (win > tt)).sum())})
        t += pd.Timedelta(minutes=step_min)
    return out


def queue_now(db: Session, ctx: DemoContext) -> dict[str, Any]:
    start = ctx.as_of - timedelta(hours=30)
    df = mask_future(load_trips(db, start, ctx.as_of), ctx.as_of)
    on_site = df[df["exit_ts"].isna()].copy()
    sup = dict(db.execute(select(Supplier.id, Supplier.code)).all())
    trucks = []
    if not on_site.empty:
        on_site["stage"] = on_site.apply(stage_at, axis=1)
        waiting = on_site[on_site["stage"] == "queued"].sort_values("arrival_ts")
        pos = {tid: i + 1 for i, tid in enumerate(waiting["id"])}
        for _, r in on_site.sort_values("arrival_ts").iterrows():
            trucks.append({
                "truck_trip_id": int(r["id"]), "code": r["code"], "supplier_code": sup.get(int(r["supplier_id"]), "?"), "plate_masked": r["plate_masked"],
                "status": r["stage"], "arrival_ts": r["arrival_ts"].to_pydatetime(),
                "waiting_min": round((pd.Timestamp(ctx.as_of) - r["arrival_ts"]).total_seconds() / 60, 1), "position": pos.get(r["id"]),
            })  # fmt: skip
    waiting_t = [t for t in trucks if t["status"] == "queued"]
    by_stage: dict[str, int] = {}
    for t in trucks:
        by_stage[t["status"]] = by_stage.get(t["status"], 0) + 1
    waits = [t["waiting_min"] for t in waiting_t]
    return {
        "as_of": ctx.as_of,
        "trucks_waiting": len(waiting_t),
        "trucks_unloading": by_stage.get("unloading", 0),
        "avg_wait_min": rnd(float(np.mean(waits)), 1) if waits else None,
        "max_wait_min": rnd(float(np.max(waits)), 1) if waits else None,
        "trucks": trucks,
        "by_stage": by_stage,
        "queue_length_series": {"key": "queue_length", "label": "Trucks waiting for the weighbridge (15-min samples, last 24 h)", "unit": "trucks",
                                "points": queue_length_series(df, ctx.as_of - timedelta(hours=24), ctx.as_of), "provenance": provenance("synthetic_actual", SRC, ctx)},
        "provenance": provenance("synthetic_actual", SRC, ctx),
        "note": "Waiting time of trucks still in the queue is right-censored (time so far). Long waits are a flow problem to analyse, never an accusation.",
    }  # fmt: skip


# ---------------------------------------------------------------------------- tickets
def _tare_medians(db: Session, as_of: datetime) -> dict[str, float]:
    rows = db.execute(
        select(TruckTrip.plate_masked, WeighbridgeTicket.tare_kg).join(WeighbridgeTicket, WeighbridgeTicket.truck_trip_id == TruckTrip.id)
        .where(WeighbridgeTicket.weigh_out_ts <= as_of, WeighbridgeTicket.tare_kg.is_not(None))
    ).all()  # fmt: skip
    df = pd.DataFrame(rows, columns=["plate", "tare"])
    return df.groupby("plate")["tare"].median().to_dict() if not df.empty else {}


def tickets(db: Session, ctx: DemoContext, period: Period, supplier_id: int | None, flagged_only: bool, limit: int, offset: int) -> dict[str, Any]:
    cur, _ = period_windows(ctx, period)
    q = (
        select(WeighbridgeTicket, TruckTrip.plate_masked, TruckTrip.truck_type, TruckTrip.arrival_ts, Supplier.code, FfbDelivery.grade,
               FfbDelivery.deduction_pct, FfbDelivery.accepted_kg, FfbDelivery.received_ts)
        .join(TruckTrip, TruckTrip.id == WeighbridgeTicket.truck_trip_id).join(Supplier, Supplier.id == TruckTrip.supplier_id)
        .outerjoin(FfbDelivery, FfbDelivery.ticket_id == WeighbridgeTicket.id)
        .where(WeighbridgeTicket.weigh_in_ts >= cur.start, WeighbridgeTicket.weigh_in_ts <= cur.end)
    )  # fmt: skip
    if supplier_id:
        q = q.where(TruckTrip.supplier_id == supplier_id)
    rows = db.execute(q.order_by(WeighbridgeTicket.weigh_in_ts.desc())).all()
    medians = _tare_medians(db, ctx.as_of)
    items = []
    for t, plate, ttype, arrival, scode, grade, ded, acc, rec_ts in rows:
        done = t.weigh_out_ts is not None and iso_utc(t.weigh_out_ts) <= ctx.as_of
        tare, net = (t.tare_kg, t.net_kg) if done else (None, None)
        graded = rec_ts is not None and iso_utc(rec_ts) <= ctx.as_of
        flags = []
        if net is not None and ttype in CLASS_MAX_KEY and net > float(param_meta(CLASS_MAX_KEY[ttype])["max"]) * 1000 * 1.15:
            flags.append("net_above_class_max")
        med = medians.get(plate)
        if tare is not None and med and abs(tare - med) / med > 0.15:
            flags.append("tare_deviation")
        wait = (iso_utc(t.weigh_in_ts) - iso_utc(arrival)).total_seconds() / 60
        if wait > 60:
            flags.append("long_wait")
        if graded and ded is not None and ded > 10:
            flags.append("high_deduction")
        if flagged_only and not flags:
            continue
        items.append({
            "id": t.id, "ticket_no": t.ticket_no, "truck_trip_id": t.truck_trip_id, "supplier_code": scode, "bridge_code": t.bridge_code,
            "weigh_in_ts": iso_utc(t.weigh_in_ts), "weigh_out_ts": iso_utc(t.weigh_out_ts) if done else None, "gross_kg": t.gross_kg,
            "tare_kg": tare, "net_kg": net, "grade": grade if graded else None, "deduction_pct": rnd(ded, 2) if graded else None,
            "accepted_kg": acc if graded else None, "flags": flags,
        })  # fmt: skip
    return {"items": items[offset : offset + limit], "total": len(items),
            "note": "Flags are data-quality prompts for review (rules in app/services/logistics.py), never accusations. "
            "Tare/net appear only after weigh-out <= as_of."}  # fmt: skip


# ---------------------------------------------------------------------------- suppliers
def _supplier_stats(db: Session, ctx: DemoContext, supplier_id: int | None = None) -> dict[int, dict[str, Any]]:
    start = max(local_midnight(ctx, ctx.business_date - timedelta(days=29)), ctx.window_start)
    q = select(FfbDelivery.supplier_id, FfbDelivery.accepted_kg, FfbDelivery.ripe_pct, FfbDelivery.grade, TruckTrip.arrival_ts, TruckTrip.weigh_in_ts).join(
        TruckTrip, TruckTrip.id == FfbDelivery.truck_trip_id
    ).where(FfbDelivery.received_ts >= start, FfbDelivery.received_ts <= ctx.as_of)
    if supplier_id:
        q = q.where(FfbDelivery.supplier_id == supplier_id)
    df = pd.DataFrame(db.execute(q).all(), columns=["sid", "acc", "ripe", "grade", "arr", "win"])
    out: dict[int, dict[str, Any]] = {}
    if df.empty:
        return out
    df["wait"] = (pd.to_datetime(df["win"], utc=True) - pd.to_datetime(df["arr"], utc=True)).dt.total_seconds() / 60
    for sid, g in df.groupby("sid"):
        mix = (g["grade"].value_counts(normalize=True) * 100).round(2).to_dict()
        out[int(sid)] = {"deliveries_30d": int(len(g)), "ffb_30d_t": rnd(float(g["acc"].sum()) / 1000, 2),
                         "avg_ripe_pct": rnd(float((g["ripe"] * g["acc"]).sum() / g["acc"].sum()), 2) if g["acc"].sum() else None,
                         "grade_mix": {str(k): float(v) for k, v in mix.items()}, "avg_wait_min": rnd(float(g["wait"].mean()), 1)}  # fmt: skip
    return out


def _supplier_out(s: Supplier, st: dict[str, Any]) -> dict[str, Any]:
    return {"id": s.id, "code": s.code, "name": s.name, "supplier_type": s.supplier_type, "province": s.province,
            "sustainability_status": s.sustainability_status, **({"deliveries_30d": 0, "ffb_30d_t": 0.0} | st)}  # fmt: skip


def suppliers(db: Session, ctx: DemoContext, supplier_type: str | None) -> dict[str, Any]:
    q = select(Supplier).order_by(Supplier.code)
    if supplier_type:
        q = q.where(Supplier.supplier_type == supplier_type)
    stats = _supplier_stats(db, ctx)
    items = [_supplier_out(s, stats.get(s.id, {})) for s in db.execute(q).scalars()]
    items.sort(key=lambda x: x.get("ffb_30d_t") or 0, reverse=True)
    return {"items": items, "total": len(items)}


def supplier_detail(db: Session, ctx: DemoContext, supplier_id: int) -> dict[str, Any]:
    s = db.get(Supplier, supplier_id)
    if s is None:
        not_found("supplier", supplier_id)
    out = _supplier_out(s, _supplier_stats(db, ctx, supplier_id).get(supplier_id, {}))
    out["plantations"] = [{"id": p.id, "code": p.code, "name": p.name, "area_ha": p.area_ha, "district": p.district, "planting_year": p.planting_year}
                          for p in db.execute(select(Plantation).where(Plantation.supplier_id == supplier_id).order_by(Plantation.code)).scalars()]  # fmt: skip
    start = max(local_midnight(ctx, ctx.business_date - timedelta(days=29)), ctx.window_start)
    rows = db.execute(select(FfbDelivery.business_date, FfbDelivery.accepted_kg, FfbDelivery.ripe_pct).where(
        FfbDelivery.supplier_id == supplier_id, FfbDelivery.received_ts >= start, FfbDelivery.received_ts <= ctx.as_of)).all()  # fmt: skip
    df = pd.DataFrame(rows, columns=["d", "acc", "ripe"])
    q_pts, v_pts = [], []
    if not df.empty:
        for d, g in df.groupby("d"):
            t = local_midnight(ctx, d)
            v_pts.append({"t": t, "v": rnd(float(g["acc"].sum()) / 1000, 3)})
            q_pts.append({"t": t, "v": rnd(float((g["ripe"] * g["acc"]).sum() / g["acc"].sum()), 2) if g["acc"].sum() else None})
    pv = provenance("synthetic_actual", "ffb_deliveries", ctx)
    out["quality_series"] = {"key": "ripe_pct", "label": "Ripe share (tonnage-weighted, daily)", "unit": "%", "points": q_pts, "provenance": pv}
    out["volume_series"] = {"key": "ffb_t", "label": "FFB accepted (daily)", "unit": "t", "points": v_pts, "provenance": pv}
    return out


# ---------------------------------------------------------------------------- KPIs
def _window_kpis(db: Session, w: Window) -> dict[str, float | None]:
    df = load_trips(db, w.start - timedelta(hours=12), w.end)
    t0, t1 = pd.Timestamp(w.start), pd.Timestamp(w.end)
    weighed = df[(df["weigh_in_ts"] >= t0) & (df["weigh_in_ts"] <= t1)]
    exited = df[(df["exit_ts"] >= t0) & (df["exit_ts"] <= t1)]
    wait = (weighed["weigh_in_ts"] - weighed["arrival_ts"]).dt.total_seconds() / 60
    tat = (exited["exit_ts"] - exited["arrival_ts"]).dt.total_seconds() / 60
    minutes = (w.end - w.start).total_seconds() / 60
    events = int(((df["weigh_in_ts"] >= t0) & (df["weigh_in_ts"] <= t1)).sum() + ((df["weigh_out_ts"] >= t0) & (df["weigh_out_ts"] <= t1)).sum())
    bridge_util = safe_div(events * param("weighbridge_service_min_per_event"), param("weighbridge_count") * minutes, 100.0)
    us = df["unload_start_ts"].clip(lower=t0)
    ue = df["unload_end_ts"].clip(upper=t1)
    busy = ((ue - us).dt.total_seconds() / 60).clip(lower=0).fillna(0).sum()
    unload_util = safe_div(float(busy), param("unloading_bays") * minutes, 100.0)
    qs = queue_length_series(mask_future(df, w.end), w.start, w.end, 10)
    arrivals = int(((df["arrival_ts"] >= t0) & (df["arrival_ts"] <= t1)).sum())
    received = db.execute(select(func.sum(FfbDelivery.accepted_kg)).where(FfbDelivery.received_ts >= w.start, FfbDelivery.received_ts <= w.end)).scalar_one_or_none()
    return {
        "avg_wait_min": float(wait.mean()) if len(wait) else None,
        "p90_wait_min": float(np.percentile(wait, 90)) if len(wait) else None,
        "avg_turnaround_min": float(tat.mean()) if len(tat) else None,
        "p90_turnaround_min": float(np.percentile(tat, 90)) if len(tat) else None,
        "max_queue_length": float(max((p["v"] for p in qs), default=0)),
        "bridge_utilisation_pct": bridge_util,
        "unloading_utilisation_pct": unload_util,
        "trucks_per_day": safe_div(arrivals, minutes / 1440.0),
        "ffb_received_t": (received or 0) / 1000.0,
    }


def kpis(db: Session, ctx: DemoContext, period: Period) -> dict[str, Any]:
    cur, prev = period_windows(ctx, period)
    v = _window_kpis(db, cur)
    vp = _window_kpis(db, prev) if prev else {}
    meta = [
        ("avg_wait_min", "Truck wait-to-weigh (mean)", "min", "down", status_above(v["avg_wait_min"], "queue_min")),
        ("p90_wait_min", "Truck wait-to-weigh (P90)", "min", "down", None),
        ("avg_turnaround_min", "Truck turnaround (mean)", "min", "down", status_above(v["avg_turnaround_min"], "turnaround_min")),
        ("p90_turnaround_min", "Truck turnaround (P90)", "min", "down", None),
        ("max_queue_length", "Max trucks waiting (10-min samples)", "trucks", "down", None),
        ("bridge_utilisation_pct", "Weighbridge utilisation", "%", "flat", None),
        ("unloading_utilisation_pct", "Unloading bay utilisation (measured busy time)", "%", "flat", None),
        ("trucks_per_day", "Truck arrivals per day", "trucks/d", "flat", None),
        ("ffb_received_t", "FFB received (accepted net)", "t", "up", None),
    ]
    return {"kpis": [kpi_value(ctx, k, lab, v.get(k), u, SRC if k != "ffb_received_t" else "ffb_deliveries.accepted_kg", vp.get(k), g, st) for k, lab, u, g, st in meta],
            "period_start": cur.start, "period_end": cur.end}  # fmt: skip


# ---------------------------------------------------------------------------- arrival pattern
def arrival_pattern(db: Session, ctx: DemoContext, business_date: date | None, lookback_days: int) -> dict[str, Any]:
    d = business_date or ctx.business_date
    if d > ctx.business_date:
        raise ApiError(422, "future_date", "business_date is after the demo clock (as_of)")
    day_start = local_midnight(ctx, d)
    if day_start + timedelta(days=1) <= ctx.window_start:
        raise ApiError(422, "out_of_window", "business_date is before the dataset window")
    hist_start = max(day_start - timedelta(days=90), ctx.window_start)
    df = load_trips(db, hist_start, min(day_start + timedelta(days=1), ctx.as_of))
    df = df[df["arrival_ts"] <= pd.Timestamp(ctx.as_of)]
    loc = df["arrival_ts"].dt.tz_convert(ctx.timezone)
    df = df.assign(d=loc.dt.date, h=loc.dt.hour, wd=loc.dt.day_of_week)
    today = df[df["d"] == d]
    by_hour = today.groupby("h").size().reindex(range(24), fill_value=0)
    lb = df[(df["d"] < d) & (df["d"] >= d - timedelta(days=lookback_days))]
    n_lb = max(lb["d"].nunique(), 1)
    typical = lb.groupby("h").size().reindex(range(24), fill_value=0) / n_lb
    hist = df[df["d"] < d]
    heat = []
    if not hist.empty:
        days_per_wd = hist.groupby("wd")["d"].nunique()
        cnt = hist.groupby(["wd", "h"]).size()
        for (wd, h), n in cnt.items():
            heat.append({"weekday": int(wd), "hour": int(h), "avg_arrivals": round(float(n) / int(days_per_wd[wd]), 2)})
    pv = provenance("synthetic_actual", SRC, ctx)
    last_hour = ctx.local_as_of.hour if d == ctx.business_date else 23
    pts = [{"t": day_start + timedelta(hours=h), "v": float(by_hour[h]) if h <= last_hour else None} for h in range(24)]
    return {
        "business_date": d,
        "by_hour": {"key": "arrivals", "label": "Arrivals per hour (actual, up to as_of)", "unit": "trucks/h", "points": pts, "provenance": pv},
        "typical_by_hour": {"key": "typical_arrivals", "label": f"Average arrivals per hour, previous {lookback_days} days", "unit": "trucks/h",
                            "points": [{"t": day_start + timedelta(hours=h), "v": round(float(typical[h]), 2)} for h in range(24)], "provenance": pv},
        "heatmap": sorted(heat, key=lambda x: (x["weekday"], x["hour"])),
        "heatmap_note": "Average arrivals per (weekday 0=Mon, mill-local hour) over up to 90 days before business_date.",
        "provenance": pv,
    }  # fmt: skip
