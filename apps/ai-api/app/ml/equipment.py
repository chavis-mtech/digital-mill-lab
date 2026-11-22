"""AI-C02 equipment anomaly detection (+ anomaly-score input for the rule-based risk index owned by backend-b).

Served detector (statistical, causal): per sensor, a robust baseline (expanding median/MAD of the equipment's own
*running* hours, recomputed daily from data older than 2 days) -> one-sided z on the 'bad' side (vibration/bearing
temperature/current high, low-is-bad process tags low) -> 3 h causal rolling mean -> equipment score = max over its
sensors. An event needs >= 3 consecutive hours above the threshold (tuned on the training period only).
Sensor-health events (flatline / missing data) are emitted separately and recommend a sensor check.
Comparator: per-equipment IsolationForest on the multivariate z-state, refitted weekly on past data only.
Nothing here is a failure probability; scores are relative anomaly scores (0-1).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from app.ml.common import SEED, SPLIT_TS, WINDOW_END, WINDOW_START, ModelResult
from app.ml.data import sensor_wide
from app.ml.events import (
    Event,
    evaluate_events,
    expanding_robust_stats,
    extract_events,
    labels_from_frame,
    per_scenario_table,
    tune_threshold,
    walk_forward,
)

SKIP_PREFIX = ("STR-", "TNK-", "DG-01", "CLR-01-LVL")
USE_TYPES = {"vibration", "temperature", "current", "pressure", "flow", "load"}
FLOORS = {"vibration": 0.08, "temperature": 0.6, "current": 1.0, "pressure": 0.05, "flow": 0.5, "load": 15.0}
THRESHOLD_GRID = [3.0, 3.5, 4.0, 4.5, 5.0, 6.0, 7.0, 8.0, 10.0]
MIN_LEN = 3
SMOOTH_H = 3
REC_BY_TYPE = {
    "vibration": ("inspect_bearing", "Inspect bearing condition and alignment (vibration spectrum, looseness, lubrication)"),
    "temperature": ("lubrication", "Check lubrication and cooling; confirm with an IR / contact thermometer reading"),
    "current": ("alignment", "Check mechanical load, friction and alignment; compare motor current with throughput"),
    "pressure": ("process_check", "Check the pressure loop (pump, valves, steam supply) and confirm the transmitter reading"),
    "flow": ("process_check", "Check the flow loop and confirm the meter reading"),
    "load": ("process_check", "Check the generator/turbine loading and steam supply"),
    "sensor": ("sensor_check", "Sensor check: the signal looks frozen or missing - verify the transmitter and wiring before trusting it"),
}


def direction_for(row) -> str:
    if row.sensor_type in ("vibration",):
        return "high"
    if row.sensor_type == "temperature":
        return "low" if bool(row.low_is_bad) else "high"
    if row.sensor_type == "pressure":
        return "low" if bool(row.low_is_bad) else "high"
    if row.sensor_type == "current":
        return "high"  # friction / overload; low current = unloaded or idle (an energy question, not equipment health)
    return "both"


def select_sensors(meta: pd.DataFrame) -> pd.DataFrame:
    m = meta[meta["sensor_type"].isin(USE_TYPES) & ~meta["code"].str.startswith(SKIP_PREFIX)].copy()
    m["direction"] = [direction_for(r) for r in m.itertuples()]
    return m


def running_mask(wide_min: pd.DataFrame, meta: pd.DataFrame, process: pd.DataFrame) -> pd.DataFrame:
    """Per-equipment steady-running flag per hour (causal): every sample of the motor current in this hour AND the
    previous hour > 25 % of its normal max (excludes start/stop hours and thermal transients); equipment without a
    current sensor follows the mill (full running hour now and in the previous hour)."""
    mill_full = (process["running_minutes"] >= 59).reindex(wide_min.index).fillna(False)
    mill = mill_full & mill_full.shift(1, fill_value=False)
    out = {}
    for eq, g in meta.groupby("equipment_code"):
        cur = g[g["sensor_type"] == "current"]
        if len(cur):
            r = cur.iloc[0]
            on = (wide_min[r.code] > 0.25 * r.normal_max).fillna(False)
            out[eq] = on & on.shift(1, fill_value=False)
        else:
            out[eq] = mill
    return pd.DataFrame(out, index=wide_min.index)


def compute_scores(wide: pd.DataFrame, meta: pd.DataFrame, process: pd.DataFrame, wide_min: pd.DataFrame) -> dict:
    sel = select_sensors(meta)
    run = running_mask(wide_min, meta, process)
    dz = {}  # sensor -> directional z (smoothed)
    sz = {}
    base = {}
    for r in sel.itertuples():
        x = wide[r.code].where(run[r.equipment_code])
        med, mad = expanding_robust_stats(x)
        z = (x - med) / np.maximum(mad, FLOORS[r.sensor_type])
        d = -z if r.direction == "low" else z if r.direction == "high" else z.abs()
        dz[r.code] = d.clip(lower=0).rolling(SMOOTH_H, min_periods=2).mean()
        sz[r.code] = z
        base[r.code] = (med, mad)
    dz = pd.DataFrame(dz, index=wide.index)
    sz = pd.DataFrame(sz, index=wide.index)
    eq_raw = {eq: dz[g["code"].tolist()].max(axis=1, skipna=True) for eq, g in sel.groupby("equipment_code")}
    return {"sel": sel, "run": run, "dz": dz, "sz": sz, "base": base, "eq_raw": pd.DataFrame(eq_raw, index=wide.index)}


def sensor_health_events(sh: pd.DataFrame, meta: pd.DataFrame, run: pd.DataFrame, index: pd.DatetimeIndex) -> list[Event]:
    """Flatline (hourly min == max for >= 3 h while the equipment runs) and missing data (>= 3 h without samples)."""
    sel = select_sensors(meta)
    codes = sel.set_index("sensor_id")
    evs: list[Event] = []
    for sid, g in sh[sh["sensor_id"].isin(codes.index)].groupby("sensor_id"):
        r = codes.loc[sid]
        g = g.set_index("ts").reindex(index)
        _ = run
        flat = ((g["vmax"] - g["vmin"]).abs() < 1e-9) & (g["n"] >= 2) & (g["vmax"].abs() > 1e-6)
        missing = g["n"].isna()  # sensors report while the plant is stopped too, so a gap is a data problem
        for kind, flag in (("flatline", flat), ("missing_data", missing)):
            raw = flag.astype(float) * 10.0
            for e in extract_events(raw, 5.0, min_len=3, merge_gap_h=1, key=r.equipment_code):
                e.info = {"sensor_health": kind, "sensor": r.code, "sensor_type": r.sensor_type}
                evs.append(e)
    return evs


def iforest_raw(det: dict) -> pd.DataFrame:
    sel, sz, run = det["sel"], det["sz"], det["run"]
    out = {}
    for eq, g in sel.groupby("equipment_code"):
        X = sz[g["code"].tolist()].clip(-15, 15).where(run[eq])
        valid = X.notna().all(axis=1)
        Xv = X[valid]
        if len(Xv) < 200:
            continue
        arr = Xv.to_numpy()

        def fp(tr: np.ndarray, bl: np.ndarray, arr=arr) -> np.ndarray:
            m = IsolationForest(n_estimators=50, max_samples=min(256, int(tr.sum())), random_state=SEED).fit(arr[tr])
            return -m.score_samples(arr[bl])

        raw = pd.Series(walk_forward(Xv.index, fp, warmup_days=21), index=Xv.index)
        out[eq] = ((raw - 0.5) * 20).clip(lower=0).rolling(SMOOTH_H, min_periods=2).mean().reindex(sz.index)
    return pd.DataFrame(out, index=sz.index)


def events_from_raw(eq_raw: pd.DataFrame, thr: float) -> list[Event]:
    evs = []
    for eq in eq_raw.columns:
        evs.extend(extract_events(eq_raw[eq], thr, MIN_LEN, merge_gap_h=6, key=eq))
    return evs


def train_and_detect(wide: pd.DataFrame, sh: pd.DataFrame, meta: pd.DataFrame, process: pd.DataFrame, labels_df: pd.DataFrame,
                     equipment: pd.DataFrame, rule_alerts: pd.DataFrame) -> tuple[ModelResult, dict]:
    wide_min = sensor_wide(sh, meta, "vmin").reindex(wide.index)
    det = compute_scores(wide, meta, process, wide_min)
    key_map = dict(zip(equipment["id"].astype(int), equipment["code"], strict=True))
    eq_labels = labels_df[labels_df["equipment_id"].notna()]
    targets = labels_from_frame(eq_labels[eq_labels["domain"] == "equipment"], key_map)
    # any injected label legitimises a detection on its equipment; labels without an equipment (stage / plant level,
    # e.g. idle running, steam dip) legitimise detections on any equipment (key "")
    abnormal = labels_from_frame(labels_df, key_map)
    kw = {"tol_h": 12}
    thr, grid = tune_threshold(THRESHOLD_GRID, lambda t: events_from_raw(det["eq_raw"], t), targets, abnormal, **kw)
    health = sensor_health_events(sh, meta, det["run"], wide.index)
    events = events_from_raw(det["eq_raw"], thr)
    all_events = events + health
    test_p, train_p = (SPLIT_TS, WINDOW_END), (WINDOW_START, SPLIT_TS)
    m_test = evaluate_events(all_events, targets, abnormal, test_p, **kw)
    m_train = evaluate_events(all_events, targets, abnormal, train_p, **kw)
    m_stat_only = evaluate_events(events, targets, abnormal, test_p, **kw)
    ifr = iforest_raw(det)
    thr_if, grid_if = tune_threshold([1, 1.5, 2, 2.5, 3, 4, 5], lambda t: events_from_raw(ifr, t), targets, abnormal, **kw)
    m_if = evaluate_events(events_from_raw(ifr, thr_if), targets, abnormal, test_p, **kw)
    m_if_train = evaluate_events(events_from_raw(ifr, thr_if), targets, abnormal, train_p, **kw)
    # rule baseline: the seeded threshold alarms (data-engine) as detections on the same labels
    rule_events = []
    for r in rule_alerts[rule_alerts["equipment_id"].notna()].itertuples():
        t = r.raised_at
        rule_events.append(Event(start=t, end=t + pd.Timedelta(hours=1), detected_at=t, peak_ts=t, peak_raw=1.0,
                                 key=key_map.get(int(r.equipment_id), "")))
    m_rule = evaluate_events(rule_events, targets, abnormal, test_p, **kw)
    m_rule_train = evaluate_events(rule_events, targets, abnormal, train_p, **kw)

    lead = press_lead_time(all_events, rule_alerts, labels_df, key_map)

    def brief(m: dict) -> dict:
        return {k: m[k] for k in ("events", "precision", "recall", "f1", "false_positives_per_day", "median_latency_h", "target_labels",
                                  "detected_labels")}

    metrics = {
        "threshold_z": thr, "min_consecutive_hours": MIN_LEN, "smoothing_h": SMOOTH_H, "tuning_grid_train": grid,
        "sensors_monitored": int(len(det["sel"])), "equipment_monitored": int(det["eq_raw"].shape[1]),
        "test": m_test, "train_in_sample_tuning": brief(m_train), "test_statistical_only_no_sensor_health": brief(m_stat_only),
        "per_scenario_test": per_scenario_table(m_test["per_label"]),
        "press_vibration_lead_time": lead,
        "comparators": {
            "isolation_forest": {"threshold": thr_if, "test": brief(m_if), "train": brief(m_if_train), "tuning_grid_train": grid_if},
            "rule_threshold_alarms": {"test": brief(m_rule), "train": brief(m_rule_train),
                                      "note": "seeded alarm system (warn/crit limits, 3-sample debounce); latency = alarm time - label start"},
        },
        "label_definition": "targets = injected equipment-domain labels with an equipment (incl. sensor faults and equipment-domain "
                            "breakdowns); a detection is a true positive if it overlaps (12 h tolerance) any injected label on the "
                            "same equipment, or a plant/stage-level label without an equipment (e.g. idle running)",
    }
    beats = (m_test["f1"] or 0) > (m_rule["f1"] or 0)
    headline = [
        {"name": "precision", "model": m_test["precision"], "baseline": m_rule["precision"], "baseline_name": "rule_threshold_alarms",
         "better_is": "higher"},
        {"name": "recall", "model": m_test["recall"], "baseline": m_rule["recall"], "baseline_name": "rule_threshold_alarms",
         "better_is": "higher"},
        {"name": "false_positives_per_day", "model": m_test["false_positives_per_day"], "baseline": m_rule["false_positives_per_day"],
         "baseline_name": "rule_threshold_alarms", "better_is": "lower"},
        {"name": "median_latency_h", "model": m_test["median_latency_h"], "baseline": m_rule["median_latency_h"],
         "baseline_name": "rule_threshold_alarms", "better_is": "lower"},
        {"name": "press_lead_time_vs_critical_alarm_h", "model": lead.get("lead_vs_critical_alarm_h"), "baseline": 0.0,
         "baseline_name": "rule_threshold_alarms", "better_is": "higher"},
    ]
    res = ModelResult(
        name="equipment_anomaly", task="anomaly",
        algorithm="Per-sensor robust z (expanding median/MAD on running hours) + sensor-health rules; IsolationForest comparator",
        features=det["sel"]["code"].tolist(), metrics=metrics, beats_baseline=bool(beats),
        train_window=(WINDOW_START, SPLIT_TS), test_window=(SPLIT_TS, WINDOW_END),
        artifact={"threshold": thr, "sensors": det["sel"][["code", "sensor_type", "direction", "equipment_code"]].to_dict("records")},
        headline=headline,
    )
    det.update({"events": events, "health": health, "threshold": thr})
    return res, det


def press_lead_time(events: list[Event], rule_alerts: pd.DataFrame, labels_df: pd.DataFrame, key_map: dict[int, str]) -> dict:
    lab = labels_df[labels_df["code"] == "INJ-PRS-BRG"]
    if lab.empty:
        return {"available": False}
    lb = lab.iloc[0]
    eq = key_map.get(int(lb["equipment_id"]), "")
    hits = sorted((e for e in events if e.key == eq and e.detected_at >= lb["start_ts"] and e.start < lb["end_ts"]), key=lambda e: e.detected_at)
    ra = rule_alerts[(rule_alerts["equipment_id"] == lb["equipment_id"]) & (rule_alerts["raised_at"] >= lb["start_ts"])]
    warn = ra[ra["severity"] != "critical"]["raised_at"].min()
    crit = ra[ra["severity"] == "critical"]["raised_at"].min()
    first = hits[0].detected_at if hits else None
    out = {"available": True, "equipment": eq, "label_start": lb["start_ts"].isoformat(),
           "first_ml_detection": first.isoformat() if first is not None else None,
           "first_rule_warning": None if pd.isna(warn) else warn.isoformat(),
           "first_rule_critical": None if pd.isna(crit) else crit.isoformat()}
    if first is not None:
        out["latency_from_onset_h"] = round((first - lb["start_ts"]).total_seconds() / 3600, 1)
        out["lead_vs_warning_alarm_h"] = None if pd.isna(warn) else round((warn - first).total_seconds() / 3600, 1)
        out["lead_vs_critical_alarm_h"] = None if pd.isna(crit) else round((crit - first).total_seconds() / 3600, 1)
        out["detected_before_critical"] = bool(not pd.isna(crit) and first < crit)
    else:
        out["detected_before_critical"] = False
    return out


def describe_event(ev: Event, det: dict, wide: pd.DataFrame) -> dict:
    sel, dz, base = det["sel"], det["dz"], det["base"]
    if ev.info.get("sensor_health"):
        return {"trajectory": [], "sensor_health": ev.info}
    codes = sel[sel["equipment_code"] == ev.key]["code"].tolist()
    seg = dz.loc[ev.start : ev.end - pd.Timedelta(hours=1), codes]
    traj = []
    for t, row in seg.iterrows():
        top = row.dropna().sort_values(ascending=False)
        top = top[top >= 1.5].head(3)
        traj.append({"t": t.isoformat(), "raw": round(float(row.max(skipna=True)), 3),
                     "signals": {k: {"z": round(float(v), 2), "observed": _f(wide.at[t, k]), "median": _f(base[k][0].at[t]),
                                     "mad": _f(base[k][1].at[t])} for k, v in top.items()}})
    return {"trajectory": traj}


def _f(x) -> float | None:
    return None if x is None or pd.isna(x) else round(float(x), 4)
