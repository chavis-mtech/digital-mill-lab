"""AI-B01 at shift (8 h) and calendar-day granularity + the 'expected OER given current conditions' nowcast (owner: ml).

Same temporal split and leakage rules as app.ml.oer: features are FFB-weighted means of the observable drivers over the
block (no OER/KER/CPO/oil-loss column, no labels); baselines use only OER of earlier blocks. Model choice per
granularity = lowest mean MAE over 3 expanding-window folds inside the training period; the test period is scored once.

Nowcast ("expected OER given current conditions"): standardised Ridge on drivers only (no lagged OER), so the
prediction decomposes exactly into per-driver contributions vs average training conditions; residual = actual -
expected with a split-conformal band. Out-of-sample residuals for the whole timeline come from weekly walk-forward refits.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.common import SEED, SPLIT_TS, assert_no_forbidden, mae, r4, rmse
from app.ml.events import weekly_boundaries
from app.ml.oer import LABELS

DRIVERS = ["ffb_ripe_pct", "recv_unripe_pct_12h", "recv_harvest_to_mill_h_12h", "avg_wait_to_process_h", "sterilizer_cycle_min",
           "steam_pressure_bar", "digester_temp_c", "clarifier_temp_c", "press_vib_max", "press_cur_max", "press_cone_pressure_bar",
           "throughput_tph"]
assert_no_forbidden(DRIVERS)
GRANULARITIES = {"hour": None, "shift_8h": 8, "day": 24}
MIN_FFB_T = {"shift_8h": 150.0, "day": 400.0}
LAGS = {"shift_8h": {"prev": 1, "same_yesterday": 3, "roll": 21}, "day": {"prev": 1, "same_yesterday": 1, "roll": 7}}
ALPHA = 0.10


def make_ridge(alpha: float = 3.0):
    return make_pipeline(StandardScaler(), Ridge(alpha=alpha))


def make_hgb() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_leaf_nodes=7, min_samples_leaf=8, early_stopping=False,
                                         random_state=SEED)


def aggregate(df: pd.DataFrame, gran: str) -> pd.DataFrame:
    """FFB-weighted block means of OER and drivers over running hours. Index = block start (UTC)."""
    d = df[df["is_model_row"]].dropna(subset=DRIVERS + ["oer_pct"]).copy()
    loc = d.index + pd.Timedelta(hours=7)
    hrs = GRANULARITIES[gran]
    start_local = loc.floor("D") + pd.to_timedelta((loc.hour // hrs) * hrs, unit="h")
    d["block"] = start_local - pd.Timedelta(hours=7)
    w = d["ffb_processed_t"]
    cols = DRIVERS + ["oer_pct"]
    num = d[cols].mul(w, axis=0).groupby(d["block"]).sum()
    agg = num.div(w.groupby(d["block"]).sum(), axis=0)
    agg["ffb_t"] = w.groupby(d["block"]).sum()
    agg["running_h"] = d.groupby("block").size()
    agg = agg[agg["ffb_t"] >= MIN_FFB_T[gran]].sort_index()
    lg = LAGS[gran]
    y = agg["oer_pct"]
    agg["bl_previous_block"] = y.shift(lg["prev"])
    agg["bl_same_block_yesterday"] = y.shift(lg["same_yesterday"])
    agg["bl_rolling_7d"] = y.rolling(lg["roll"], min_periods=max(3, lg["roll"] // 2)).mean().shift(1)
    return agg.dropna(subset=["bl_previous_block", "bl_same_block_yesterday", "bl_rolling_7d"])


CANDS = {
    "ridge_drivers": (make_ridge, False),
    "hgb_drivers": (make_hgb, False),
    "ridge_level_plus_drivers": (make_ridge, True),  # target = OER - rolling-7d level (lagged), drivers as features
}
BASELINES = ("bl_previous_block", "bl_same_block_yesterday", "bl_rolling_7d", "train_mean")


def _fit_predict(name: str, tr: pd.DataFrame, te: pd.DataFrame) -> np.ndarray:
    mk, resid = CANDS[name]
    y = tr["oer_pct"] - (tr["bl_rolling_7d"] if resid else 0)
    p = mk().fit(tr[DRIVERS], y).predict(te[DRIVERS])
    return p + (te["bl_rolling_7d"].to_numpy() if resid else 0)


def evaluate_granularity(df: pd.DataFrame, gran: str) -> dict:
    a = aggregate(df, gran)
    tr, te = a[a.index < SPLIT_TS], a[a.index >= SPLIT_TS]
    folds = []
    for k in (3, 2, 1):
        v_end = SPLIT_TS - pd.Timedelta(days=14 * (k - 1))
        v_start = v_end - pd.Timedelta(days=14)
        f_tr, f_va = tr[tr.index < v_start], tr[(tr.index >= v_start) & (tr.index < v_end)]
        row = {name: mae(f_va["oer_pct"], _fit_predict(name, f_tr, f_va)) for name in CANDS}
        for b in BASELINES:
            pb = np.full(len(f_va), f_tr["oer_pct"].mean()) if b == "train_mean" else f_va[b]
            row[b] = mae(f_va["oer_pct"], pb)
        folds.append(row)
    cv = {k: r4(float(np.mean([f[k] for f in folds]))) for k in folds[0]}
    served = min(CANDS, key=lambda k: cv[k])
    best_bl_cv = min(BASELINES, key=lambda k: cv[k])
    test = {}
    for name in CANDS:
        p = _fit_predict(name, tr, te)
        test[name] = {"mae": r4(mae(te["oer_pct"], p)), "rmse": r4(rmse(te["oer_pct"], p))}
    for b in BASELINES:
        pb = np.full(len(te), tr["oer_pct"].mean()) if b == "train_mean" else te[b]
        test[b] = {"mae": r4(mae(te["oer_pct"], pb)), "rmse": r4(rmse(te["oer_pct"], pb))}
    best_bl = min(BASELINES, key=lambda k: test[k]["mae"])
    return {"granularity": gran, "blocks": {"train": len(tr), "test": len(te)}, "target_sd_test": r4(float(te["oer_pct"].std())),
            "cv_mean_mae": cv, "selected_by_cv": served, "best_baseline_cv": best_bl_cv, "test": test, "best_baseline_test": best_bl,
            "beats_best_baseline": bool(test[served]["mae"] < test[best_bl]["mae"]),
            "beats_cv_selected_baseline": bool(test[served]["mae"] < test[best_bl_cv]["mae"])}


# ---------------------------------------------------------------------------- nowcast (expected OER given current conditions)
def fit_nowcast(blocks: pd.DataFrame):
    return make_ridge().fit(blocks[DRIVERS], blocks["oer_pct"])


def contributions(model, x: pd.Series) -> tuple[float, float, list[dict]]:
    """Exact decomposition of a standardised Ridge prediction: intercept(at mean conditions) + sum(coef * z)."""
    sc, rg = model.named_steps["standardscaler"], model.named_steps["ridge"]
    z = (x[DRIVERS].astype(float).to_numpy() - sc.mean_) / sc.scale_
    c = rg.coef_ * z
    base = float(rg.intercept_)
    out = [{"feature": f, "label": LABELS.get(f, f), "value": round(float(x[f]), 4), "typical": round(float(m), 4),
            "contribution": round(float(v), 4)} for f, m, v in zip(DRIVERS, sc.mean_, c, strict=True)]
    return base, base + float(c.sum()), sorted(out, key=lambda r: -abs(r["contribution"]))


def nowcast_study(df: pd.DataFrame, gran: str = "day") -> tuple[dict, dict]:
    """Walk-forward residuals over the timeline, conformal band from training residuals, OER_DEGRADATION explanation."""
    a = aggregate(df, gran)
    pred = pd.Series(np.nan, index=a.index)
    bounds = weekly_boundaries(warmup_days=28)
    for i, b in enumerate(bounds):
        e = bounds[i + 1] if i + 1 < len(bounds) else a.index.max() + pd.Timedelta(days=1)
        trm, blm = a.index < b, (a.index >= b) & (a.index < e)
        if blm.sum() and trm.sum() >= 10:
            pred[blm] = fit_nowcast(a[trm]).predict(a.loc[blm, DRIVERS])
    resid = a["oer_pct"] - pred
    tr_res = resid[(resid.index < SPLIT_TS)].dropna()
    n = len(tr_res)
    q = float(np.quantile(np.abs(tr_res), min(1.0, np.ceil((n + 1) * (1 - ALPHA)) / n)))
    te_res = resid[resid.index >= SPLIT_TS].dropna()
    final = fit_nowcast(a[a.index < SPLIT_TS])
    # OER_DEGRADATION focus day (2026-10-02 local): model fitted only on blocks before that week (walk-forward)
    focus = pd.Timestamp("2026-10-01 17:00", tz="UTC")
    wk = max(b for b in bounds if b <= focus)
    m_f = fit_nowcast(a[a.index < wk])
    row = a.loc[a.index[(a.index >= focus) & (a.index < focus + pd.Timedelta(days=1))][0]] if gran == "day" else None
    expl = None
    if row is not None:
        base, p, contrib = contributions(m_f, row)
        expl = {"day_local": "2026-10-02", "actual_oer_pct": r4(float(row["oer_pct"])), "expected_oer_pct": r4(p),
                "typical_conditions_oer_pct": r4(base), "residual_pp": r4(float(row["oer_pct"]) - p), "top_contributions": contrib[:6],
                "model_fitted_before": str(wk), "basis": "out-of-sample (walk-forward: fitted only on blocks before that week)"}
        b2, p2, c2 = contributions(final, row)
        expl_in = {"expected_oer_pct": r4(p2), "residual_pp": r4(float(row["oer_pct"]) - p2), "top_contributions": c2[:6],
                   "basis": "IN-SAMPLE (model fitted on the whole training period, which contains this episode) - shows what the "
                            "model learned after seeing it, not a prediction"}
        expl["in_sample_view"] = expl_in
    study = {"granularity": gran, "model": "ridge on standardised drivers (no lagged OER)", "drivers": DRIVERS,
             "residual_band_pp_90": r4(q), "train_walk_forward_residual_mae": r4(float(np.abs(tr_res).mean())),
             "test_walk_forward_residual_mae": r4(float(np.abs(te_res).mean())),
             "test_residual_band_coverage": r4(float(np.mean(np.abs(te_res) <= q))),
             "oer_degradation_explanation": expl}
    return study, {"model": final, "residual_band": q, "granularity": gran, "drivers": DRIVERS}
