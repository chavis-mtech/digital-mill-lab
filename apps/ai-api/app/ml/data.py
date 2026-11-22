"""Data loaders for the ML layer (owner: ml). Read-only SQL over the seeded demo DB.

Every loader returns UTC-indexed frames. Feature builders here only use information available at or before the
row's timestamp (trailing windows are `.shift(1)` / closed on the left). `injected_events` is loaded ONLY by
`load_labels()`, which is imported by evaluation code, never by feature builders or API inference.
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from app.ml.common import read_sql

PROCESS_COLS = (
    "ts, running_minutes, downtime_min, ffb_received_t, ffb_processed_t, throughput_tph, ffb_waiting_t, avg_wait_to_process_h, "
    "sterilizer_cycles, sterilizer_cycle_min, steam_pressure_bar, boiler_steam_t, digester_temp_c, press_load_a, "
    "press_cone_pressure_bar, clarifier_temp_c, ffb_ripe_pct, oer_pct, oil_loss_total_pct"
)


def _bounds(col: str, start: str | None, end: str | None) -> tuple[str, tuple]:
    """SQL WHERE fragment for optional [start, end] bounds (timestamps as 'YYYY-MM-DD HH:MM:SS' UTC text)."""
    parts, params = [], []
    if start:
        parts.append(f"{col} >= ?")
        params.append(start)
    if end:
        parts.append(f"{col} <= ?")
        # stored text is 'YYYY-MM-DD HH:MM:SS.ffffff'; pad so an end of 'HH:MM:SS' includes that exact timestamp
        params.append(end if "." in end else end + ".999999")
    return (" WHERE " + " AND ".join(parts)) if parts else "", tuple(params)


def load_process_hourly(con: sqlite3.Connection, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    w, p = _bounds("ts", start, end)
    df = read_sql(con, f"SELECT {PROCESS_COLS} FROM process_hourly{w} ORDER BY ts", params=p)  # noqa: S608
    return df.set_index("ts")


def load_sensor_meta(con: sqlite3.Connection) -> pd.DataFrame:
    return read_sql(
        con,
        "SELECT s.id AS sensor_id, s.code, s.sensor_type, s.unit, s.equipment_id, e.code AS equipment_code, e.equipment_type, "
        "e.process_stage_id, s.normal_min, s.normal_max, s.warn_limit, s.crit_limit, s.low_is_bad, s.sampling_seconds "
        "FROM sensors s JOIN equipment e ON e.id = s.equipment_id ORDER BY s.id",
        ts_cols=(),
    )


def load_sensor_hourly(con: sqlite3.Connection, start: str | None = None, end: str | None = None,
                       sensor_ids: list[int] | None = None) -> pd.DataFrame:
    """Hourly mean/min/max/count per sensor (aggregated in SQL; ~320k rows for the full window)."""
    w, p = _bounds("ts", start, end)
    w = w + (" AND " if w else " WHERE ") + "value IS NOT NULL"
    if sensor_ids:
        w += f" AND sensor_id IN ({','.join(str(int(i)) for i in sensor_ids)})"
    df = read_sql(
        con,
        "SELECT sensor_id, strftime('%Y-%m-%d %H:00:00', ts) AS ts, AVG(value) AS mean, MIN(value) AS vmin, "
        f"MAX(value) AS vmax, COUNT(*) AS n FROM sensor_readings{w} GROUP BY sensor_id, 2",  # noqa: S608
        params=p,
    )
    return df


def sensor_wide(sensor_hourly: pd.DataFrame, meta: pd.DataFrame, stat: str = "mean") -> pd.DataFrame:
    """Hourly wide frame: columns = sensor codes."""
    codes = meta.set_index("sensor_id")["code"]
    w = sensor_hourly.pivot(index="ts", columns="sensor_id", values=stat)
    w.columns = [codes[c] for c in w.columns]
    return w.sort_index()


def load_deliveries(con: sqlite3.Connection, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    w, p = _bounds("d.received_ts", start, end)
    return read_sql(
        con,
        "SELECT d.id, d.truck_trip_id, d.received_ts AS ts, d.net_kg, d.unripe_pct, d.ripe_pct, d.overripe_pct, d.harvest_to_mill_h, "
        f"d.deduction_pct, d.grade FROM ffb_deliveries d{w} ORDER BY d.received_ts",  # noqa: S608
        params=p,
    )


def delivery_quality_features(deliv: pd.DataFrame, index: pd.DatetimeIndex, window_h: int = 12) -> pd.DataFrame:
    """Net-weighted unripe % and harvest-to-mill h of FFB received in the `window_h` hours BEFORE each hour (causal)."""
    d = deliv.copy()
    d["h"] = d["ts"].dt.floor("h")
    g = d.groupby("h").agg(net=("net_kg", "sum"))
    g["unripe_w"] = d.groupby("h").apply(lambda x: float((x["net_kg"] * x["unripe_pct"]).sum()), include_groups=False)
    g["h2m_w"] = d.groupby("h").apply(lambda x: float((x["net_kg"] * x["harvest_to_mill_h"]).sum()), include_groups=False)
    g = g.reindex(index, fill_value=0.0)
    roll = g.rolling(window_h, min_periods=1).sum().shift(1)  # hours t-window..t-1 only
    out = pd.DataFrame(index=index)
    out["recv_unripe_pct_12h"] = (roll["unripe_w"] / roll["net"]).replace([np.inf, -np.inf], np.nan)
    out["recv_harvest_to_mill_h_12h"] = (roll["h2m_w"] / roll["net"]).replace([np.inf, -np.inf], np.nan)
    return out.ffill()


def load_energy_plant_hourly(con: sqlite3.Connection) -> pd.DataFrame:
    """Plant-level energy rows (process_stage_id IS NULL = whole-facility meter)."""
    df = read_sql(
        con,
        "SELECT ts, electricity_kwh, grid_import_kwh, self_generated_kwh, steam_t, diesel_l, ffb_processed_t AS e_ffb_t, idle_kwh, cost_thb "
        "FROM energy_consumption WHERE process_stage_id IS NULL ORDER BY ts",
    )
    return df.set_index("ts")


def load_trucks(con: sqlite3.Connection) -> pd.DataFrame:
    df = read_sql(
        con,
        "SELECT t.id, t.code, t.supplier_id, t.truck_type, t.arrival_ts, t.queue_start_ts, t.weigh_in_ts, t.unload_start_ts, "
        "t.unload_end_ts, t.weigh_out_ts, t.exit_ts, w.gross_kg, w.tare_kg, w.net_kg, w.bridge_code "
        "FROM truck_trips t LEFT JOIN weighbridge_tickets w ON w.truck_trip_id = t.id ORDER BY t.arrival_ts",
        ts_cols=("arrival_ts", "queue_start_ts", "weigh_in_ts", "unload_start_ts", "unload_end_ts", "weigh_out_ts", "exit_ts"),
    )
    return df


def load_equipment(con: sqlite3.Connection) -> pd.DataFrame:
    return read_sql(
        con,
        "SELECT e.id, e.code, e.name, e.equipment_type, e.process_stage_id, ps.code AS stage_code FROM equipment e "
        "LEFT JOIN process_stages ps ON ps.id = e.process_stage_id ORDER BY e.id",
        ts_cols=(),
    )


# ---------------------------------------------------------------------------- labels (EVALUATION ONLY)
def load_labels(con: sqlite3.Connection) -> pd.DataFrame:
    """Ground-truth injected events. EVALUATION ONLY - never pass to a feature builder or the API."""
    return read_sql(
        con,
        "SELECT code, scenario_code, event_type, domain, entity_type, entity_id, equipment_id, process_stage_id, start_ts, end_ts, "
        "magnitude FROM injected_events ORDER BY start_ts",
        ts_cols=("start_ts", "end_ts"),
    )


def load_rule_alerts(con: sqlite3.Connection) -> pd.DataFrame:
    """Seeded rule/threshold alerts (data-engine), used to measure ML lead time vs the alarm system."""
    return read_sql(
        con,
        "SELECT code, severity, title, raised_at, equipment_id, scenario_code, evidence_json FROM alerts WHERE source = 'rule' ORDER BY raised_at",
        ts_cols=("raised_at",),
    )
