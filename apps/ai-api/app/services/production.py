"""Palm Mill Production Intelligence (DML-043/044/045). Owner: backend-a.

Formulas (real columns; ratio of sums; hourly rows complete at the window end; nothing after as_of):
  OER  = 100 * SUM(process_hourly.cpo_t) / SUM(process_hourly.ffb_processed_t)       (FFB *processed* denominator)
  KER  = 100 * SUM(kernel_t) / SUM(ffb_processed_t)
  Oil loss by stream (% of FFB) = SUM(ffb_processed_t * oil_loss_<stream>_pct) / SUM(ffb_processed_t)
     streams stored: press_fibre, efb, sludge, nut; condensate/other = oil_loss_total_pct - (sum of the four)
     (derived; the data engine's total includes sterilizer condensate, DATA_GENERATION section 4).
  lost_cpo_t (stream) = SUM(ffb_processed_t * pct / 100)   = oil leaving the mill in that stream
  Expected OER band (oer-trend): for each bucket, expected = trailing 28-day OER (ratio of sums of the 28 days
     before the bucket's day); band = expected +/- 2 x standard deviation of the daily OER over the same 28 days
     (hour granularity: s.d. of hourly OER of running hours). A statistical band from history, not a model forecast.
  Process variable normal range (process-state): P5-P95 of the variable over running hours of the 28 days
     before as_of; status warning outside P5-P95, critical outside P1-P99 (statistical, labelled as such).
  Mass balance closure = (CPO + kernel + shell + fibre + EFB) / FFB processed (water / evaporation excluded;
     ~64% expected). By-products come from byproduct_outputs of batches completed <= as_of in the day.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models.logistics import FfbDelivery
from app.models.production import ByproductOutput, ProductionBatch, ProductionShift, QualityMeasurement
from app.models.traceability import BatchInput, FfbBatch
from app.schemas.common import Period
from app.services.demo_context import DemoContext, provenance
from app.services.kpi_common import (
    BASELINE_DAYS,
    THRESHOLDS,
    Window,
    iso_utc,
    kpi_value,
    local_midnight,
    param,
    period_windows,
    rnd,
    safe_div,
)
from app.services.kpi_data import add_bucket, aggregate, last_complete_hour, load_hourly, totals

SRC = "process_hourly"
LOSS_STREAMS = [
    ("press_fibre", "Press fibre", "oil_loss_press_fibre_pct", "oil_loss_fibre_pct_ffb"),
    ("efb", "Empty fruit bunch (EFB)", "oil_loss_efb_pct", "oil_loss_efb_pct_ffb"),
    ("sludge", "Clarification sludge", "oil_loss_sludge_pct", "oil_loss_sludge_pct_ffb"),
    ("nut", "Nut / other", "oil_loss_nut_pct", "oil_loss_other_pct_ffb"),
    ("condensate", "Sterilizer condensate (derived = total - streams)", None, "oil_loss_sterilizer_condensate_pct_ffb"),
]


def _day_window(ctx: DemoContext, d: date) -> Window:
    return Window(max(local_midnight(ctx, d), ctx.window_start), min(local_midnight(ctx, d + timedelta(days=1)), ctx.as_of))


# ---------------------------------------------------------------------------- summary
def summary(db: Session, ctx: DemoContext, business_date: date | None) -> dict[str, Any]:
    d = business_date or ctx.business_date
    if d > ctx.business_date:
        raise ApiError(422, "future_date", "business_date is after the demo clock (as_of)", {"as_of_date": ctx.business_date.isoformat()})
    if local_midnight(ctx, d + timedelta(days=1)) <= ctx.window_start:
        raise ApiError(422, "out_of_window", "business_date is before the dataset window")
    w = _day_window(ctx, d)
    pw = Window(w.start - timedelta(days=1), w.end - timedelta(days=1)) if w.start - timedelta(days=1) >= ctx.window_start else None
    t = totals(db, ctx, w)
    tp = totals(db, ctx, pw) if pw else {}
    hourly = load_hourly(db, w)
    ramp = float(hourly["ffb_waiting_t"].iloc[-1]) if not hourly.empty and pd.notna(hourly["ffb_waiting_t"].iloc[-1]) else None
    hourly_p = load_hourly(db, pw) if pw else pd.DataFrame()
    ramp_p = float(hourly_p["ffb_waiting_t"].iloc[-1]) if not hourly_p.empty and pd.notna(hourly_p["ffb_waiting_t"].iloc[-1]) else None

    def vals(x: dict) -> dict[str, float | None]:
        ffb = x.get("ffb_processed_t")
        return {
            "ffb_received_t": x.get("ffb_received_t"), "ffb_processed_t": ffb, "cpo_t": x.get("cpo_t"), "kernel_t": x.get("kernel_t"),
            "oer_pct": safe_div(x.get("cpo_t"), ffb, 100.0), "ker_pct": safe_div(x.get("kernel_t"), ffb, 100.0),
            "throughput_tph": safe_div(ffb, x.get("running_h")), "operating_h": x.get("running_h"), "downtime_h": x.get("downtime_h"),
        }  # fmt: skip

    v, vp = vals(t), vals(tp) if pw else {}
    meta = [
        ("ffb_received_t", "FFB received (accepted net)", "t", "up", "ffb_deliveries.accepted_kg"),
        ("ffb_processed_t", "FFB processed", "t", "up", SRC), ("cpo_t", "CPO produced", "t", "up", SRC),
        ("kernel_t", "Kernel produced", "t", "up", SRC), ("oer_pct", "OER (CPO / FFB processed)", "%", "up", SRC),
        ("ker_pct", "KER (kernel / FFB processed)", "%", "up", SRC), ("throughput_tph", "Throughput per running hour", "t/h", "up", SRC),
        ("operating_h", "Operating (running) hours", "h", "up", SRC), ("downtime_h", "Downtime", "h", "down", SRC),
    ]  # fmt: skip
    kpis = [kpi_value(ctx, k, lab, v.get(k), u, src, vp.get(k) if pw else None, g) for k, lab, u, g, src in meta]
    kpis.append(kpi_value(ctx, "ffb_waiting_t", "Ramp stock (FFB waiting) at end of window", ramp, "t", SRC, ramp_p, "down"))

    # by-products of batches completed inside the window
    bp_rows = db.execute(
        select(ByproductOutput.product, func.sum(ByproductOutput.quantity_t))
        .join(ProductionBatch, ProductionBatch.id == ByproductOutput.production_batch_id)
        .where(ProductionBatch.start_ts >= w.start, ProductionBatch.end_ts <= w.end)
        .group_by(ByproductOutput.product)
    ).all()
    bp = {p: float(q) for p, q in bp_rows}
    batch_ffb = db.execute(
        select(func.sum(ProductionBatch.ffb_input_t)).where(ProductionBatch.start_ts >= w.start, ProductionBatch.end_ts <= w.end)
    ).scalar_one_or_none()
    ffb = t.get("ffb_processed_t") or 0.0
    loss_t = float((hourly["ffb_processed_t"] * hourly["oil_loss_total_pct"].fillna(0) / 100.0).sum()) if not hourly.empty else None
    # Closure uses the batch basis for by-products, scaled to hourly FFB when the batch set is incomplete.
    scale = safe_div(ffb, batch_ffb) or 1.0
    outputs = (t.get("cpo_t") or 0) + (t.get("kernel_t") or 0) + scale * sum(bp.get(k, 0.0) for k in ("shell", "fibre", "efb"))
    closure = safe_div(outputs, ffb, 100.0)
    mb = {
        "ffb_processed_t": rnd(ffb, 3), "cpo_t": rnd(t.get("cpo_t") or 0, 3), "kernel_t": rnd(t.get("kernel_t") or 0, 3),
        "shell_t": rnd(bp.get("shell"), 3), "fibre_t": rnd(bp.get("fibre"), 3), "efb_t": rnd(bp.get("efb"), 3),
        "pome_m3": rnd(bp.get("pome"), 3), "oil_losses_t": rnd(loss_t, 3), "closure_pct": rnd(closure, 2),
        "formulas": [
            {"key": "closure_pct", "label": "Mass-balance closure (water/evaporation excluded)",
             "expression": "closure_pct = (cpo_t + kernel_t + k*(shell_t + fibre_t + efb_t)) / ffb_processed_t * 100, k = ffb_hourly / ffb_batches",
             "inputs": {"ffb_batches_t": rnd(batch_ffb, 3), "k": rnd(scale, 4)}, "result": rnd(closure, 2), "unit": "%"},
            {"key": "oil_losses_t", "label": "Oil lost in process streams", "expression": "oil_losses_t = sum_h ffb_processed_t * oil_loss_total_pct / 100",
             "inputs": {}, "result": rnd(loss_t, 3), "unit": "t"},
        ],
        "provenance": provenance("synthetic_actual", "process_hourly + byproduct_outputs (pome_m3 reported in t, density ~1 t/m3)", ctx),
    }  # fmt: skip
    oer = v["oer_pct"]
    return {
        "business_date": d,
        "kpis": kpis,
        "mass_balance": mb,
        "oer_formula": {
            "key": "oer_pct", "label": "OER (process basis)", "expression": "oer_pct = sum(cpo_t) / sum(ffb_processed_t) * 100",
            "inputs": {"cpo_t": rnd(t.get("cpo_t"), 3), "ffb_processed_t": rnd(ffb, 3)}, "result": rnd(oer, 3), "unit": "%",
        },  # fmt: skip
        "window_start": w.start,
        "window_end": w.end,
    }


# ---------------------------------------------------------------------------- OER trend
def _daily_table(db: Session, ctx: DemoContext, w: Window) -> pd.DataFrame:
    h = load_hourly(db, w)
    if h.empty:
        return pd.DataFrame(columns=["ffb", "cpo", "kernel", "ripe_w"])
    h = add_bucket(h, "ts", ctx, "day")
    h["ripe_w"] = h["ffb_ripe_pct"].fillna(0) * h["ffb_processed_t"]
    g = h.groupby("bucket").agg(ffb=("ffb_processed_t", "sum"), cpo=("cpo_t", "sum"), kernel=("kernel_t", "sum"), ripe_w=("ripe_w", "sum"))
    return g


def oer_trend(db: Session, ctx: DemoContext, period: Period, granularity: str) -> dict[str, Any]:
    cur, _ = period_windows(ctx, period)
    hist_w = Window(max(cur.start - timedelta(days=BASELINE_DAYS + 1), ctx.window_start), cur.end)
    daily = _daily_table(db, ctx, hist_w)
    daily = daily[daily["ffb"] > 0]
    daily_oer = daily["cpo"] / daily["ffb"] * 100.0

    hourly_hist = None
    if granularity == "hour":
        hh = load_hourly(db, hist_w)
        hourly_hist = hh[hh["ffb_processed_t"] > 0].copy()
        hourly_hist["local_day"] = hourly_hist["ts"].dt.tz_convert(ctx.timezone).dt.normalize()

    def expected_for(day_start: pd.Timestamp) -> tuple[float | None, float | None]:
        lo = day_start - pd.Timedelta(days=BASELINE_DAYS)
        m = (daily.index >= lo) & (daily.index < day_start)
        sub = daily[m]
        if len(sub) < 7:
            return None, None
        exp = float(sub["cpo"].sum() / sub["ffb"].sum() * 100.0)
        if hourly_hist is not None:
            hs = hourly_hist[(hourly_hist["local_day"] >= lo) & (hourly_hist["local_day"] < day_start)]
            sd = float(hs["oer_pct"].std()) if len(hs) > 10 else None
        else:
            sd = float(daily_oer[m].std())
        return exp, sd

    agg = aggregate(db, ctx, cur, granularity)
    oer_pts, ker_pts, exp_pts, band_pts, ripe_pts = [], [], [], [], []
    h_ripe = None
    hh2 = load_hourly(db, cur)
    if not hh2.empty:
        hh2 = add_bucket(hh2, "ts", ctx, granularity)
        hh2["ripe_w"] = hh2["ffb_ripe_pct"].fillna(0) * hh2["ffb_processed_t"]
        gr = hh2.groupby("bucket")[["ripe_w", "ffb_processed_t"]].sum()
        h_ripe = (gr["ripe_w"] / gr["ffb_processed_t"].replace(0, np.nan)).to_dict()
    exp_cache: dict = {}
    for b, row in agg.iterrows():
        t = b.tz_convert("UTC").to_pydatetime()
        ffb = row.get("ffb_processed_t")
        oer = safe_div(row.get("cpo_t"), ffb, 100.0) if pd.notna(ffb) else None
        ker = safe_div(row.get("kernel_t"), ffb, 100.0) if pd.notna(ffb) else None
        day = b.normalize()
        if day not in exp_cache:
            exp_cache[day] = expected_for(day)
        exp, sd = exp_cache[day]
        oer_pts.append({"t": t, "v": rnd(oer, 4)})
        ker_pts.append({"t": t, "v": rnd(ker, 4)})
        exp_pts.append({"t": t, "v": rnd(exp, 4)})
        band_pts.append({"t": t, "v": rnd(exp, 4), "lower": rnd(exp - 2 * sd, 4) if exp is not None and sd is not None else None,
                         "upper": rnd(exp + 2 * sd, 4) if exp is not None and sd is not None else None})  # fmt: skip
        r = h_ripe.get(b) if h_ripe else None
        ripe_pts.append({"t": t, "v": rnd(r, 3) if r is not None and pd.notna(r) else None})
    pv = provenance("synthetic_actual", SRC, ctx)
    return {
        "granularity": granularity,
        "oer": {"key": "oer_pct", "label": "OER (CPO / FFB processed)", "unit": "%", "points": oer_pts, "provenance": pv},
        "ker": {"key": "ker_pct", "label": "KER (kernel / FFB processed)", "unit": "%", "points": ker_pts, "provenance": pv},
        "expected_oer": {"key": "expected_oer_pct", "label": "Expected OER = trailing 28-day OER (ratio of sums)", "unit": "%",
                         "points": exp_pts, "provenance": pv},
        "expected_band": {"key": "expected_oer_band", "label": "Expected OER range (trailing 28 days)", "unit": "%", "points": band_pts,
                          "interval": "expected +/- 2 s.d. of " + ("hourly" if granularity == "hour" else "daily") + " OER over the trailing 28 days",
                          "provenance": pv},
        "ffb_ripe_pct": {"key": "ffb_ripe_pct", "label": "Ripe share of FFB processed (tonnage-weighted)", "unit": "%", "points": ripe_pts,
                         "provenance": pv},
        "note": "Statistical expected range from history; for the model-based forecast see /api/v1/ai/oer/forecast. "
        "The synthetic data books CPO in the hour the FFB is processed (no sterilizer-to-tank lag); hourly OER is noisy - decide on day / week windows.",
    }  # fmt: skip


# ---------------------------------------------------------------------------- process state
PROCESS_VARS = [
    ("throughput_tph", "Throughput", "t/h"), ("ffb_waiting_t", "Ramp stock (FFB waiting)", "t"),
    ("avg_wait_to_process_h", "FFB wait-to-process", "h"), ("sterilizer_cycle_min", "Sterilizer cycle", "min"),
    ("steam_pressure_bar", "Sterilizer steam header pressure", "bar"), ("boiler_steam_t", "Boiler steam", "t/h"),
    ("digester_temp_c", "Digester temperature", "degC"), ("press_load_a", "Press motor load", "A"),
    ("press_cone_pressure_bar", "Press cone pressure", "bar"), ("clarifier_temp_c", "Clarifier temperature", "degC"),
    ("oil_loss_total_pct", "Total oil loss", "% FFB"), ("oer_pct", "OER (hour)", "%"), ("ffb_ripe_pct", "Ripe share of FFB processed", "%"),
]  # fmt: skip


def process_variables(db: Session, ctx: DemoContext, keys: list[str] | None = None) -> tuple[dict | None, list[dict[str, Any]]]:
    hour = last_complete_hour(db, ctx.as_of)
    if hour is None:
        return None, []
    hist = load_hourly(db, Window(max(ctx.as_of - timedelta(days=BASELINE_DAYS), ctx.window_start), ctx.as_of))
    running_hist = hist[hist["running_minutes"] > 0]
    last24 = hist[hist["ts"] > pd.Timestamp(iso_utc(hour["ts"])) - pd.Timedelta(hours=24)]
    running = (hour["running_minutes"] or 0) > 0
    out = []
    for key, label, unit in PROCESS_VARS:
        if keys is not None and key not in keys:
            continue
        val = hour.get(key)
        col = running_hist[key].dropna() if key in running_hist else pd.Series(dtype=float)
        nr, status = None, "normal"
        if len(col) >= 24:
            p1, p5, p95, p99 = (float(x) for x in np.percentile(col, [1, 5, 95, 99]))
            nr = {"low": round(p5, 3), "high": round(p95, 3), "unit": unit,
                  "basis": "P5-P95 of running hours over the 28 days before as_of (statistical, synthetic data)"}  # fmt: skip
            if val is not None and running:
                if val < p1 or val > p99:
                    status = "critical"
                elif val < p5 or val > p95:
                    status = "warning"
        if not running and key not in ("ffb_waiting_t", "avg_wait_to_process_h"):
            status = "normal"
        out.append({
            "key": key, "label": label,
            "value": {"value": rnd(val, 3), "unit": unit, "provenance": provenance("synthetic_actual", SRC, ctx)},
            "normal_range": nr, "status": status,
            "trend_24h": [rnd(x, 3) if pd.notna(x) else None for x in last24[key].tolist()] if key in last24 else [],
        })  # fmt: skip
    return hour, out


def process_state(db: Session, ctx: DemoContext) -> dict[str, Any]:
    hour, variables = process_variables(db, ctx)
    if hour is None:
        raise ApiError(404, "no_data", "No complete process hour before as_of")
    return {"ts": iso_utc(hour["ts"]), "running": (hour["running_minutes"] or 0) > 0, "variables": variables,
            "note": "Last complete hour before as_of. Status vs the statistical normal range; not evaluated while the mill is stopped."}  # fmt: skip


# ---------------------------------------------------------------------------- shifts, batches
def shifts(db: Session, ctx: DemoContext, period: Period, limit: int) -> dict[str, Any]:
    cur, _ = period_windows(ctx, period)
    base = select(ProductionShift).where(ProductionShift.start_ts >= cur.start - timedelta(hours=12), ProductionShift.end_ts <= ctx.as_of,
                                         ProductionShift.end_ts > cur.start)  # fmt: skip
    rows = list(db.execute(base.order_by(ProductionShift.start_ts.desc())).scalars())
    pv = provenance("synthetic_actual", "production_shifts", ctx)
    items = [{
        "id": r.id, "business_date": r.business_date, "shift_code": r.shift_code, "start_ts": iso_utc(r.start_ts), "end_ts": iso_utc(r.end_ts),
        "ffb_processed_t": rnd(r.ffb_processed_t, 3), "cpo_t": rnd(r.cpo_t, 3), "kernel_t": rnd(r.kernel_t, 3),
        "oer_pct": rnd(r.oer_pct, 3), "ker_pct": rnd(r.ker_pct, 3), "operating_hours": rnd(r.operating_hours, 3),
        "downtime_min": rnd(r.downtime_min, 1), "provenance": pv,
    } for r in rows[:limit]]  # fmt: skip
    return {"items": items, "total": len(rows), "note": "Only shifts that ended at or before as_of (an in-progress shift is not reported)."}


def batches(db: Session, ctx: DemoContext, period: Period, limit: int, offset: int) -> dict[str, Any]:
    cur, _ = period_windows(ctx, period)
    cond = (ProductionBatch.start_ts >= cur.start, ProductionBatch.end_ts <= ctx.as_of)
    total = db.execute(select(func.count()).select_from(ProductionBatch).where(*cond)).scalar_one()
    rows = list(db.execute(select(ProductionBatch).where(*cond).order_by(ProductionBatch.start_ts.desc()).limit(limit).offset(offset)).scalars())
    ids = [r.id for r in rows]
    sup = {}
    if ids:
        sup = dict(db.execute(
            select(BatchInput.production_batch_id, func.count(func.distinct(FfbDelivery.supplier_id)))
            .join(FfbBatch, FfbBatch.id == BatchInput.ffb_batch_id).join(FfbDelivery, FfbDelivery.id == FfbBatch.delivery_id)
            .where(BatchInput.production_batch_id.in_(ids)).group_by(BatchInput.production_batch_id)
        ).all())  # fmt: skip
    items = [{
        "id": r.id, "code": r.code, "start_ts": iso_utc(r.start_ts), "end_ts": iso_utc(r.end_ts), "ffb_input_t": rnd(r.ffb_input_t, 3),
        "cpo_t": rnd(r.cpo_t, 3), "kernel_t": rnd(r.kernel_t, 3), "oer_pct": rnd(r.oer_pct, 3), "ker_pct": rnd(r.ker_pct, 3),
        "trace_method": r.trace_method, "supplier_count": sup.get(r.id),
    } for r in rows]  # fmt: skip
    return {"items": items, "total": total}


# ---------------------------------------------------------------------------- losses
def losses(db: Session, ctx: DemoContext, period: Period) -> dict[str, Any]:
    cur, _ = period_windows(ctx, period)
    h = load_hourly(db, cur)
    ffb = float(h["ffb_processed_t"].sum()) if not h.empty else 0.0
    if h.empty or ffb <= 0:
        return {"total_loss_pct": None, "components": [], "series": [], "provenance": provenance("synthetic_actual", SRC, ctx),
                "note": "No FFB processed in the window (reason: no_production)."}  # fmt: skip
    h = h.copy()
    h["oil_loss_condensate_pct"] = (h["oil_loss_total_pct"] - h[[s[2] for s in LOSS_STREAMS if s[2]]].sum(axis=1)).clip(lower=0)
    comps, series = [], []
    hb = add_bucket(h, "ts", ctx, "day" if cur.hours > 30 else "hour")
    for key, label, col, bench_key in LOSS_STREAMS:
        col = col or "oil_loss_condensate_pct"
        lost = float((h["ffb_processed_t"] * h[col].fillna(0) / 100.0).sum())
        comps.append({"key": key, "label": label, "pct_of_ffb": rnd(lost / ffb * 100.0, 4), "benchmark_pct": param(bench_key),
                      "lost_cpo_t": rnd(lost, 3)})  # fmt: skip
        hb["_w"] = hb["ffb_processed_t"] * hb[col].fillna(0)
        g = hb.groupby("bucket")[["_w", "ffb_processed_t"]].sum()
        series.append({"key": key, "label": label, "unit": "% FFB",
                       "points": [{"t": b.tz_convert("UTC").to_pydatetime(), "v": rnd(safe_div(r["_w"], r["ffb_processed_t"]), 4)} for b, r in g.iterrows()],
                       "provenance": provenance("synthetic_actual", SRC, ctx)})  # fmt: skip
    total = float((h["ffb_processed_t"] * h["oil_loss_total_pct"].fillna(0)).sum() / ffb)
    return {
        "total_loss_pct": rnd(total, 4),
        "components": comps,
        "series": series,
        "provenance": provenance("synthetic_actual", SRC, ctx),
        "benchmark_total_pct": param("oil_loss_total_pct_ffb"),
        "note": "pct_of_ffb = sum(ffb x loss%) / sum(ffb); benchmarks are DOMAIN_PARAMETERS nominal values (Industry Practice / "
        "Engineering Assumption). Components sum to the total (condensate is derived as the remainder).",
    }


# ---------------------------------------------------------------------------- quality
QUALITY_LIMITS = {
    ("cpo_tank", "ffa"): (None, THRESHOLDS["cpo_ffa_pct"]["red"], "off-spec above 5.0% FFA (KPI_DEFINITIONS section 5; amber 4.0%)"),
    ("cpo_tank", "moisture"): (None, 0.25, "M&I limit 0.25% (KPI_DEFINITIONS KPI-16; moisture shown alone)"),
    ("cpo_tank", "dirt"): (None, 0.25, "M&I limit 0.25% (KPI_DEFINITIONS KPI-16; dirt shown alone)"),
    ("kernel", "moisture"): (None, 7.0, "kernel dry-to-spec below ~7% moisture (KPI_DEFINITIONS 4.5)"),
}


def quality(db: Session, ctx: DemoContext, period: Period) -> dict[str, Any]:
    cur, _ = period_windows(ctx, period)
    rows = db.execute(
        select(QualityMeasurement.sample_point, QualityMeasurement.parameter, QualityMeasurement.unit, QualityMeasurement.sample_ts,
               QualityMeasurement.value)
        .where(QualityMeasurement.sample_ts >= cur.start, QualityMeasurement.sample_ts <= cur.end)
        .order_by(QualityMeasurement.sample_ts)
    ).all()  # fmt: skip
    groups: dict[tuple[str, str, str], list[tuple]] = {}
    for sp, par, unit, ts, v in rows:
        groups.setdefault((sp, par, unit), []).append((iso_utc(ts), float(v)))
    bench = {("press_fibre", "oil_loss"): "oil_loss_fibre_pct_ffb", ("efb", "oil_loss"): "oil_loss_efb_pct_ffb",
             ("sludge", "oil_loss"): "oil_loss_sludge_pct_ffb", ("nut", "oil_loss"): "oil_loss_other_pct_ffb",
             ("condensate", "oil_loss"): "oil_loss_sterilizer_condensate_pct_ffb"}  # fmt: skip
    params = []
    pv = provenance("synthetic_actual", "quality_measurements", ctx)
    for (sp, par, unit), pts in sorted(groups.items()):
        lim = None
        if (sp, par) in QUALITY_LIMITS:
            lo, hi, basis = QUALITY_LIMITS[(sp, par)]
            lim = {"low": lo, "high": hi, "unit": unit, "basis": basis}
        elif (sp, par) in bench:
            m = param(bench[(sp, par)])
            lim = {"low": None, "high": m, "unit": unit, "basis": f"industry-practice nominal {m} (DOMAIN_PARAMETERS {bench[(sp, par)]}), reference not a limit"}
        params.append({
            "sample_point": sp, "parameter": par,
            "latest": {"value": rnd(pts[-1][1], 4), "unit": unit, "provenance": pv},
            "limit": lim,
            "series": {"key": f"{sp}.{par}", "label": f"{sp} {par}", "unit": unit, "points": [{"t": t, "v": rnd(v, 4)} for t, v in pts[-500:]],
                       "provenance": pv},
        })  # fmt: skip
    return {"parameters": params}
