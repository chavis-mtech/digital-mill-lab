"""`python -m app.ml.train` (make models): train + evaluate every model on the temporal split, save artifacts to
data/models/<name>/<version>/, then run the causal detection pipeline into the DB named by DATABASE_URL.

Options: --db-url URL (default: settings DATABASE_URL), --no-write (train/evaluate only, no DB writes).
Reads the source DB read-only for training; writes only ML-owned rows (see app.ml.pipeline).
"""

from __future__ import annotations

import argparse
import json
import time

import numpy as np
import pandas as pd

from app.config import get_settings, resolve_database_url
from app.ml import energy, equipment, logistics, oer, oer_agg, production
from app.ml.common import MODELS_DIR, SEED, SPLIT_TS, WINDOW_END, db_fingerprint, ro_connect, utc_dt
from app.ml.data import (
    load_energy_plant_hourly,
    load_equipment,
    load_labels,
    load_rule_alerts,
    load_sensor_hourly,
    load_sensor_meta,
    load_trucks,
    sensor_wide,
)
from app.ml.events import score01
from app.ml.pipeline import Record, equipment_records, generic_records, production_records, write_all


def run(db_url: str, write: bool = True, verbose: bool = True) -> dict:
    np.random.seed(SEED)
    t0 = time.time()
    con = ro_connect(db_url)
    log = (lambda *a: print(*a, flush=True)) if verbose else (lambda *a: None)
    fp = db_fingerprint(con)
    meta, sh = load_sensor_meta(con), load_sensor_hourly(con)
    labels = load_labels(con)  # EVALUATION ONLY (scoring detections + tuning thresholds on the training period)
    eqp = load_equipment(con)
    energy_h = load_energy_plant_hourly(con)
    trucks = load_trucks(con)
    windows = pd.read_sql_query("SELECT code, start_ts, end_ts FROM scenario_runs", con)
    for c in ("start_ts", "end_ts"):
        windows[c] = pd.to_datetime(windows[c], utc=True, format="mixed")
    stage_ids = dict(pd.read_sql_query("SELECT code, id FROM process_stages", con).itertuples(index=False, name=None))

    log("[1/6] OER model ...")
    oer_res, df = oer.train(con, sh, meta)
    log(f"      served={oer_res.metrics['served_model']} test MAE={oer_res.headline[0]['model']} vs {oer_res.headline[0]['baseline_name']} "
        f"{oer_res.headline[0]['baseline']} beats_baseline={oer_res.beats_baseline}")
    gran = {g: oer_agg.evaluate_granularity(df, g) for g in ("shift_8h", "day")}
    hm = oer_res.metrics
    gran = {"hour": {"granularity": "hour", "blocks": hm["rows"], "selected_by_cv": hm["served_model"], "test": hm["test"],
                     "best_baseline_test": hm["best_baseline"], "beats_best_baseline": oer_res.beats_baseline,
                     "target_sd_test": hm["target_sd_test"],
                     "train_mean_test_mae": round(float(abs(df.loc[df.index >= SPLIT_TS].query("is_model_row")["oer_pct"]
                                                            - df.loc[df.index < SPLIT_TS].query("is_model_row")["oer_pct"].mean()).mean()), 4)},
            **gran}
    study, nowcast_art = oer_agg.nowcast_study(df, "day")
    oer_res.metrics["granularity_comparison"] = gran
    oer_res.metrics["nowcast_day"] = study
    oer_res.metrics["granularity_verdict"] = GRANULARITY_VERDICT
    oer_res.artifact["nowcast"] = nowcast_art
    for g, v in gran.items():
        log(f"      {g}: model {v['test'][v['selected_by_cv']]['mae']} vs best baseline {v['best_baseline_test']} "
            f"{v['test'][v['best_baseline_test']]['mae']} beats={v['beats_best_baseline']}")
    log(f"      nowcast(day) residual band +/-{study['residual_band_pp_90']} pp, test coverage {study['test_residual_band_coverage']}")
    log("[2/6] production anomaly ...")
    prod_res, prod_det = production.train_and_detect(df, energy_h, labels)
    log(f"      test {_brief(prod_res.metrics['test'])}")
    log("[3/6] equipment anomaly ...")
    wide = sensor_wide(sh, meta).reindex(df.index)
    eq_res, eq_det = equipment.train_and_detect(wide, sh, meta, df, labels, eqp, load_rule_alerts(con))
    log(f"      test {_brief(eq_res.metrics['test'])}; PRS-03 lead {eq_res.metrics['press_vibration_lead_time']}")
    log("[4/6] energy forecast + anomaly ...")
    efc_res, ean_res, e_det = energy.train_and_detect(df, energy_h, labels)
    log(f"      forecast MAE {efc_res.headline[0]}; anomaly test {_brief(ean_res.metrics['test'])}")
    log("[5/6] logistics ...")
    q_res = logistics.train_queue(trucks)
    a_res = logistics.train_arrivals(trucks, df.index)
    l_res, l_det = logistics.detect_flags(trucks, labels)
    log(f"      queue {q_res.headline[0]}; arrivals {a_res.headline[0]}")
    results = [oer_res, prod_res, eq_res, efc_res, ean_res, q_res, a_res, l_res]
    for r in results:
        r.metrics["data_fingerprint"] = fp
        r.save()

    summary = {"data_fingerprint": fp, "split_ts_utc": str(SPLIT_TS), "seed": SEED,
               "models": {r.name: {"beats_baseline": r.beats_baseline, "headline": r.headline} for r in results}}
    (MODELS_DIR / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")

    counts = {}
    if write:
        log("[6/6] detection pipeline -> DB ...")
        records: list[Record] = production_records(prod_det, stage_ids) + equipment_records(eq_det, wide, eqp)
        records += generic_records(e_det["events"], e_det["threshold"], lambda ev: energy.describe(ev, e_det), domain="energy",
                                   detector="residual_z_energy", model_name="energy_anomaly", entity_type="facility", entity_id=1,
                                   equipment_id=None, process_stage_id=None)
        records += logistics_records(l_det)
        preds = predictions(df, oer_res, e_det, q_res, a_res, trucks)
        from app.db.session import get_sessionmaker  # noqa: PLC0415

        with get_sessionmaker(db_url)() as db:
            counts = write_all(db, results, records, preds, windows, WINDOW_END)
        log(f"      wrote {counts}")
    log(f"done in {time.time() - t0:.1f} s")
    return {"summary": summary, "counts": counts, "results": results}


GRANULARITY_VERDICT = (
    "No granularity (hour, 8 h shift, calendar day) beats the naive baselines for FORECASTING OER on this synthetic data; "
    "the useful view is the day-level 'expected OER given current conditions' nowcast and its residual (actual - expected) "
    "with a 90% band, used as a diagnostic flag. Its driver attribution is unreliable out-of-sample (see nowcast_day)."
)


def logistics_records(l_det: dict) -> list[Record]:
    out = []
    for ev in l_det["weight_events"]:
        i = ev.info
        out.append(Record(
            domain="logistics", detector="weight_envelope", model_name="logistics_anomaly", entity_type="truck_trip",
            entity_id=i["truck_trip_id"], equipment_id=None, process_stage_id=None, start=ev.start, end=ev.end, peak=ev.peak_ts,
            detected_at=ev.detected_at, score=min(1.0, 0.5 + (ev.peak_raw - 1.0) * 3), title=f"Unusual net weight - needs review (trip {i['truck_trip_id']})",
            evidence={"trajectory": [{"t": ev.detected_at.isoformat(), "raw": ev.peak_raw, "signals": {"net_kg": {
                "z": None, "observed": i["net_kg"], "median": None, "mad": None, "envelope_kg": i["envelope_kg"]}}}],
                "sensor_meta": {"net_kg": {"type": "weight", "unit": "kg", "label": "Net weight", "high": i["envelope_kg"]}}, **i},
            contributing=["net weight above the usual envelope for this truck class (could be a weighing, tare or data-entry issue)"],
            investigation=["Re-check the weighbridge ticket (gross/tare) and the truck class", "Confirm weighbridge calibration log"],
            sensors=["net_kg"], rec_type="review_ticket", rec_title="Review weighbridge ticket (unusual, not an accusation)"))
    for ev in l_det["wait_events"]:
        i = ev.info
        out.append(Record(
            domain="logistics", detector="wait_p99", model_name="logistics_anomaly", entity_type="facility", entity_id=1, equipment_id=None,
            process_stage_id=None, start=ev.start, end=ev.end, peak=ev.peak_ts, detected_at=ev.detected_at,
            score=min(1.0, 0.5 + (ev.peak_raw - 1.0) * 0.5), title=f"{len(i['trucks'])} truck(s) waited longer than usual",
            evidence={"trajectory": [{"t": ev.detected_at.isoformat(), "raw": ev.peak_raw, "signals": {"wait_min": {
                "z": None, "observed": i["max_wait_min"], "median": None, "mad": None, "p99_min": i["p99_min"]}}}],
                "sensor_meta": {"wait_min": {"type": "time", "unit": "min", "label": "Longest arrival-to-weigh-in wait", "high": i["p99_min"]}},
                **i},
            contributing=["arrival surge, weighbridge or unloading-bay capacity reduced"],
            investigation=["Check weighbridge / unloading bay availability", "Consider staggered arrival slots (see queue simulation)"],
            sensors=["wait_min"], rec_type=None, rec_title=None, raise_alert=False))
    k = l_det["queue_k"]
    raw = l_det["queue_raw"]
    for ev in l_det["queue_events"]:
        seg = raw.loc[ev.start : ev.end - pd.Timedelta(hours=1)]
        out.append(Record(
            domain="logistics", detector="queue_window", model_name="logistics_anomaly", entity_type="facility", entity_id=1, equipment_id=None,
            process_stage_id=None, start=ev.start, end=ev.end, peak=ev.peak_ts, detected_at=ev.detected_at,
            score=float(score01(ev.peak_raw, k)), threshold=float(k),
            title=f"Sustained queue anomaly: up to {int(ev.peak_raw)} trucks beyond the usual wait within 3 h",
            evidence={"trajectory": [{"t": t.isoformat(), "raw": float(v), "signals": {"trucks_over_p99_3h": {
                "z": None, "observed": float(v), "median": None, "mad": None}}} for t, v in seg.items()],
                "sensor_meta": {"trucks_over_p99_3h": {"type": "count", "unit": "trucks/3 h", "label": "Trucks past the usual (P99) wait in 3 h",
                                                       "high": float(k)}}},
            contributing=["arrival surge, weighbridge or unloading-bay capacity reduced (possible factors, not proven)"],
            investigation=["Check weighbridge / unloading bay availability", "Consider staggered arrival slots (see queue simulation)"],
            sensors=["trucks_over_p99_3h"], rec_type="queue_review", rec_title="Review queue: sustained waits above the usual range"))
    return out


def predictions(df: pd.DataFrame, oer_res, e_det: dict, q_res, a_res, trucks: pd.DataFrame) -> list[dict]:
    out = []
    q = oer_res.artifact["conformal_half_width"]
    s = df["oer_pred_wf"].dropna()
    for t, v in s.items():
        out.append({"model": "oer_forecast", "target": "oer_pct", "entity_type": "facility", "entity_id": 1, "target_ts": utc_dt(t),
                    "made_at": utc_dt(t + pd.Timedelta(hours=1)), "horizon_minutes": 0, "value": round(float(v), 4),
                    "lower": round(float(v - q), 4), "upper": round(float(v + q), 4), "unit": "%",
                    "explanation_json": json.dumps({"method": "walk-forward weekly refit (out-of-sample)", "split": _split(t)})})
    exp = e_det["expected"].dropna()
    hw = float(e_det.get("half_width", 0) or 0)
    for t, v in exp.items():
        out.append({"model": "energy_forecast", "target": "electricity_kwh", "entity_type": "facility", "entity_id": 1, "target_ts": utc_dt(t),
                    "made_at": utc_dt(t + pd.Timedelta(hours=1)), "horizon_minutes": 0, "value": round(float(v), 2),
                    "lower": None if not hw else round(float(v - hw), 2), "upper": None if not hw else round(float(v + hw), 2), "unit": "kWh",
                    "explanation_json": json.dumps({"method": "walk-forward expected kWh given processed FFB (conditional)", "split": _split(t)})})
    qf = logistics.queue_frame(trucks)
    art = q_res.artifact
    X = qf[art["features"]]
    pv, lo, hi = art["model"].predict(X), art["lo"].predict(X), art["hi"].predict(X)
    for i, r in enumerate(qf.itertuples(index=False)):
        out.append({"model": "queue_time", "target": "queue_wait_min", "entity_type": "truck_trip", "entity_id": int(r.truck_trip_id),
                    "target_ts": utc_dt(r.arrival_ts), "made_at": utc_dt(r.arrival_ts), "horizon_minutes": None,
                    "value": round(max(0.0, float(pv[i])), 2), "lower": round(max(0.0, float(min(lo[i], pv[i]))), 2),
                    "upper": round(float(max(hi[i], pv[i])), 2), "unit": "min",
                    "explanation_json": json.dumps({"split": _split(r.arrival_ts), "note": "train-period rows are in-sample"})})
    af = logistics.arrival_frame(trucks, df.index).dropna()
    pa = a_res.artifact["model"].predict(af[a_res.artifact["features"]])
    for t, v in zip(af.index, pa, strict=True):
        out.append({"model": "arrival_forecast", "target": "arrivals", "entity_type": "facility", "entity_id": 1, "target_ts": utc_dt(t),
                    "made_at": utc_dt(t - pd.Timedelta(hours=24)), "horizon_minutes": 1440, "value": round(float(v), 3), "lower": None,
                    "upper": None, "unit": "trucks/h", "explanation_json": json.dumps({"split": _split(t)})})
    return out


def _split(t) -> str:
    return "test" if pd.Timestamp(t) >= SPLIT_TS else "train"


def _brief(m: dict) -> dict:
    return {k: m.get(k) for k in ("precision", "recall", "false_positives_per_day", "median_latency_h", "events")}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db-url", default=None)
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args()
    url = resolve_database_url(a.db_url) if a.db_url else get_settings().database_url
    run(url, write=not a.no_write)


if __name__ == "__main__":
    main()
