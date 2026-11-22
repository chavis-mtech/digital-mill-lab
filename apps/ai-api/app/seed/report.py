"""Cross-module scenario chain report: python -m app.seed.report [--db-url URL] [--json] [--out PATH]

For each scenario: focus day vs its baseline day (and NORMAL_DAY) - sensor evidence -> production KPI -> alerts ->
traced batches / CPO lots. Reads only the database (what every other module sees), so the numbers are the ones the
API, ML and copilot will compute from.
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np
import pandas as pd

from app.seed.validate import LOCAL, _df, _oer


def _day(df: pd.DataFrame, col: str, ts: pd.Timestamp) -> pd.DataFrame:
    return df[(df[col] + LOCAL).dt.date == (ts + LOCAL).date()]


def chain_report(engine) -> dict:
    scen = _df(engine, "SELECT code, start_ts, end_ts, focus_ts, baseline_ts FROM scenario_runs ORDER BY focus_ts", ("start_ts", "end_ts", "focus_ts", "baseline_ts"))
    ph = _df(engine, "SELECT * FROM process_hourly", ("ts",))
    en = _df(engine, "SELECT * FROM energy_consumption WHERE process_stage_id IS NULL", ("ts",))
    al = _df(engine, "SELECT a.code, a.severity, a.module, a.title, a.raised_at, a.scenario_code, e.code AS equip_code FROM alerts a "
                     "LEFT JOIN equipment e ON e.id = a.equipment_id", ("raised_at",))
    trips = _df(engine, "SELECT arrival_ts, weigh_in_ts, exit_ts FROM truck_trips", ("arrival_ts", "weigh_in_ts", "exit_ts"))
    lots = _df(engine, "SELECT id, code, fill_start_ts, quantity_t, ffa_pct, dobi FROM cpo_output_lots", ("fill_start_ts",))
    pb = _df(engine, "SELECT id, code, start_ts, ffb_input_t, oer_pct FROM production_batches", ("start_ts",))
    dl = _df(engine, "SELECT received_ts, net_kg, unripe_pct, harvest_to_mill_h FROM ffb_deliveries", ("received_ts",))

    def sensor_day(code: str, ts: pd.Timestamp, agg: str = "max", running_only: bool = False):
        d0 = (ts + LOCAL).normalize() - LOCAL
        df = _df(engine, f"SELECT r.ts, r.value FROM sensor_readings r JOIN sensors s ON s.id = r.sensor_id WHERE s.code = '{code}' "  # noqa: S608 - internal codes
                         f"AND r.ts >= '{d0:%Y-%m-%d %H:%M:%S}' AND r.ts < '{d0 + pd.Timedelta(days=1):%Y-%m-%d %H:%M:%S}'", ("ts",))
        v = df.value[df.value > 1] if running_only else df.value
        return round(float(getattr(v, agg)()), 3) if len(v) else None

    def kpis(ts: pd.Timestamp) -> dict:
        p = _day(ph, "ts", ts)
        e = _day(en, "ts", ts)
        t = _day(trips, "arrival_ts", ts)
        d = _day(dl, "received_ts", ts)
        wait = (t.weigh_in_ts - t.arrival_ts).dt.total_seconds() / 60
        turn = (t.exit_ts - t.arrival_ts).dt.total_seconds() / 60
        lot = _day(lots, "fill_start_ts", ts)
        f = p.ffb_processed_t.sum()
        return {
            "date": str((ts + LOCAL).date()), "ffb_received_t": round(float(p.ffb_received_t.sum()), 1), "ffb_processed_t": round(float(f), 1),
            "oer_pct": round(_oer(p), 2), "throughput_tph": round(float(f / (p.running_minutes.sum() / 60)), 2) if f else None,
            "running_h": round(float(p.running_minutes.sum() / 60), 1), "downtime_h": round(float(p.downtime_min.sum() / 60), 1),
            "oil_loss_total_pct": round(float(np.average(p.oil_loss_total_pct.dropna(), weights=p.ffb_processed_t[p.oil_loss_total_pct.notna()])), 3),
            "press_fibre_loss_pct": round(float(np.average(p.oil_loss_press_fibre_pct.dropna(), weights=p.ffb_processed_t[p.oil_loss_press_fibre_pct.notna()])), 3),
            "sludge_loss_pct": round(float(np.average(p.oil_loss_sludge_pct.dropna(), weights=p.ffb_processed_t[p.oil_loss_sludge_pct.notna()])), 3),
            "efb_loss_pct": round(float(np.average(p.oil_loss_efb_pct.dropna(), weights=p.ffb_processed_t[p.oil_loss_efb_pct.notna()])), 3),
            "sterilizer_cycle_min": round(float(p.sterilizer_cycle_min.mean()), 1), "header_pressure_min_bar": round(float(p.steam_pressure_bar.min()), 2),
            "clarifier_temp_min_c": round(float(p[p.ffb_processed_t > 0].clarifier_temp_c.min()), 1),
            "digester_temp_min_c": round(float(p[p.ffb_processed_t > 0].digester_temp_c.min()), 1),
            "ffb_wait_to_process_h": round(float(np.average(p.avg_wait_to_process_h.fillna(0), weights=p.ffb_processed_t)), 2) if f else None,
            "ramp_stock_max_t": round(float(p.ffb_waiting_t.max()), 0),
            "kwh_per_t": round(float(e.electricity_kwh.sum() / e.ffb_processed_t.sum()), 2), "steam_t_per_t": round(float(e.steam_t.sum() / e.ffb_processed_t.sum()), 3),
            "idle_kwh": round(float(e.idle_kwh.sum()), 0), "grid_import_kwh": round(float(e.grid_import_kwh.sum()), 0), "diesel_l": round(float(e.diesel_l.sum()), 0),
            "energy_cost_thb": round(float(e.cost_thb.sum()), 0),
            "trucks": int(len(t)), "wait_to_weigh_mean_min": round(float(wait.mean()), 1), "wait_to_weigh_max_min": round(float(wait.max()), 1),
            "turnaround_mean_min": round(float(turn.mean()), 1),
            "delivered_unripe_pct": round(float(np.average(d.unripe_pct, weights=d.net_kg)), 2), "harvest_to_mill_h": round(float(np.average(d.harvest_to_mill_h, weights=d.net_kg)), 1),
            "cpo_lot": lot.code.iloc[0] if len(lot) else None, "lot_ffa_pct": float(lot.ffa_pct.iloc[0]) if len(lot) else None,
            "lot_dobi": float(lot.dobi.iloc[0]) if len(lot) else None,
        }

    out = {}
    normal = scen[scen.code == "NORMAL_DAY"]
    for s in scen.itertuples():
        item = {"window_local": [str(s.start_ts + LOCAL), str(s.end_ts + LOCAL)], "focus_local": str(s.focus_ts + LOCAL),
                "focus": kpis(s.focus_ts), "baseline": kpis(s.baseline_ts)}
        if not normal.empty and s.code not in ("NORMAL_DAY",):
            item["normal_day"] = kpis(normal.focus_ts.iloc[0])
        a = al[al.scenario_code == s.code].sort_values("raised_at")
        item["alerts"] = [{"code": x.code, "severity": x.severity, "module": x.module, "equipment": x.equip_code, "title": x.title,
                           "raised_local": str(x.raised_at + LOCAL)} for x in a.itertuples()]
        fb = _day(pb, "start_ts", s.focus_ts)
        item["focus_batches"] = {"count": int(len(fb)), "lowest_oer": fb.nsmallest(3, "oer_pct")[["code", "oer_pct"]].to_dict("records")}
        sens = {}
        if s.code == "PRESS_VIBRATION_ANOMALY":
            for code, agg, ro in (("PRS-03-VIB-DE", "max", False), ("PRS-03-TMP-BRG", "max", False), ("PRS-03-CUR", "mean", True), ("PRS-01-VIB-DE", "max", False)):
                sens[code] = {"focus": sensor_day(code, s.focus_ts, agg, ro), "baseline": sensor_day(code, s.baseline_ts, agg, ro), "agg": agg}
        elif s.code == "STEAM_PRESSURE_DEVIATION":
            for code, agg in (("FWP-01-VIB-DE", "max"), ("BLR-01-P-DRUM", "min"), ("TG-01-P-HDR", "min"), ("TG-01-LOAD", "mean")):
                sens[code] = {"focus": sensor_day(code, s.focus_ts, agg), "baseline": sensor_day(code, s.baseline_ts, agg), "agg": agg}
        elif s.code == "ENERGY_EFFICIENCY_DROP":
            for code, agg in (("BLR-01-TMP-FLUE", "max"), ("BLR-FAN-01-CUR", "mean"), ("BLR-01-FLOW-STM", "mean")):
                sens[code] = {"focus": sensor_day(code, s.focus_ts, agg), "baseline": sensor_day(code, s.baseline_ts, agg), "agg": agg}
        elif s.code == "OER_DEGRADATION":
            for code, agg in (("CLR-01-TMP", "min"), ("PRS-02-CUR", "mean")):
                sens[code] = {"focus": sensor_day(code, s.focus_ts, agg, code.endswith("CUR")), "baseline": sensor_day(code, s.baseline_ts, agg, code.endswith("CUR")), "agg": agg}
        item["sensors"] = sens
        out[s.code] = item
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.seed.report")
    ap.add_argument("--db-url", default=None)
    ap.add_argument("--out", default=None, help="write the JSON report to this path")
    a = ap.parse_args(argv)
    from app.seed.dburl import seed_db_url

    url = seed_db_url(a.db_url)
    from app.db.session import get_engine

    rep = chain_report(get_engine(url))
    txt = json.dumps(rep, indent=2, default=str, ensure_ascii=False)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(txt + "\n")
        print(f"report: wrote {a.out}")
    else:
        print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
