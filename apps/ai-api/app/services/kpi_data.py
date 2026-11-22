"""Data access + bucketed aggregation for KPI / production / energy / logistics services. Owner: backend-a.

All loaders respect the demo clock: hourly rows only when complete at the window end (ts <= end - 1 h),
event rows only when their timestamp is inside [start, end] (end <= as_of). Aggregation is always sum-based so
ratio KPIs are ratio-of-sums per bucket.

Source columns (real schema names, see docs/architecture/DATABASE_SCHEMA.md):
  process_hourly: ffb_processed_t, cpo_t, kernel_t, running_minutes, downtime_min, ffb_received_t (ticket net
                  unloaded), ffb_waiting_t (ramp stock), oil_loss_*_pct (% of FFB), process variables.
  energy_consumption (process_stage_id IS NULL = plant total): electricity_kwh, grid_import_kwh,
                  self_generated_kwh, diesel_l, steam_t, water_m3, idle_kwh, cost_thb, boiler_fibre_t/shell_t.
  ffb_deliveries: accepted_kg (after grading deduction), net_kg, received_ts.
  truck_trips: arrival_ts, weigh_in_ts, exit_ts.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.energy import EnergyConsumption
from app.models.logistics import FfbDelivery, TruckTrip
from app.models.production import ProcessHourly
from app.services.demo_context import DemoContext
from app.services.kpi_common import Window, complete_hour_cutoff, param, price_map, price_on

HOURLY_COLS = [
    "ts", "running_minutes", "downtime_min", "ffb_received_t", "ffb_processed_t", "throughput_tph", "ffb_waiting_t",
    "avg_wait_to_process_h", "sterilizer_cycles", "sterilizer_cycle_min", "steam_pressure_bar", "boiler_steam_t",
    "digester_temp_c", "press_load_a", "press_cone_pressure_bar", "clarifier_temp_c", "oil_loss_press_fibre_pct",
    "oil_loss_efb_pct", "oil_loss_sludge_pct", "oil_loss_nut_pct", "oil_loss_total_pct", "cpo_t", "kernel_t",
    "oer_pct", "ker_pct", "ffb_ripe_pct",
]  # fmt: skip
ENERGY_COLS = [
    "ts", "electricity_kwh", "grid_import_kwh", "self_generated_kwh", "steam_t", "boiler_fibre_t", "boiler_shell_t",
    "diesel_l", "water_m3", "ffb_processed_t", "idle_kwh", "cost_thb",
]  # fmt: skip


def _frame(rows, cols: list[str]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=cols)
    if not df.empty:
        for c in cols:
            if c.endswith("_ts") or c == "ts":
                df[c] = pd.to_datetime(df[c], utc=True)
            else:
                df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    return df


def load_hourly(db: Session, w: Window) -> pd.DataFrame:
    cutoff = complete_hour_cutoff(w.end)
    cols = [getattr(ProcessHourly, c) for c in HOURLY_COLS]
    rows = db.execute(
        select(*cols).where(ProcessHourly.ts >= w.start, ProcessHourly.ts <= cutoff).order_by(ProcessHourly.ts)
    ).all()
    return _frame(rows, HOURLY_COLS)


def load_energy(db: Session, w: Window, stage_id: int | None = None, all_stages: bool = False) -> pd.DataFrame:
    cutoff = complete_hour_cutoff(w.end)
    cols = [getattr(EnergyConsumption, c) for c in ENERGY_COLS]
    q = select(*cols, EnergyConsumption.process_stage_id).where(EnergyConsumption.ts >= w.start, EnergyConsumption.ts <= cutoff)
    if not all_stages:
        q = q.where(EnergyConsumption.process_stage_id.is_(None) if stage_id is None else EnergyConsumption.process_stage_id == stage_id)
    rows = db.execute(q.order_by(EnergyConsumption.ts)).all()
    df = _frame([r[:-1] for r in rows], ENERGY_COLS)
    if all_stages:
        df["process_stage_id"] = [r[-1] for r in rows]
    return df


def load_deliveries(db: Session, w: Window) -> pd.DataFrame:
    cols = ["received_ts", "accepted_kg", "net_kg", "ripe_pct", "unripe_pct", "deduction_pct", "supplier_id"]
    rows = db.execute(
        select(FfbDelivery.received_ts, FfbDelivery.accepted_kg, FfbDelivery.net_kg, FfbDelivery.ripe_pct,
               FfbDelivery.unripe_pct, FfbDelivery.deduction_pct, FfbDelivery.supplier_id)
        .where(FfbDelivery.received_ts >= w.start, FfbDelivery.received_ts <= w.end)
    ).all()  # fmt: skip
    return _frame(rows, cols)


def load_weigh_ins(db: Session, w: Window) -> pd.DataFrame:
    """Trucks whose weigh-in happened in the window (completed queue spells; censoring per KPI_DEFINITIONS 4.9)."""
    cols = ["arrival_ts", "weigh_in_ts"]
    rows = db.execute(
        select(TruckTrip.arrival_ts, TruckTrip.weigh_in_ts).where(TruckTrip.weigh_in_ts >= w.start, TruckTrip.weigh_in_ts <= w.end)
    ).all()
    df = _frame(rows, cols)
    if not df.empty:
        df["wait_min"] = (df["weigh_in_ts"] - df["arrival_ts"]).dt.total_seconds() / 60.0
    return df


# ---------------------------------------------------------------------------- bucketing
def bucket_series(local: pd.Series, granularity: str | None) -> pd.Series:
    """Bucket start (mill-local, tz-aware) for each local timestamp."""
    if granularity is None:
        return pd.Series(pd.Timestamp("1970-01-01", tz=local.dt.tz), index=local.index)
    if granularity == "hour":
        return local.dt.floor("h")
    day = local.dt.normalize()
    if granularity == "day":
        return day
    if granularity == "week":
        return day - pd.to_timedelta(local.dt.day_of_week, unit="D")
    if granularity == "shift":  # A 06-18, B 18-06 (business date = shift start date)
        h = local.dt.hour
        out = day + pd.Timedelta(hours=6)
        out = out.where(h < 18, day + pd.Timedelta(hours=18))
        out = out.where(h >= 6, day - pd.Timedelta(hours=6))
        return out
    raise ValueError(granularity)


def add_bucket(df: pd.DataFrame, col: str, ctx: DemoContext, granularity: str | None) -> pd.DataFrame:
    df = df.copy()
    if df.empty:
        df["bucket"] = pd.Series(dtype=f"datetime64[ns, {ctx.timezone}]")
        return df
    df["bucket"] = bucket_series(df[col].dt.tz_convert(ctx.timezone), granularity)
    return df


SUM_COLS = [
    "ffb_processed_t", "cpo_t", "kernel_t", "running_h", "downtime_h", "ffb_cost_thb", "kernel_credit_thb",
    "ffb_received_t", "ffb_received_net_t", "electricity_kwh", "grid_import_kwh", "self_generated_kwh", "diesel_l",
    "steam_t", "water_m3", "energy_cost_thb", "idle_kwh", "energy_ffb_t", "queue_wait_sum_min", "queue_n",
    "biomass_t", "hours",
]  # fmt: skip


def aggregate(db: Session, ctx: DemoContext, w: Window, granularity: str | None = None) -> pd.DataFrame:
    """Sum-based aggregates per bucket over the window (index = local bucket start). See module docstring."""
    h = load_hourly(db, w)
    parts: list[pd.DataFrame] = []
    if not h.empty:
        h = add_bucket(h, "ts", ctx, granularity)
        local_dates = h["ts"].dt.tz_convert(ctx.timezone).dt.date
        ffb_p = price_map(db, "ffb")
        ker_p = price_map(db, "kernel")
        h["ffb_cost_thb"] = h["ffb_processed_t"] * 1000.0 * np.array([price_on(ffb_p, d, param("ffb_price_thb_per_kg")) for d in local_dates])
        h["kernel_credit_thb"] = h["kernel_t"] * 1000.0 * np.array(
            [price_on(ker_p, d, param("palm_kernel_price_thb_per_t") / 1000.0) for d in local_dates]
        )
        h["running_h"] = h["running_minutes"] / 60.0
        h["downtime_h"] = h["downtime_min"] / 60.0
        h["hours"] = 1.0
        parts.append(
            h.groupby("bucket")[["ffb_processed_t", "cpo_t", "kernel_t", "running_h", "downtime_h", "ffb_cost_thb", "kernel_credit_thb", "hours"]].sum()
        )
    e = load_energy(db, w)
    if not e.empty:
        e = add_bucket(e, "ts", ctx, granularity)
        e["energy_cost_thb"] = e["cost_thb"]
        e["energy_ffb_t"] = e["ffb_processed_t"]
        e["biomass_t"] = e["boiler_fibre_t"].fillna(0) + e["boiler_shell_t"].fillna(0)
        parts.append(
            e.groupby("bucket")[["electricity_kwh", "grid_import_kwh", "self_generated_kwh", "diesel_l", "steam_t", "water_m3",
                                 "energy_cost_thb", "idle_kwh", "energy_ffb_t", "biomass_t"]].sum(min_count=1)
        )  # fmt: skip
    d = load_deliveries(db, w)
    if not d.empty:
        d = add_bucket(d, "received_ts", ctx, granularity)
        d["ffb_received_t"] = d["accepted_kg"] / 1000.0
        d["ffb_received_net_t"] = d["net_kg"] / 1000.0
        parts.append(d.groupby("bucket")[["ffb_received_t", "ffb_received_net_t"]].sum())
    q = load_weigh_ins(db, w)
    if not q.empty:
        q = add_bucket(q, "weigh_in_ts", ctx, granularity)
        g = q.groupby("bucket")["wait_min"]
        parts.append(pd.DataFrame({"queue_wait_sum_min": g.sum(), "queue_n": g.count().astype(float)}))
    if not parts:
        return pd.DataFrame(columns=SUM_COLS)
    out = pd.concat(parts, axis=1).sort_index()
    for c in SUM_COLS:
        if c not in out.columns:
            out[c] = np.nan
    return out[SUM_COLS]


def totals(db: Session, ctx: DemoContext, w: Window) -> dict[str, float | None]:
    """Window totals as a plain dict (one bucket)."""
    agg = aggregate(db, ctx, w, None)
    if agg.empty:
        return {c: None for c in SUM_COLS}
    row = agg.iloc[0]
    return {c: (None if pd.isna(row[c]) else float(row[c])) for c in SUM_COLS}


def last_complete_hour(db: Session, as_of: datetime) -> dict | None:
    """The latest process_hourly row that is complete at as_of (dict of HOURLY_COLS)."""
    cutoff = complete_hour_cutoff(as_of)
    cols = [getattr(ProcessHourly, c) for c in HOURLY_COLS]
    row = db.execute(select(*cols).where(ProcessHourly.ts <= cutoff).order_by(ProcessHourly.ts.desc()).limit(1)).first()
    return dict(zip(HOURLY_COLS, row, strict=True)) if row else None
