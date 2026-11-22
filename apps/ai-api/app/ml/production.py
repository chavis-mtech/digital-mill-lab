"""AI-B02 production anomaly detection (owner: ml).

Two detectors over the hourly plant state, both causal:
1. statistical (served): one-sided robust z-scores of process signals against an expanding median/MAD baseline
   (recomputed daily from data older than 2 days) + the OER residual versus the walk-forward expected-OER model;
   hourly score = max directional z; an event needs >= 2 consecutive hours above the threshold.
2. IsolationForest comparator on the multivariate z-state, refitted weekly on past data only.
Thresholds are tuned on the training period only; injected_events are used only to score detections.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from app.ml.common import SEED, SPLIT_TS, WINDOW_END, WINDOW_START, ModelResult
from app.ml.events import (
    Label,
    evaluate_events,
    expanding_robust_stats,
    extract_events,
    labels_from_frame,
    per_scenario_table,
    robust_z,
    tune_threshold,
    walk_forward,
)

# signal -> (direction, MAD floor, label, unit)
SIGNALS: dict[str, tuple[str, float, str, str]] = {
    "oer_residual_4h": ("low", 0.08, "OER vs expected (4 h mean residual)", "pp"),
    "steam_pressure_bar": ("low", 0.03, "Steam header pressure", "bar"),
    "throughput_tph": ("low", 1.0, "Processing rate while running", "t/h"),
    "sterilizer_cycle_min": ("both", 1.0, "Sterilizer cycle time", "min"),
    "digester_temp_c": ("low", 0.3, "Digester temperature", "degC"),
    "clarifier_temp_c": ("low", 0.3, "Clarifier temperature", "degC"),
    "oil_loss_total_pct": ("high", 0.02, "Total oil loss (% FFB)", "% FFB"),
    "kwh_per_t": ("high", 0.5, "Electricity per tonne FFB (hourly)", "kWh/t"),
    "unplanned_downtime_min": ("high", 5.0, "Unplanned downtime in hour (outside the Sunday 05-13 planned stop)", "min"),
}
FACTOR_HINTS = {
    "oer_residual_4h": "OER below the level expected from current FFB quality and process conditions",
    "steam_pressure_bar": "steam supply shortfall (boiler output, feed-water, fuel moisture)",
    "throughput_tph": "processing-rate restriction (equipment derate, stoppage, feed interruption)",
    "sterilizer_cycle_min": "sterilisation cycle deviating from the usual profile (under/over-cooking risk)",
    "digester_temp_c": "low digester temperature (steam supply or heating)",
    "clarifier_temp_c": "low clarifier temperature (steam valve / heating)",
    "oil_loss_total_pct": "elevated oil losses (press, sterilisation, clarification)",
    "kwh_per_t": "electricity intensity above usual for the processed volume",
    "unplanned_downtime_min": "unplanned stoppage (equipment breakdown, feed interruption)",
}
INVESTIGATION = {
    "oer_residual_4h": "Review lab oil-loss samples (press fibre, EFB, sludge) for the flagged hours",
    "steam_pressure_bar": "Check boiler drum / BPV header pressure trend and feed-water pump condition",
    "throughput_tph": "Check stoppage log and press / thresher availability for the flagged hours",
    "sterilizer_cycle_min": "Compare sterilizer cycle recipe and steam availability with the operator log",
    "digester_temp_c": "Verify digester steam valves and temperature sensors",
    "clarifier_temp_c": "Verify clarifier steam valve position and temperature sensor",
    "oil_loss_total_pct": "Take additional oil-loss samples and inspect press screws / clarifier operation",
    "kwh_per_t": "Check for idle-running motors and compressed-air leaks during the flagged hours",
    "unplanned_downtime_min": "Review the stoppage log and the equipment that tripped during the flagged hours",
}
THRESHOLD_GRID = [3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 7.0, 8.0, 10.0]
MIN_LEN = 2


def signal_frame(df: pd.DataFrame, energy: pd.DataFrame) -> pd.DataFrame:
    """df = OER frame from app.ml.oer (process_hourly + expected OER). Values only on running hours."""
    run = (df["running_minutes"] >= 30) & (df["ffb_processed_t"] > 5)
    s = pd.DataFrame(index=df.index)
    resid = (df["oer_pct"] - df["oer_expected_wf"]).where(run)
    s["oer_residual_4h"] = resid.dropna().rolling(4, min_periods=2).mean().reindex(df.index)
    for c in ("steam_pressure_bar", "throughput_tph", "sterilizer_cycle_min", "digester_temp_c", "clarifier_temp_c", "oil_loss_total_pct"):
        s[c] = df[c].where(run)
    e = energy.reindex(df.index)
    s["kwh_per_t"] = (e["electricity_kwh"] / df["ffb_processed_t"]).where(run & (df["ffb_processed_t"] > 20))
    loc = df.index + pd.Timedelta(hours=7)
    planned = (loc.day_of_week == 6) & (loc.hour >= 5) & (loc.hour < 13)  # documented plant schedule, not ground truth
    s["unplanned_downtime_min"] = df["downtime_min"].where(~planned, 0.0)
    return s


def zscores(sig: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, tuple[pd.Series, pd.Series]]]:
    """Directional z (>= 0, 'bad' side) and signed z per signal, plus the causal baselines."""
    dz, sz, base = pd.DataFrame(index=sig.index), pd.DataFrame(index=sig.index), {}
    for c, (direction, floor, _l, _u) in SIGNALS.items():
        med, mad = expanding_robust_stats(sig[c])
        z = robust_z(sig[c], med, mad, floor)
        sz[c] = z
        dz[c] = (-z if direction == "low" else z if direction == "high" else z.abs()).clip(lower=0)
        base[c] = (med, mad)
    return dz, sz, base


def iforest_scores(sz: pd.DataFrame) -> pd.Series:
    X = sz.clip(-15, 15)
    valid = X.notna().all(axis=1)
    Xv = X[valid]
    idx = Xv.index

    def fp(tr: np.ndarray, bl: np.ndarray) -> np.ndarray:
        m = IsolationForest(n_estimators=100, max_samples=min(256, int(tr.sum())), random_state=SEED).fit(Xv.to_numpy()[tr])
        return -m.score_samples(Xv.to_numpy()[bl])

    raw = pd.Series(walk_forward(idx, fp, warmup_days=28), index=idx)
    # express as distance above the typical score: (s - 0.5) * 20 so that ~3 means clearly unusual
    return ((raw - 0.5) * 20).clip(lower=0).reindex(sz.index)


def _labels(labels_df: pd.DataFrame) -> tuple[list[Label], list[Label]]:
    tgt = labels_df[(labels_df["domain"].isin(["production", "quality"])) | (labels_df["scenario_code"] == "STEAM_PRESSURE_DEVIATION")]
    return labels_from_frame(tgt), labels_from_frame(labels_df)


def train_and_detect(df: pd.DataFrame, energy: pd.DataFrame, labels_df: pd.DataFrame) -> tuple[ModelResult, dict]:
    sig = signal_frame(df, energy)
    dz, sz, base = zscores(sig)
    stat_raw = dz.max(axis=1, skipna=True)
    if_raw = iforest_scores(sz)
    targets, abnormal = _labels(labels_df)
    kw = {"key_match": False, "tol_h": 6}

    def ev_stat(t: float):
        return extract_events(stat_raw, t, MIN_LEN)

    def ev_if(t: float):
        return extract_events(if_raw, t, MIN_LEN)

    thr, grid = tune_threshold(THRESHOLD_GRID, ev_stat, targets, abnormal, **kw)
    thr_if, grid_if = tune_threshold([1, 1.5, 2, 2.5, 3, 3.5, 4, 5], ev_if, targets, abnormal, **kw)
    test_p, train_p = (SPLIT_TS, WINDOW_END), (WINDOW_START, SPLIT_TS)
    events = ev_stat(thr)
    m_test = evaluate_events(events, targets, abnormal, test_p, **kw)
    m_train = evaluate_events(events, targets, abnormal, train_p, **kw)
    m_if_test = evaluate_events(ev_if(thr_if), targets, abnormal, test_p, **kw)
    m_if_train = evaluate_events(ev_if(thr_if), targets, abnormal, train_p, **kw)
    # naive baseline: OER-only rule (4 h residual z) - what an "OER below expected" alarm alone would catch
    oer_only = dz["oer_residual_4h"]
    thr_o, _ = tune_threshold(THRESHOLD_GRID, lambda t: extract_events(oer_only, t, MIN_LEN), targets, abnormal, **kw)
    m_oer_test = evaluate_events(extract_events(oer_only, thr_o, MIN_LEN), targets, abnormal, test_p, **kw)

    def brief(m: dict) -> dict:
        return {k: m[k] for k in ("events", "precision", "recall", "f1", "false_positives_per_day", "median_latency_h", "target_labels")}

    metrics = {
        "threshold_z": thr, "min_consecutive_hours": MIN_LEN, "tuning_grid_train": grid,
        "test": m_test, "train_in_sample_tuning": brief(m_train),
        "per_scenario_test": per_scenario_table(m_test["per_label"]),
        "comparators": {
            "isolation_forest": {"threshold": thr_if, "test": brief(m_if_test), "train": brief(m_if_train), "tuning_grid_train": grid_if},
            "oer_residual_only": {"threshold": thr_o, "test": brief(m_oer_test)},
        },
        "label_definition": "targets = injected production/quality labels + the STEAM_PRESSURE_DEVIATION driver; any injected label "
                            "makes a detection a true positive (tolerance 6 h after label end)",
    }
    rec, prec = m_test["recall"], m_test["precision"]
    rec_if, prec_if = m_if_test["recall"], m_if_test["precision"]
    beats = None
    if rec is not None and rec_if is not None:
        beats = (m_test["f1"] or 0) >= (m_if_test["f1"] or 0)
    headline = [
        {"name": "precision", "model": prec, "baseline": prec_if, "baseline_name": "isolation_forest", "better_is": "higher"},
        {"name": "recall", "model": rec, "baseline": rec_if, "baseline_name": "isolation_forest", "better_is": "higher"},
        {"name": "false_positives_per_day", "model": m_test["false_positives_per_day"], "baseline": m_if_test["false_positives_per_day"],
         "baseline_name": "isolation_forest", "better_is": "lower"},
        {"name": "median_latency_h", "model": m_test["median_latency_h"], "baseline": m_if_test["median_latency_h"],
         "baseline_name": "isolation_forest", "better_is": "lower"},
    ]
    res = ModelResult(
        name="production_anomaly", task="anomaly", algorithm="Robust z-score (expanding median/MAD) + OER residual; IsolationForest comparator",
        features=list(SIGNALS), metrics=metrics, beats_baseline=beats,
        train_window=(WINDOW_START, SPLIT_TS), test_window=(SPLIT_TS, WINDOW_END),
        artifact={"threshold": thr, "signals": SIGNALS, "min_len": MIN_LEN}, headline=headline,
    )
    _ = rec_if, prec_if
    detail = {"events": events, "dz": dz, "sig": sig, "base": base, "threshold": thr, "raw": stat_raw}
    return res, detail


def describe_event(ev, detail: dict) -> dict:
    """Evidence trajectory + contributing signals for one event (stored; truncated to as_of at read time)."""
    dz, sig, base = detail["dz"], detail["sig"], detail["base"]
    seg = dz.loc[ev.start : ev.end - pd.Timedelta(hours=1)]
    traj = []
    for t, row in seg.iterrows():
        top = row.dropna().sort_values(ascending=False)
        top = top[top >= 2.0].head(3)
        traj.append({"t": t.isoformat(), "raw": round(float(row.max(skipna=True)), 3),
                     "signals": {k: {"z": round(float(v), 2), "observed": _f(sig.at[t, k]), "median": _f(base[k][0].at[t]),
                                     "mad": _f(base[k][1].at[t])} for k, v in top.items()}})
    return {"trajectory": traj}


def _f(x) -> float | None:
    return None if x is None or pd.isna(x) else round(float(x), 4)
