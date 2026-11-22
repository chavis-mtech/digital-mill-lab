"""AI-B01 OER model (owner: ml).

What it is: an hourly *expected-OER* model ("soft sensor" / nowcast) that predicts plant OER for an hour from the
process conditions observed in that hour (FFB quality, wait-to-process, sterilisation, steam, temperatures, press
state and equipment-condition proxies, calendar). Multi-hour forecasts hold the latest conditions constant
(persistence of drivers), which is stated in the API response.

Leakage audit: no OER/KER/CPO/kernel/oil-loss column and no injected_events/scenario field is a feature
(`assert_no_forbidden`). Every feature is observed at or before the target hour; delivery-quality features use only
deliveries received in the 12 h *before* the hour. Baselines use only OER values strictly before the target hour.
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.common import SEED, SPLIT_TS, ModelResult, assert_no_forbidden, mae, r4, rmse
from app.ml.data import delivery_quality_features, load_deliveries, load_process_hourly, load_sensor_hourly, load_sensor_meta, sensor_wide
from app.ml.events import walk_forward

FEATURE_GROUPS: dict[str, list[str]] = {
    "ffb_quality": ["ffb_ripe_pct", "recv_unripe_pct_12h", "recv_harvest_to_mill_h_12h"],
    "wait_to_process": ["avg_wait_to_process_h", "ffb_waiting_t"],
    "sterilization_steam": ["sterilizer_cycle_min", "steam_pressure_bar", "boiler_steam_t"],
    "process_temperatures": ["digester_temp_c", "clarifier_temp_c"],
    "press_condition": ["press_load_a", "press_cone_pressure_bar", "press_vib_max", "press_vib_mean", "press_cur_max"],
    "operating_rate": ["throughput_tph", "running_minutes"],
    "calendar": ["hour_local", "weekday_local", "day_of_year"],
}
FEATURES = [f for g in FEATURE_GROUPS.values() for f in g]
LABELS = {
    "ffb_ripe_pct": "Ripe FFB in feed (%)",
    "recv_unripe_pct_12h": "Unripe FFB received, last 12 h (%)",
    "recv_harvest_to_mill_h_12h": "Harvest-to-mill time, last 12 h (h)",
    "avg_wait_to_process_h": "FFB wait-to-process (h)",
    "ffb_waiting_t": "FFB on ramp (t)",
    "sterilizer_cycle_min": "Sterilizer cycle (min)",
    "steam_pressure_bar": "Steam header pressure (bar)",
    "boiler_steam_t": "Boiler steam (t/h)",
    "digester_temp_c": "Digester temperature (C)",
    "clarifier_temp_c": "Clarifier temperature (C)",
    "press_load_a": "Press load (A)",
    "press_cone_pressure_bar": "Press cone pressure (bar)",
    "press_vib_max": "Max press vibration (mm/s)",
    "press_vib_mean": "Mean press vibration (mm/s)",
    "press_cur_max": "Max press motor current (A)",
    "throughput_tph": "Throughput (t/h)",
    "running_minutes": "Running minutes in hour",
    "hour_local": "Hour of day (local)",
    "weekday_local": "Weekday (local)",
    "day_of_year": "Day of year (seasonality)",
}
TARGET = "oer_pct"
INTERVAL_ALPHA = 0.10  # 90 % prediction interval
# Time-lagged target feature, explicitly allowed by the leakage audit: mean of the last 24 *observed* hourly OER
# values strictly before the target hour (same quantity as the rolling-mean baseline).
LAG_LEVEL = "oer_level_lag24"
DELTA_BASE = ["ffb_ripe_pct", "recv_unripe_pct_12h", "recv_harvest_to_mill_h_12h", "avg_wait_to_process_h", "sterilizer_cycle_min",
              "steam_pressure_bar", "digester_temp_c", "clarifier_temp_c", "press_vib_max", "press_cur_max", "throughput_tph"]
DELTAS = [f"{f}_d24" for f in DELTA_BASE]
LEVEL_FEATURES = FEATURES + DELTAS + [LAG_LEVEL]
for _f in DELTA_BASE:
    LABELS[f"{_f}_d24"] = LABELS[_f] + " - change vs its trailing 24 h mean"
LABELS[LAG_LEVEL] = "Mean OER of the previous 24 running hours (lagged)"
assert_no_forbidden(FEATURES)
assert_no_forbidden(LEVEL_FEATURES, allow=(LAG_LEVEL,))


def make_hgb(seed: int = SEED, loss: str = "squared_error", quantile: float | None = None) -> HistGradientBoostingRegressor:
    kw = {"loss": loss, "max_iter": 300, "learning_rate": 0.05, "max_leaf_nodes": 15, "min_samples_leaf": 20,
          "l2_regularization": 1.0, "early_stopping": False, "random_state": seed}
    if quantile is not None:
        kw["quantile"] = quantile
    return HistGradientBoostingRegressor(**kw)


def make_rf(seed: int = SEED) -> RandomForestRegressor:
    return RandomForestRegressor(n_estimators=200, max_depth=12, min_samples_leaf=5, n_jobs=4, random_state=seed)


def make_ridge():
    return make_pipeline(StandardScaler(), Ridge(alpha=1.0))


# ---------------------------------------------------------------------------- features
def build_frame(con: sqlite3.Connection, sensor_hourly: pd.DataFrame | None = None, meta: pd.DataFrame | None = None,
                start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """All hours with features, target and the three naive baselines. Model rows = running hours with OER.
    Optional [start, end] bounds (UTC text) restrict every query - used by API inference with end <= as_of."""
    ph = load_process_hourly(con, start, end)
    idx = ph.index
    meta = meta if meta is not None else load_sensor_meta(con)
    if sensor_hourly is None:
        ids = meta[meta["code"].str.match(r"PRS-0\d-(VIB-DE|CUR)$")]["sensor_id"].tolist()
        # the hourly row stamped `end` covers [end, end + 1 h): callers pass a complete hour (end + 1 h <= as_of)
        s_end = None if end is None else (pd.Timestamp(end) + pd.Timedelta(minutes=59, seconds=59)).strftime("%Y-%m-%d %H:%M:%S")
        sensor_hourly = load_sensor_hourly(con, start, s_end, ids)
    sh = sensor_hourly
    w = sensor_wide(sh, meta).reindex(idx)
    vib = w[[f"PRS-0{i}-VIB-DE" for i in range(1, 5)]]
    cur = w[[f"PRS-0{i}-CUR" for i in range(1, 5)]]
    df = ph.copy()
    df["press_vib_max"] = vib.max(axis=1)
    df["press_vib_mean"] = vib.mean(axis=1)
    df["press_cur_max"] = cur.max(axis=1)
    d_start = None if start is None else str(pd.Timestamp(start) - pd.Timedelta(hours=13))
    df = df.join(delivery_quality_features(load_deliveries(con, d_start, end), idx))
    loc = idx + pd.Timedelta(hours=7)
    df["hour_local"] = loc.hour
    df["weekday_local"] = loc.day_of_week
    df["day_of_year"] = loc.day_of_year
    df["is_model_row"] = (df["ffb_processed_t"] > 0) & df[TARGET].notna() & (df["running_minutes"] >= 30)
    # naive baselines (strictly before t)
    y = df[TARGET].where(df["is_model_row"])
    obs = y.dropna()
    df["bl_persistence"] = obs.shift(1).reindex(idx).ffill() if len(obs) else np.nan
    df["bl_persistence"] = df["bl_persistence"].where(df["is_model_row"])
    prev = obs.shift(1).reindex(idx).ffill()
    df["bl_seasonal_24h"] = y.shift(24).fillna(prev)
    df["bl_rolling_24"] = obs.rolling(24, min_periods=6).mean().shift(1).reindex(idx).ffill()
    df[LAG_LEVEL] = df["bl_rolling_24"]
    run = df[df["is_model_row"]]
    for f in DELTA_BASE:
        trailing = run[f].rolling(24, min_periods=6).mean().shift(1).reindex(idx).ffill()
        df[f"{f}_d24"] = df[f] - trailing
    return df


def model_rows(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df["is_model_row"]].copy()
    return d.dropna(subset=["bl_persistence", "bl_rolling_24"])


# ---------------------------------------------------------------------------- training / evaluation
def _cv_folds(train: pd.DataFrame, n_folds: int = 3, block_days: int = 14) -> list[tuple[np.ndarray, np.ndarray]]:
    """Expanding-window folds inside the training period (validation blocks of 14 days at the end)."""
    folds = []
    for k in range(n_folds, 0, -1):
        v_end = SPLIT_TS - pd.Timedelta(days=block_days * (k - 1))
        v_start = v_end - pd.Timedelta(days=block_days)
        tr = np.asarray(train.index < v_start)
        va = np.asarray((train.index >= v_start) & (train.index < v_end))
        folds.append((tr, va))
    return folds


def _scenario_windows(con: sqlite3.Connection) -> pd.DataFrame:
    """Scenario windows from scenario_runs (EVALUATION ONLY: used to slice errors, never as features)."""
    s = pd.read_sql_query("SELECT code, start_ts, end_ts FROM scenario_runs", con)
    s["start_ts"] = pd.to_datetime(s["start_ts"], utc=True, format="mixed")
    s["end_ts"] = pd.to_datetime(s["end_ts"], utc=True, format="mixed")
    return s


class Candidate:
    """A model spec. resid=True -> predicts (OER - lagged 24 h level) and adds the level back."""

    def __init__(self, name: str, make, features: list[str], resid: bool):
        self.name, self.make, self.features, self.resid = name, make, features, resid
        self.model = None

    def fit(self, d: pd.DataFrame) -> Candidate:
        y = d[TARGET] - d[LAG_LEVEL] if self.resid else d[TARGET]
        self.model = self.make().fit(d[self.features], y)
        return self

    def predict(self, d: pd.DataFrame) -> np.ndarray:
        p = self.model.predict(d[self.features])
        return p + d[LAG_LEVEL].to_numpy() if self.resid else p


class _CandEstimator(RegressorMixin, BaseEstimator):
    """sklearn-compatible view of a fitted Candidate (permutation importance only; never refit)."""

    def __init__(self, candidate: Candidate | None = None):
        self.candidate = candidate

    def fit(self, X, y=None):  # pragma: no cover
        return self

    def predict(self, X):
        return self.candidate.predict(X)


CANDIDATES = {
    "hgb_drivers": (make_hgb, FEATURES, False),
    "ridge_drivers": (make_ridge, FEATURES, False),
    "random_forest_drivers": (make_rf, FEATURES, False),
    "hgb_level_plus_drivers": (make_hgb, LEVEL_FEATURES, True),
    "ridge_level_plus_drivers": (make_ridge, LEVEL_FEATURES, True),
}
BASELINES = ("bl_persistence", "bl_seasonal_24h", "bl_rolling_24")
ANOMALY_EXPECTATION = "hgb_drivers"  # expected OER from same-hour conditions only (no lagged OER) for residual detection


def cand(name: str) -> Candidate:
    mk, feats, resid = CANDIDATES[name]
    return Candidate(name, mk, feats, resid)


def train(con: sqlite3.Connection, sensor_hourly: pd.DataFrame | None = None, meta: pd.DataFrame | None = None) -> tuple[ModelResult, pd.DataFrame]:
    df = build_frame(con, sensor_hourly, meta)
    d = model_rows(df).dropna(subset=DELTAS)
    train_df, test_df = d[d.index < SPLIT_TS], d[d.index >= SPLIT_TS]
    yte = test_df[TARGET]

    # --- expanding-window CV inside train: selects the served model (the test period is NOT used for selection)
    cv_rows = []
    for i, (tr, va) in enumerate(_cv_folds(train_df)):
        row = {"fold": i + 1, "val_start": str(train_df.index[va][0]), "val_end": str(train_df.index[va][-1]), "n_val": int(va.sum())}
        for name in CANDIDATES:
            c = cand(name).fit(train_df[tr])
            row[name] = r4(mae(train_df[TARGET][va], c.predict(train_df[va])))
        for bl in BASELINES:
            row[bl] = r4(mae(train_df[TARGET][va], train_df[bl][va]))
        cv_rows.append(row)
    cv_mean = {k: r4(float(np.mean([r[k] for r in cv_rows]))) for k in list(CANDIDATES) + list(BASELINES)}
    served = min(CANDIDATES, key=lambda k: cv_mean[k])

    # --- every candidate refit on the full training period, evaluated ONCE on the test period
    fitted = {name: cand(name).fit(train_df) for name in CANDIDATES}
    preds = {name: c.predict(test_df) for name, c in fitted.items()}
    test_metrics = {name: {"mae": r4(mae(yte, p)), "rmse": r4(rmse(yte, p))} for name, p in preds.items()}
    for bl in BASELINES:
        test_metrics[bl] = {"mae": r4(mae(yte, test_df[bl])), "rmse": r4(rmse(yte, test_df[bl]))}
    best_bl = min(BASELINES, key=lambda b: test_metrics[b]["mae"])  # strictest comparison: best baseline in hindsight
    model = fitted[served]
    p_srv = preds[served]

    # --- prediction intervals: split-conformal (calibrate on the last 14 train days) vs quantile HGB
    cal_start = SPLIT_TS - pd.Timedelta(days=14)
    fit_df, cal_df = train_df[train_df.index < cal_start], train_df[train_df.index >= cal_start]
    resid = np.abs(cal_df[TARGET].to_numpy() - cand(served).fit(fit_df).predict(cal_df))
    n_cal = len(resid)
    q_level = min(1.0, np.ceil((n_cal + 1) * (1 - INTERVAL_ALPHA)) / n_cal)
    q_conf = float(np.quantile(resid, q_level))
    cov_conf = float(np.mean(np.abs(yte.to_numpy() - p_srv) <= q_conf))
    feats_q = model.features
    yq = train_df[TARGET] - (train_df[LAG_LEVEL] if model.resid else 0)
    add = test_df[LAG_LEVEL].to_numpy() if model.resid else 0
    lo = make_hgb(loss="quantile", quantile=INTERVAL_ALPHA / 2).fit(train_df[feats_q], yq).predict(test_df[feats_q]) + add
    hi = make_hgb(loss="quantile", quantile=1 - INTERVAL_ALPHA / 2).fit(train_df[feats_q], yq).predict(test_df[feats_q]) + add
    cov_q = float(np.mean((yte.to_numpy() >= lo) & (yte.to_numpy() <= hi)))
    intervals = {
        "nominal_coverage": 1 - INTERVAL_ALPHA,
        "split_conformal": {"half_width_pp": r4(q_conf), "calibration_rows": n_cal, "test_coverage": r4(cov_conf)},
        "quantile_hgb": {"mean_width_pp": r4(float(np.mean(hi - lo))), "test_coverage": r4(cov_q)},
        "served": "split_conformal",
    }

    # --- permutation importance of the served model (test period)
    Xte = test_df[model.features]
    pi = permutation_importance(_CandEstimator(model), Xte, yte, n_repeats=5, random_state=SEED, scoring="neg_mean_absolute_error")
    imp = {f: float(max(0.0, v)) for f, v in zip(model.features, pi.importances_mean, strict=True)}
    tot = sum(imp.values()) or 1.0
    importance = sorted(({"feature": f, "label": LABELS[f], "mae_increase_pp": r4(v), "importance": r4(v / tot)} for f, v in imp.items()),
                        key=lambda r: -r["mae_increase_pp"])

    # --- ablation: drivers-only HGB, remove one driver group at a time / keep one group only
    ablation = [{"removed_group": "(none - drivers-only HGB)", "features_left": len(FEATURES), "test_mae": test_metrics["hgb_drivers"]["mae"]}]
    only = {}
    for g, cols in FEATURE_GROUPS.items():
        keep = [f for f in FEATURES if f not in cols]
        m = make_hgb().fit(train_df[keep], train_df[TARGET])
        ablation.append({"removed_group": g, "features_left": len(keep), "test_mae": r4(mae(yte, m.predict(test_df[keep])))})
        m1 = make_hgb().fit(train_df[cols], train_df[TARGET])
        only[g] = r4(mae(yte, m1.predict(test_df[cols])))
    lvl_only = r4(mae(yte, test_df[LAG_LEVEL]))

    # --- walk-forward (weekly refits on past data only) for the served model and the anomaly expectation model
    wf_served = walk_forward_predictions(df, served)
    wf_expect = walk_forward_predictions(df, ANOMALY_EXPECTATION)
    sw = _scenario_windows(con)
    per_scn = []
    for r in sw.itertuples(index=False):
        msk = (d.index >= r.start_ts) & (d.index < r.end_ts)
        if msk.sum() == 0:
            continue
        sub = d[msk]
        pred = wf_served.reindex(sub.index)
        ok = pred.notna()
        per_scn.append({
            "scenario": r.code, "side": "test" if r.start_ts >= SPLIT_TS else "train", "hours": int(msk.sum()),
            "walk_forward_mae": r4(mae(sub[TARGET][ok], pred[ok])) if ok.any() else None,
            "persistence_mae": r4(mae(sub[TARGET], sub["bl_persistence"])),
            "rolling24_mae": r4(mae(sub[TARGET], sub["bl_rolling_24"])),
            "mean_actual_oer": r4(float(sub[TARGET].mean())),
            "mean_walk_forward_pred": r4(float(pred[ok].mean())) if ok.any() else None,
        })
    wft = wf_served.reindex(test_df.index)
    okt = wft.notna()

    # --- daily view: feed-weighted daily OER from the same hourly test predictions vs day-level naive baselines
    daily = _daily_view(test_df, p_srv, d)

    beats = test_metrics[served]["mae"] < test_metrics[best_bl]["mae"]
    metrics = {
        "daily_aggregate_test": daily,
        "rows": {"train": len(train_df), "test": len(test_df)},
        "served_model": served,
        "selection": "lowest mean MAE over 3 expanding-window folds inside the training period",
        "cv_mean_mae": cv_mean,
        "cv_expanding_window": cv_rows,
        "test": test_metrics,
        "best_baseline": best_bl,
        "intervals": intervals,
        "permutation_importance_test": importance,
        "ablation_remove_group": ablation,
        "single_group_only_test_mae": only,
        "lagged_level_only_test_mae": lvl_only,
        "per_scenario": per_scn,
        "walk_forward_test_mae": r4(mae(test_df[TARGET][okt], wft[okt])),
        "target_sd_test": r4(float(yte.std())),
        "notes": [
            "Synthetic data: OER is generated by a deterministic loss model plus noise and every driver is observable; real plants will differ.",
            "Hourly OER carries hourly + daily noise that no same-hour driver explains; a 24 h rolling mean of past OER is a strong baseline.",
            "The model is a nowcast from same-hour conditions (+ lagged OER level for the level model); baselines use only past OER.",
        ],
    }
    headline = [
        {"name": "mae", "model": test_metrics[served]["mae"], "baseline": test_metrics[best_bl]["mae"], "baseline_name": best_bl,
         "better_is": "lower"},
        {"name": "rmse", "model": test_metrics[served]["rmse"], "baseline": test_metrics[best_bl]["rmse"], "baseline_name": best_bl,
         "better_is": "lower"},
        {"name": "interval_coverage_90", "model": intervals["split_conformal"]["test_coverage"], "baseline": 0.9,
         "baseline_name": "nominal", "better_is": "closer"},
    ]
    medians = {f: float(np.nanmedian(train_df[f])) for f in model.features}
    artifact = {"model": model, "served": served, "features": model.features, "labels": LABELS, "conformal_half_width": q_conf,
                "train_medians": medians, "importance": importance, "groups": FEATURE_GROUPS,
                "expectation_model": fitted[ANOMALY_EXPECTATION]}
    res = ModelResult(
        name="oer_forecast", task="regression",
        algorithm=f"{served} (sklearn; candidates HGB/Ridge/RandomForest) + split-conformal 90% interval",
        features=model.features, metrics=metrics, beats_baseline=bool(beats),
        train_window=(train_df.index.min(), train_df.index.max()), test_window=(test_df.index.min(), test_df.index.max()),
        artifact=artifact, headline=headline,
    )
    df["oer_pred_wf"] = wf_served
    df["oer_expected_wf"] = wf_expect
    return res, df


def _daily_view(test_df: pd.DataFrame, pred: np.ndarray, all_rows: pd.DataFrame) -> dict:
    def wavg(frame: pd.DataFrame, col: str) -> pd.Series:
        day = (frame.index + pd.Timedelta(hours=7)).floor("D")
        w = frame["ffb_processed_t"]
        return (frame[col] * w).groupby(day).sum() / w.groupby(day).sum()

    t = test_df.assign(_pred=pred)
    act = wavg(t, TARGET)
    mdl = wavg(t, "_pred")
    hist = wavg(all_rows, TARGET)  # all days (train+test) for lagged daily baselines
    prev_day = hist.shift(1).reindex(act.index)
    mean7 = hist.rolling(7, min_periods=3).mean().shift(1).reindex(act.index)
    ok = prev_day.notna() & mean7.notna()
    return {
        "days": int(ok.sum()),
        "model_mae": r4(mae(act[ok], mdl[ok])),
        "previous_day_mae": r4(mae(act[ok], prev_day[ok])),
        "trailing_7d_mean_mae": r4(mae(act[ok], mean7[ok])),
        "daily_sd": r4(float(act[ok].std())),
        "note": "daily OER = FFB-weighted mean of hourly values (business day, Asia/Bangkok); model = same-day hourly nowcasts aggregated",
    }


def walk_forward_predictions(df: pd.DataFrame, name: str) -> pd.Series:
    """Out-of-sample predictions for every model row: weekly refits on data strictly before each week."""
    d = model_rows(df).dropna(subset=DELTAS)

    def fp(tr: np.ndarray, bl: np.ndarray) -> np.ndarray:
        return cand(name).fit(d[tr]).predict(d[bl])

    return pd.Series(walk_forward(d.index, fp), index=d.index).reindex(df.index)


def explain(artifact: dict, row: pd.Series) -> tuple[float, list[dict]]:
    """Local occlusion explanation: change in prediction when one feature is replaced by its training median."""
    model: Candidate = artifact["model"]
    feats = artifact["features"]
    x = row[feats].astype(float).to_frame().T.reset_index(drop=True)
    if model.resid and LAG_LEVEL not in x:
        x[LAG_LEVEL] = float(row[LAG_LEVEL])
    base = float(model.predict(x)[0])
    imp = {r["feature"]: r["importance"] for r in artifact["importance"]}
    xs = pd.concat([x] * len(feats), ignore_index=True)
    for i, f in enumerate(feats):
        xs.loc[i, f] = artifact["train_medians"][f]
    preds = model.predict(xs)
    out = []
    for i, f in enumerate(feats):
        v = row[f]
        out.append({"feature": f, "label": artifact["labels"][f], "value": None if pd.isna(v) else round(float(v), 4),
                    "contribution": round(base - float(preds[i]), 4), "importance": imp.get(f)})
    return base, sorted(out, key=lambda r: -abs(r["contribution"]))
