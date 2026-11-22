"""AI-D01 queue-time prediction, AI-D02 arrival forecast, AI-D04 logistics review flags (owner: ml).

D01 target: minutes from truck arrival to weigh-in. Features are the yard state *at arrival* (trucks arrived but not
yet weighed in, trucks inside the yard, arrivals and weigh-ins in the previous 60 min, hour, weekday, truck type) -
all known at arrival time. Baseline (queueing / drain-time): wait = gate time + trucks ahead / recent weigh-in rate.
D02 target: trucks arriving per hour, forecast day-ahead (all lags >= 24 h). Baselines: hour x weekday profile of the
training period, seasonal-naive 24 h. Model: HGB.
D04: per-truck flags "unusual, needs review" (never an accusation): net weight above the class's training P99.5
envelope x factor, or wait above the training P99. Thresholds from the training period only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from app.ml.common import SEED, SPLIT_TS, WINDOW_END, WINDOW_START, ModelResult, assert_no_forbidden, mae, r4, rmse
from app.ml.events import Event, evaluate_events, extract_events, labels_from_frame

Q_FEATURES = ["trucks_ahead", "trucks_in_yard", "arrivals_last_60m", "weigh_ins_last_60m", "hour_local", "weekday_local", "truck_class"]
A_FEATURES = ["hour_local", "weekday_local", "lag_24h", "lag_168h", "mean_24h_lag24", "same_hour_mean_7d_lag24"]
assert_no_forbidden(Q_FEATURES + A_FEATURES)
CLASSES = {"pickup": 0, "six-wheel": 1, "ten-wheel": 2, "trailer": 3}


def make_hgb(loss: str = "squared_error", **kw) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(loss=loss, max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=20,
                                         early_stopping=False, random_state=SEED, **kw)


def queue_frame(trucks: pd.DataFrame) -> pd.DataFrame:
    t = trucks.dropna(subset=["arrival_ts", "weigh_in_ts"]).sort_values("arrival_ts").reset_index(drop=True)
    arr = t["arrival_ts"].astype("int64").to_numpy()
    win = np.sort(t["weigh_in_ts"].astype("int64").to_numpy())
    ext = np.sort(t["exit_ts"].dropna().astype("int64").to_numpy())
    h = np.int64(3600 * 1e9)
    n_arr_before = np.arange(len(t))  # sorted by arrival -> trucks arrived strictly before (ties ignored)
    n_win_by = np.searchsorted(win, arr, side="right")
    n_exit_by = np.searchsorted(ext, arr, side="right")
    df = pd.DataFrame({
        "truck_trip_id": t["id"], "arrival_ts": t["arrival_ts"],
        "trucks_ahead": np.maximum(0, n_arr_before - n_win_by),
        "trucks_in_yard": np.maximum(0, n_arr_before - n_exit_by),
        "arrivals_last_60m": n_arr_before - np.searchsorted(arr, arr - h, side="left"),
        "weigh_ins_last_60m": n_win_by - np.searchsorted(win, arr - h, side="left"),
    })
    loc = t["arrival_ts"] + pd.Timedelta(hours=7)
    df["hour_local"] = loc.dt.hour
    df["weekday_local"] = loc.dt.day_of_week
    df["truck_class"] = t["truck_type"].map(CLASSES).fillna(1).astype(int)
    df["wait_min"] = (t["weigh_in_ts"] - t["arrival_ts"]).dt.total_seconds() / 60
    return df


def train_queue(trucks: pd.DataFrame) -> ModelResult:
    df = queue_frame(trucks)
    tr, te = df[df["arrival_ts"] < SPLIT_TS], df[df["arrival_ts"] >= SPLIT_TS]
    gate = float(tr.loc[tr["trucks_ahead"] == 0, "wait_min"].median())
    rate_floor = float(tr["weigh_ins_last_60m"].median()) or 1.0

    def drain(d: pd.DataFrame) -> np.ndarray:
        rate = np.maximum(d["weigh_ins_last_60m"].to_numpy(), rate_floor * 0.25)
        return gate + d["trucks_ahead"].to_numpy() / rate * 60

    m = make_hgb().fit(tr[Q_FEATURES], tr["wait_min"])
    lo = make_hgb("quantile", quantile=0.1).fit(tr[Q_FEATURES], tr["wait_min"])
    hi = make_hgb("quantile", quantile=0.9).fit(tr[Q_FEATURES], tr["wait_min"])
    y = te["wait_min"]
    p, pb = m.predict(te[Q_FEATURES]), drain(te)
    cov = float(np.mean((y >= lo.predict(te[Q_FEATURES])) & (y <= hi.predict(te[Q_FEATURES]))))
    cong = (te["arrival_ts"] >= pd.Timestamp("2026-11-11 17:00", tz="UTC")) & (te["arrival_ts"] < pd.Timestamp("2026-11-15 17:00", tz="UTC"))
    test = {"hgb": {"mae": r4(mae(y, p)), "rmse": r4(rmse(y, p))}, "queue_drain_baseline": {"mae": r4(mae(y, pb)), "rmse": r4(rmse(y, pb))},
            "train_median_baseline": {"mae": r4(mae(y, np.full(len(y), tr["wait_min"].median())))},
            "congestion_window_trucks": int(cong.sum()),
            "congestion_window_hgb_mae": r4(mae(y[cong], p[cong.to_numpy()])),
            "congestion_window_baseline_mae": r4(mae(y[cong], pb[cong.to_numpy()])),
            "p10_p90_interval_coverage": r4(cov), "mean_wait_test_min": r4(float(y.mean()))}
    return ModelResult(
        name="queue_time", task="regression", algorithm="HistGradientBoostingRegressor (+ P10/P90 quantile models)",
        features=Q_FEATURES, beats_baseline=bool(test["hgb"]["mae"] < test["queue_drain_baseline"]["mae"]),
        metrics={"rows": {"train": len(tr), "test": len(te)}, "test": test, "gate_time_min": r4(gate), "rate_floor_per_h": rate_floor,
                 "notes": ["Target = arrival -> weigh-in minutes from the synthetic queue simulation (interval booking, FIFO-ish)."]},
        train_window=(tr["arrival_ts"].min(), tr["arrival_ts"].max()), test_window=(te["arrival_ts"].min(), te["arrival_ts"].max()),
        artifact={"model": m, "lo": lo, "hi": hi, "features": Q_FEATURES, "gate": gate, "rate_floor": rate_floor},
        headline=[{"name": "mae", "model": test["hgb"]["mae"], "baseline": test["queue_drain_baseline"]["mae"],
                   "baseline_name": "queue_drain_baseline", "better_is": "lower"},
                  {"name": "rmse", "model": test["hgb"]["rmse"], "baseline": test["queue_drain_baseline"]["rmse"],
                   "baseline_name": "queue_drain_baseline", "better_is": "lower"}],
    )


def arrival_frame(trucks: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    c = trucks.set_index("arrival_ts").assign(n=1)["n"].resample("h").sum().reindex(index, fill_value=0).astype(float)
    df = pd.DataFrame({"arrivals": c})
    loc = index + pd.Timedelta(hours=7)
    df["hour_local"], df["weekday_local"] = loc.hour, loc.day_of_week
    df["lag_24h"], df["lag_168h"] = c.shift(24), c.shift(168)
    df["mean_24h_lag24"] = c.rolling(24).mean().shift(24)
    df["same_hour_mean_7d_lag24"] = sum(c.shift(24 * k) for k in range(1, 8)) / 7
    return df


def train_arrivals(trucks: pd.DataFrame, index: pd.DatetimeIndex) -> ModelResult:
    df = arrival_frame(trucks, index).dropna()
    tr, te = df[df.index < SPLIT_TS], df[df.index >= SPLIT_TS]
    prof = tr.groupby(["weekday_local", "hour_local"])["arrivals"].mean()
    bl_prof = np.array([prof.get((w, h), np.nan) for w, h in zip(te["weekday_local"], te["hour_local"], strict=True)])
    m = make_hgb("poisson").fit(tr[A_FEATURES], tr["arrivals"])
    p = m.predict(te[A_FEATURES])
    y = te["arrivals"]
    test = {"hgb_poisson": {"mae": r4(mae(y, p)), "rmse": r4(rmse(y, p))},
            "hour_weekday_profile": {"mae": r4(mae(y, bl_prof)), "rmse": r4(rmse(y, bl_prof))},
            "seasonal_naive_24h": {"mae": r4(mae(y, te["lag_24h"])), "rmse": r4(rmse(y, te["lag_24h"]))},
            "mean_arrivals_per_h": r4(float(y.mean()))}
    best = min(("hour_weekday_profile", "seasonal_naive_24h"), key=lambda k: test[k]["mae"])
    return ModelResult(
        name="arrival_forecast", task="forecast", algorithm="HistGradientBoostingRegressor (Poisson loss), day-ahead",
        features=A_FEATURES, beats_baseline=bool(test["hgb_poisson"]["mae"] < test[best]["mae"]),
        metrics={"rows": {"train": len(tr), "test": len(te)}, "test": test, "best_baseline": best},
        train_window=(tr.index.min(), tr.index.max()), test_window=(te.index.min(), te.index.max()),
        artifact={"model": m, "features": A_FEATURES, "profile": prof.to_dict()},
        headline=[{"name": "mae", "model": test["hgb_poisson"]["mae"], "baseline": test[best]["mae"], "baseline_name": best, "better_is": "lower"},
                  {"name": "rmse", "model": test["hgb_poisson"]["rmse"], "baseline": test[best]["rmse"], "baseline_name": best,
                   "better_is": "lower"}],
    )


def detect_flags(trucks: pd.DataFrame, labels_df: pd.DataFrame) -> tuple[ModelResult, dict]:
    t = trucks.dropna(subset=["arrival_ts", "weigh_in_ts", "net_kg"]).copy()
    t["wait_min"] = (t["weigh_in_ts"] - t["arrival_ts"]).dt.total_seconds() / 60
    tr = t[t["arrival_ts"] < SPLIT_TS]
    env = tr.groupby("truck_type")["net_kg"].quantile(0.995).to_dict()
    wait_p99 = float(tr["wait_min"].quantile(0.99))
    w_labels = labels_from_frame(labels_df[labels_df["event_type"] == "implausible_weight"].assign(equipment_id=labels_df["entity_id"]),
                                 {int(i): str(int(i)) for i in t["id"]})
    abnormal = labels_from_frame(labels_df.assign(equipment_id=np.where(labels_df["entity_type"] == "truck_trip", labels_df["entity_id"], np.nan)),
                                 {int(i): str(int(i)) for i in t["id"]})

    def weight_events(factor: float) -> list[Event]:
        r = t["net_kg"] / t["truck_type"].map(env)
        sel = t[r > factor]
        return [Event(start=x.arrival_ts, end=x.exit_ts if pd.notna(x.exit_ts) else x.weigh_out_ts, detected_at=x.weigh_out_ts,
                      peak_ts=x.weigh_out_ts, peak_raw=float(x.net_kg / env[x.truck_type]), key=str(int(x.id)),
                      info={"flag": "weight", "net_kg": int(x.net_kg), "envelope_kg": float(env[x.truck_type]), "truck_type": x.truck_type,
                            "truck_trip_id": int(x.id)})
                for x in sel.itertuples() if pd.notna(x.weigh_out_ts)]

    rows = []
    for f in (1.0, 1.02, 1.05, 1.08):
        m = evaluate_events(weight_events(f), w_labels, abnormal, (WINDOW_START, SPLIT_TS), tol_h=1)
        rows.append({"factor": f, **{k: m[k] for k in ("events", "precision", "recall", "false_positives_per_day")}})
    ok = [r for r in rows if (r["recall"] or 0) == max(x["recall"] or 0 for x in rows)]
    factor = max(ok, key=lambda r: (r["precision"] or 0, r["factor"]))["factor"]
    wev = weight_events(factor)
    m_w_train = evaluate_events(wev, w_labels, abnormal, (WINDOW_START, SPLIT_TS), tol_h=1)
    m_w_test = evaluate_events(wev, w_labels, abnormal, (SPLIT_TS, WINDOW_END), tol_h=1)
    long = t[t["wait_min"] > wait_p99]
    wait_ev = [Event(start=x.arrival_ts, end=x.weigh_in_ts, detected_at=x.arrival_ts + pd.Timedelta(minutes=wait_p99), peak_ts=x.weigh_in_ts,
                     peak_raw=float(x.wait_min / wait_p99), key="", info={"flag": "wait", "wait_min": round(float(x.wait_min), 1),
                                                                         "p99_min": round(wait_p99, 1), "truck_trip_id": int(x.id)})
               for x in long.itertuples()]
    wait_ev = _merge(sorted(wait_ev, key=lambda e: e.detected_at), gap=pd.Timedelta(hours=2))
    q_labels = labels_from_frame(labels_df[(labels_df["domain"] == "logistics") & (labels_df["event_type"] != "implausible_weight")])
    m_q_test = evaluate_events(wait_ev, q_labels, labels_from_frame(labels_df), (SPLIT_TS, WINDOW_END), tol_h=6, key_match=False)
    m_q_train = evaluate_events(wait_ev, q_labels, labels_from_frame(labels_df), (WINDOW_START, SPLIT_TS), tol_h=6, key_match=False)

    def brief(m):
        return {k: m[k] for k in ("events", "true_positive_events", "precision", "recall", "false_positives_per_day", "median_latency_h",
                                  "target_labels")}

    # ---- sustained queue anomaly (the only logistics detector that raises ALERTS): trucks passing the training P99 wait
    # while still unweighed, counted per hour at the moment they pass it (causal), rolling 3 h sum.
    exc_t = (long["arrival_ts"] + pd.Timedelta(minutes=wait_p99)).dt.floor("h")
    idx = pd.date_range(WINDOW_START, WINDOW_END, freq="h", inclusive="left")
    q_raw = exc_t.value_counts().reindex(idx, fill_value=0).astype(float).rolling(3, min_periods=1).sum()
    all_lb = labels_from_frame(labels_df)
    grid = []
    for k in (2, 3, 4, 5, 6, 8, 10):
        ev = extract_events(q_raw, k, min_len=1, merge_gap_h=3)
        m = evaluate_events(ev, q_labels, all_lb, (WINDOW_START, SPLIT_TS), tol_h=6, key_match=False)
        grid.append({"k_trucks_3h": k, "events": m["events"], "false_positives_per_day": m["false_positives_per_day"]})
    # the training period contains no queue-episode label, so k is set by a false-alarm budget (<= 1 per 30 days) on train
    k_sel = min((g for g in grid if (g["false_positives_per_day"] or 0) <= 1 / 30), key=lambda g: g["k_trucks_3h"])["k_trucks_3h"]
    q_events = extract_events(q_raw, k_sel, min_len=1, merge_gap_h=3)
    m_qw_test = evaluate_events(q_events, q_labels, all_lb, (SPLIT_TS, WINDOW_END), tol_h=6, key_match=False)
    m_qw_train = evaluate_events(q_events, q_labels, all_lb, (WINDOW_START, SPLIT_TS), tol_h=6, key_match=False)
    normal_day = (pd.Timestamp("2026-10-20 17:00", tz="UTC"), pd.Timestamp("2026-10-21 17:00", tz="UTC"))
    congestion = (pd.Timestamp("2026-11-11 17:00", tz="UTC"), pd.Timestamp("2026-11-15 17:00", tz="UTC"))
    window_check = {
        "normal_day_alerts": sum(1 for e in q_events if normal_day[0] <= e.detected_at < normal_day[1]),
        "truck_queue_congestion_alerts": sum(1 for e in q_events if congestion[0] <= e.detected_at < congestion[1]),
        "first_congestion_alert": next((e.detected_at.isoformat() for e in q_events if congestion[0] <= e.detected_at < congestion[1]), None),
    }

    res = ModelResult(
        name="logistics_anomaly", task="anomaly", algorithm="Per-class weight envelope (train P99.5 x factor) + wait > train P99",
        features=["net_kg", "truck_type", "wait_min"], beats_baseline=None,
        metrics={"weight_factor": factor, "weight_envelope_kg": {k: r4(v) for k, v in env.items()}, "wait_p99_min": r4(wait_p99),
                 "weight_tuning_train": rows, "weight_flags": {"train_in_sample": brief(m_w_train), "test": brief(m_w_test)},
                 "wait_flags": {"train": brief(m_q_train), "test": brief(m_q_test), "raises_alerts": False,
                                "per_label_test": m_q_test["per_label"]},
                 "queue_window_alerts": {"rule": f">= {k_sel} trucks passing the training P99 wait ({wait_p99:.1f} min) within 3 h",
                                         "tuning_grid_train": grid, "train": brief(m_qw_train), "test": brief(m_qw_test),
                                         "per_label_test": m_qw_test["per_label"], "window_check": window_check},
                 "caveat": "All 3 injected implausible-weight labels are in the training period: test-period weight recall is undefined; "
                           "the test period only measures false flags. Flags mean 'unusual, needs review', never wrongdoing."},
        train_window=(WINDOW_START, SPLIT_TS), test_window=(SPLIT_TS, WINDOW_END), artifact={"envelope": env, "factor": factor, "wait_p99": wait_p99},
        headline=[{"name": "queue_alert_recall_test", "model": m_qw_test["recall"], "baseline": None, "baseline_name": None,
                   "better_is": "higher"},
                  {"name": "queue_alert_false_positives_per_day_test", "model": m_qw_test["false_positives_per_day"], "baseline": None,
                   "baseline_name": None, "better_is": "lower"},
                  {"name": "weight_flag_false_positives_per_day_test", "model": m_w_test["false_positives_per_day"], "baseline": None,
                   "baseline_name": None, "better_is": "lower"},
                  {"name": "wait_flag_recall_test", "model": m_q_test["recall"], "baseline": None, "baseline_name": None, "better_is": "higher"}],
    )
    return res, {"weight_events": wev, "wait_events": wait_ev, "queue_events": q_events, "queue_k": k_sel, "queue_raw": q_raw}


def _merge(evs: list[Event], gap: pd.Timedelta) -> list[Event]:
    """Merge per-truck wait flags into congestion episodes (one review item per episode)."""
    out: list[Event] = []
    for e in evs:
        if out and e.detected_at - out[-1].end <= gap:
            o = out[-1]
            o.end = max(o.end, e.end)
            o.info["trucks"].append(e.info["truck_trip_id"])
            if e.peak_raw > o.peak_raw:
                o.peak_raw, o.peak_ts = e.peak_raw, e.peak_ts
                o.info["max_wait_min"] = e.info["wait_min"]
        else:
            e.info = {"flag": "wait", "p99_min": e.info["p99_min"], "trucks": [e.info["truck_trip_id"]], "max_wait_min": e.info["wait_min"]}
            out.append(e)
    return out
