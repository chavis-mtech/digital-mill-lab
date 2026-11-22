"""AI-E01 energy forecast and AI-E02 energy anomaly (owner: ml).

E01: hourly plant electricity (kWh) from production volume and operating state. It is a *conditional* forecast: the
processed tonnage / running minutes of the target hour are inputs (in production they would come from the
production plan). Baselines: seasonal-naive (same hour yesterday) and a linear "energy signature" (kWh = a + b*FFB +
c*running minutes) fitted on the training period. Model: HistGradientBoosting.
E02: residual of actual vs walk-forward expected kWh (weekly refits on past data only), robust z against an expanding
baseline, 6 h causal mean; events need >= 4 consecutive hours. Threshold tuned on the training period only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression

from app.ml.common import SEED, SPLIT_TS, WINDOW_END, WINDOW_START, ModelResult, assert_no_forbidden, mae, r4, rmse
from app.ml.events import (
    evaluate_events,
    expanding_robust_stats,
    extract_events,
    labels_from_frame,
    per_scenario_table,
    tune_threshold,
    walk_forward,
)

FEATURES = ["ffb_processed_t", "running_minutes", "throughput_tph", "hour_local", "weekday_local"]
SIGNATURE = ["ffb_processed_t", "running_minutes"]
TARGET = "electricity_kwh"
assert_no_forbidden(FEATURES)
MIN_LEN = 4
GRID = [2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 8.0]


def make_hgb() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=20,
                                         early_stopping=False, random_state=SEED)


def build_frame(process: pd.DataFrame, energy: pd.DataFrame) -> pd.DataFrame:
    df = process[["ffb_processed_t", "running_minutes", "throughput_tph"]].join(energy[[TARGET, "idle_kwh", "steam_t", "grid_import_kwh"]])
    loc = df.index + pd.Timedelta(hours=7)
    df["hour_local"] = loc.hour
    df["weekday_local"] = loc.day_of_week
    df["bl_seasonal_24h"] = df[TARGET].shift(24)
    return df.dropna(subset=[TARGET])


def train_and_detect(process: pd.DataFrame, energy: pd.DataFrame, labels_df: pd.DataFrame) -> tuple[ModelResult, ModelResult, dict]:
    df = build_frame(process, energy)
    tr, te = df[df.index < SPLIT_TS].dropna(subset=["bl_seasonal_24h"]), df[df.index >= SPLIT_TS]
    hgb = make_hgb().fit(tr[FEATURES], tr[TARGET])
    sig = LinearRegression().fit(tr[SIGNATURE], tr[TARGET])
    p, ps = hgb.predict(te[FEATURES]), sig.predict(te[SIGNATURE])
    y = te[TARGET]
    test = {"hgb": {"mae": r4(mae(y, p)), "rmse": r4(rmse(y, p))},
            "energy_signature_linear": {"mae": r4(mae(y, ps)), "rmse": r4(rmse(y, ps))},
            "seasonal_naive_24h": {"mae": r4(mae(y, te["bl_seasonal_24h"])), "rmse": r4(rmse(y, te["bl_seasonal_24h"]))}}
    day = (te.index + pd.Timedelta(hours=7)).floor("D")
    dy = y.groupby(day).sum()
    daily = {"days": int(len(dy)), "hgb_mae_kwh": r4(mae(dy, pd.Series(p, te.index).groupby(day).sum())),
             "signature_mae_kwh": r4(mae(dy, pd.Series(ps, te.index).groupby(day).sum())),
             "seasonal_naive_mae_kwh": r4(mae(dy[1:], te["bl_seasonal_24h"].groupby(day).sum()[1:])), "mean_daily_kwh": r4(float(dy.mean()))}
    best_bl = min(("energy_signature_linear", "seasonal_naive_24h"), key=lambda k: test[k]["mae"])
    resid = np.abs(tr[TARGET].to_numpy() - hgb.predict(tr[FEATURES]))
    q90 = float(np.quantile(resid, 0.9))
    cov = float(np.mean(np.abs(y.to_numpy() - p) <= q90))
    fc = ModelResult(
        name="energy_forecast", task="forecast", algorithm="HistGradientBoostingRegressor (conditional on planned FFB)",
        features=FEATURES, beats_baseline=bool(test["hgb"]["mae"] < test[best_bl]["mae"]),
        metrics={"rows": {"train": len(tr), "test": len(te)}, "test": test, "best_baseline": best_bl, "daily_totals_test": daily,
                 "interval": {"method": "P90 absolute in-sample training residual (not conformal; likely optimistic)",
                              "half_width_kwh": r4(q90), "test_coverage": r4(cov), "nominal": 0.9},
                 "notes": ["Conditional forecast: processed FFB and running minutes of the target hour are inputs (production plan)."]},
        train_window=(tr.index.min(), tr.index.max()), test_window=(te.index.min(), te.index.max()),
        artifact={"model": hgb, "signature": sig, "features": FEATURES, "half_width": q90},
        headline=[{"name": "mae", "model": test["hgb"]["mae"], "baseline": test[best_bl]["mae"], "baseline_name": best_bl, "better_is": "lower"},
                  {"name": "rmse", "model": test["hgb"]["rmse"], "baseline": test[best_bl]["rmse"], "baseline_name": best_bl,
                   "better_is": "lower"}],
    )

    # ---- E02 anomaly on walk-forward residuals
    X, Y = df[FEATURES], df[TARGET]
    expected = pd.Series(walk_forward(df.index, lambda a, b: make_hgb().fit(X[a], Y[a]).predict(X[b])), index=df.index)
    resid_s = (Y - expected)
    med, mad = expanding_robust_stats(resid_s)
    z = ((resid_s - med) / np.maximum(mad, 20.0)).clip(lower=0)
    raw = z.rolling(6, min_periods=3).mean()
    targets = labels_from_frame(labels_df[labels_df["domain"] == "energy"])
    abnormal = labels_from_frame(labels_df)
    kw = {"key_match": False, "tol_h": 6}
    thr, grid = tune_threshold(GRID, lambda t: extract_events(raw, t, MIN_LEN), targets, abnormal, **kw)
    events = extract_events(raw, thr, MIN_LEN)
    m_test = evaluate_events(events, targets, abnormal, (SPLIT_TS, WINDOW_END), **kw)
    m_train = evaluate_events(events, targets, abnormal, (WINDOW_START, SPLIT_TS), **kw)
    # baseline detector: daily kWh/t above the plant's fixed 18.5 kWh/t rule (seeded rule alerts do the same)
    loc_day = (df.index + pd.Timedelta(hours=7)).floor("D")
    dd = df.groupby(loc_day).agg(kwh=(TARGET, "sum"), t=("ffb_processed_t", "sum"))
    dd = dd[dd["t"] >= 1000]
    rule_days = dd[dd["kwh"] / dd["t"] > 18.5].index
    from app.ml.events import Event  # noqa: PLC0415
    rule_events = [Event(start=d - pd.Timedelta(hours=7), end=d + pd.Timedelta(hours=17), detected_at=d + pd.Timedelta(hours=17),
                         peak_ts=d, peak_raw=1.0) for d in rule_days]
    m_rule = evaluate_events(rule_events, targets, abnormal, (SPLIT_TS, WINDOW_END), **kw)
    m_rule_train = evaluate_events(rule_events, targets, abnormal, (WINDOW_START, SPLIT_TS), **kw)

    def brief(m):
        return {k: m[k] for k in ("events", "precision", "recall", "f1", "false_positives_per_day", "median_latency_h", "target_labels")}

    an = ModelResult(
        name="energy_anomaly", task="anomaly", algorithm="Walk-forward HGB expected kWh + robust z on residual (6 h mean)",
        features=FEATURES + ["electricity_kwh (observed, compared with expectation)"], beats_baseline=None,
        metrics={"threshold_z": thr, "min_consecutive_hours": MIN_LEN, "tuning_grid_train": grid, "test": m_test,
                 "train_in_sample_tuning": brief(m_train), "per_scenario_test": per_scenario_table(m_test["per_label"]),
                 "per_scenario_train_in_sample": per_scenario_table(m_train["per_label"]),
                 "comparators": {"daily_kwh_per_t_rule_18_5": {"test": brief(m_rule), "train": brief(m_rule_train)}},
                 "caveat": "Only one energy label (idle-running night) falls in the test period; ENERGY_EFFICIENCY_DROP is in the "
                           "training period, so its result is in-sample for threshold tuning."},
        train_window=(WINDOW_START, SPLIT_TS), test_window=(SPLIT_TS, WINDOW_END),
        artifact={"threshold": thr},
        headline=[{"name": "recall", "model": m_test["recall"], "baseline": m_rule["recall"], "baseline_name": "daily_kwh_per_t_rule",
                   "better_is": "higher"},
                  {"name": "false_positives_per_day", "model": m_test["false_positives_per_day"], "baseline": m_rule["false_positives_per_day"],
                   "baseline_name": "daily_kwh_per_t_rule", "better_is": "lower"}],
    )
    if m_test["f1"] is not None and m_rule["f1"] is not None:
        an.beats_baseline = bool(m_test["f1"] > m_rule["f1"])
    detail = {"events": events, "threshold": thr, "expected": expected, "df": df, "z": z, "med": med, "mad": mad, "half_width": q90}
    return fc, an, detail


def describe(ev, detail: dict) -> dict:
    df, exp, z = detail["df"], detail["expected"], detail["z"]
    seg = df.loc[ev.start : ev.end - pd.Timedelta(hours=1)]
    traj = [{"t": t.isoformat(), "raw": round(float(z.get(t, 0) or 0), 3),
             "signals": {"electricity_kwh": {"z": round(float(z.get(t, 0) or 0), 2), "observed": round(float(r[TARGET]), 1),
                                             "median": None if pd.isna(exp.get(t)) else round(float(exp[t]), 1), "mad": None},
                         "idle_kwh": {"z": None, "observed": round(float(r["idle_kwh"]), 1), "median": None, "mad": None}}}
            for t, r in seg.iterrows()]
    idle = float(seg["idle_kwh"].sum())
    factors = ["electricity above the level expected for the processed volume and running time"]
    if idle > 0.3 * float(seg[TARGET].sum()):
        factors.append("large idle-running share (motors running while the line is not processing)")
    return {"evidence": {"trajectory": traj, "sensor_meta": {"electricity_kwh": {"type": "energy", "unit": "kWh", "label": "Plant electricity (hourly)"},
                                                              "idle_kwh": {"type": "energy", "unit": "kWh", "label": "Idle-running electricity"}},
                         "excess_kwh": round(float((seg[TARGET] - exp.reindex(seg.index)).sum()), 1)},
            "contributing": factors + ["possible: boiler fouling, steam leaks, compressed-air leaks, idle running"],
            "investigation": ["Check which motors ran while the line was stopped", "Walk-down for compressed-air and steam leaks",
                              "Compare boiler flue-gas temperature and ID-fan current with the usual range"],
            "title": "Energy use above production-adjusted expectation", "sensors": ["electricity_kwh", "idle_kwh"],
            "rec_type": "energy_check", "rec_title": "Energy check: find idle running / leaks in the flagged hours"}
