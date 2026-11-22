"""Shared anomaly-detection utilities (owner: ml): causal robust baselines, walk-forward fitting, event extraction,
event-level evaluation against ground-truth labels, threshold tuning on the training period only.

Causality contract: a score at hour t uses data with timestamp <= t only; an event's `detected_at` is the end of the
hour in which the persistence rule (k consecutive hours above threshold) was first satisfied.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.ml.common import SPLIT_TS, WINDOW_END, WINDOW_START

LN2 = math.log(2.0)


def score01(raw: np.ndarray | pd.Series, thr: float) -> np.ndarray:
    """Map a non-negative raw score to 0..1 so that raw == threshold -> 0.5 (monotone, saturating)."""
    r = np.clip(np.asarray(raw, dtype=float), 0, None)
    return 1.0 - np.exp(-r / thr * LN2)


def severity_for(score: float) -> str:
    if score >= 0.9:
        return "critical"
    if score >= 0.75:
        return "high"
    return "medium"


# ---------------------------------------------------------------------------- causal robust baselines
def expanding_robust_stats(
    x: pd.Series, guard_days: int = 2, min_days: int = 7, min_n: int = 48, max_history_days: int | None = None
) -> tuple[pd.Series, pd.Series]:
    """Median and scaled MAD per hour, recomputed once per local day from values strictly before (day - guard).

    Expanding window (robust to an anomaly as long as it is < 50 % of history). Returns NaN during warm-up.
    """
    idx = x.index
    vals = x.to_numpy(dtype=float)
    local_day = (idx + pd.Timedelta(hours=7)).floor("D")
    days = local_day.unique()
    med = np.full(len(x), np.nan)
    mad = np.full(len(x), np.nan)
    first = idx[0]
    for d in days:
        cutoff = d - pd.Timedelta(hours=7) - pd.Timedelta(days=guard_days)
        if cutoff - first < pd.Timedelta(days=min_days):
            continue
        lo = cutoff - pd.Timedelta(days=max_history_days) if max_history_days else first
        m = (idx < cutoff) & (idx >= lo)
        h = vals[m]
        h = h[~np.isnan(h)]
        if len(h) < min_n:
            continue
        md = float(np.median(h))
        s = float(np.median(np.abs(h - md))) * 1.4826
        sel = local_day == d
        med[sel] = md
        mad[sel] = s
    return pd.Series(med, idx), pd.Series(mad, idx)


def robust_z(x: pd.Series, med: pd.Series, mad: pd.Series, floor: float) -> pd.Series:
    return (x - med) / np.maximum(mad, floor)


# ---------------------------------------------------------------------------- walk-forward
def weekly_boundaries(start: pd.Timestamp = WINDOW_START, end: pd.Timestamp = WINDOW_END, warmup_days: int = 21) -> list[pd.Timestamp]:
    b = start + pd.Timedelta(days=warmup_days)
    out = []
    while b < end:
        out.append(b)
        b += pd.Timedelta(days=7)
    return out


def walk_forward(
    index: pd.DatetimeIndex,
    fit_predict: Callable[[np.ndarray, np.ndarray], np.ndarray],
    warmup_days: int = 21,
) -> np.ndarray:
    """For each weekly block [b, b+7d): fit on rows with ts < b, predict the block. Returns predictions (NaN in warm-up).

    fit_predict(train_mask, block_mask) -> predictions for block rows.
    """
    pred = np.full(len(index), np.nan)
    bounds = weekly_boundaries(warmup_days=warmup_days)
    for i, b in enumerate(bounds):
        e = bounds[i + 1] if i + 1 < len(bounds) else WINDOW_END + pd.Timedelta(hours=1)
        tr = np.asarray(index < b)
        bl = np.asarray((index >= b) & (index < e))
        if bl.sum() == 0 or tr.sum() < 24:
            continue
        pred[bl] = fit_predict(tr, bl)
    return pred


# ---------------------------------------------------------------------------- events
@dataclass
class Event:
    start: pd.Timestamp
    end: pd.Timestamp  # exclusive (end of last hour above threshold)
    detected_at: pd.Timestamp
    peak_ts: pd.Timestamp
    peak_raw: float
    key: str = ""  # entity key (e.g. equipment code) or ""
    info: dict = field(default_factory=dict)


def extract_events(raw: pd.Series, thr: float, min_len: int = 2, merge_gap_h: int = 3, key: str = "") -> list[Event]:
    """Runs of >= min_len consecutive hourly values >= thr; runs closer than merge_gap_h hours are merged."""
    s = raw.dropna()
    if s.empty:
        return []
    s = s.asfreq("h")  # gaps become NaN (not above)
    above = (s >= thr).to_numpy()
    ts = s.index
    runs: list[tuple[int, int]] = []
    i, n = 0, len(above)
    while i < n:
        if above[i]:
            j = i
            while j + 1 < n and above[j + 1]:
                j += 1
            runs.append((i, j))
            i = j + 1
        else:
            i += 1
    events: list[Event] = []
    for a, b in runs:
        if b - a + 1 < min_len:
            # a short blip can still extend an existing event if it is close
            if events and (ts[a] - events[-1].end) <= pd.Timedelta(hours=merge_gap_h):
                _extend(events[-1], s, a, b)
            continue
        if events and (ts[a] - events[-1].end) <= pd.Timedelta(hours=merge_gap_h):
            _extend(events[-1], s, a, b)
            continue
        seg = s.iloc[a : b + 1]
        events.append(
            Event(
                start=ts[a],
                end=ts[b] + pd.Timedelta(hours=1),
                detected_at=ts[a + min_len - 1] + pd.Timedelta(hours=1),
                peak_ts=seg.idxmax(),
                peak_raw=float(seg.max()),
                key=key,
            )
        )
    return events


def _extend(ev: Event, s: pd.Series, a: int, b: int) -> None:
    seg = s.iloc[a : b + 1]
    ev.end = s.index[b] + pd.Timedelta(hours=1)
    if float(seg.max()) > ev.peak_raw:
        ev.peak_raw = float(seg.max())
        ev.peak_ts = seg.idxmax()


# ---------------------------------------------------------------------------- evaluation
@dataclass
class Label:
    code: str
    start: pd.Timestamp
    end: pd.Timestamp
    key: str
    kind: str
    scenario: str | None


def _overlaps(ev: Event, lb: Label, tol: pd.Timedelta, pre_tol: pd.Timedelta) -> bool:
    return ev.start < lb.end + tol and ev.end > lb.start - pre_tol and ev.detected_at >= lb.start - pre_tol


def evaluate_events(
    events: list[Event],
    targets: list[Label],
    abnormal: list[Label],
    period: tuple[pd.Timestamp, pd.Timestamp],
    tol_h: float = 6,
    pre_tol_h: float = 1,
    key_match: bool = True,
) -> dict:
    """Event-level metrics in `period`.

    targets  - labels the detector is *supposed* to find (recall, latency).
    abnormal - all labels that make a detection legitimate (precision); a superset of targets.
    Precision counts detection events (by detected_at in period); recall counts target labels (by start in period).
    """
    p0, p1 = period
    tol, pre = pd.Timedelta(hours=tol_h), pd.Timedelta(hours=pre_tol_h)
    evs = [e for e in events if p0 <= e.detected_at < p1]
    tg = [lb for lb in targets if p0 <= lb.start < p1]

    def match(e: Event, lb: Label) -> bool:
        return (not key_match or lb.key == "" or e.key == "" or e.key == lb.key) and _overlaps(e, lb, tol, pre)

    tp_events = [e for e in evs if any(match(e, lb) for lb in abnormal)]
    fp_events = [e for e in evs if e not in tp_events]
    per_label = []
    for lb in tg:
        hits = sorted((e for e in events if match(e, lb)), key=lambda e: e.detected_at)
        det = hits[0] if hits else None
        latency = None
        if det is not None:
            latency = max(0.0, (det.detected_at - lb.start).total_seconds() / 3600)
        per_label.append(
            {
                "label": lb.code,
                "kind": lb.kind,
                "scenario": lb.scenario,
                "entity": lb.key or None,
                "start": lb.start.isoformat(),
                "end": lb.end.isoformat(),
                "detected": det is not None,
                "detected_at": det.detected_at.isoformat() if det is not None else None,
                "latency_h": round(latency, 2) if latency is not None else None,
            }
        )
    days = (p1 - p0).total_seconds() / 86400
    n_det = sum(1 for r in per_label if r["detected"])
    lat = [r["latency_h"] for r in per_label if r["latency_h"] is not None]
    precision = len(tp_events) / len(evs) if evs else None
    recall = n_det / len(tg) if tg else None
    f1 = None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = 2 * precision * recall / (precision + recall)
    return {
        "period": [p0.isoformat(), p1.isoformat()],
        "days": round(days, 2),
        "events": len(evs),
        "true_positive_events": len(tp_events),
        "false_positive_events": len(fp_events),
        "precision": None if precision is None else round(precision, 4),
        "target_labels": len(tg),
        "detected_labels": n_det,
        "recall": None if recall is None else round(recall, 4),
        "f1": None if f1 is None else round(f1, 4),
        "false_positives_per_day": round(len(fp_events) / days, 4) if days > 0 else None,
        "median_latency_h": round(float(np.median(lat)), 2) if lat else None,
        "per_label": per_label,
    }


def tune_threshold(
    candidates: list[float],
    make_events: Callable[[float], list[Event]],
    targets: list[Label],
    abnormal: list[Label],
    max_fp_per_day: float = 0.25,
    **kw,
) -> tuple[float, list[dict]]:
    """Pick the threshold maximising F1 on the TRAINING period, subject to FP/day <= cap (falls back to min FP/day)."""
    period = (WINDOW_START, SPLIT_TS)
    rows = []
    for thr in candidates:
        m = evaluate_events(make_events(thr), targets, abnormal, period, **kw)
        rows.append({"threshold": round(float(thr), 4), **{k: m[k] for k in ("events", "precision", "recall", "f1", "false_positives_per_day")}})
    ok = [r for r in rows if (r["false_positives_per_day"] or 0) <= max_fp_per_day]
    pool = ok or sorted(rows, key=lambda r: r["false_positives_per_day"] or 0)[:1]
    best = max(pool, key=lambda r: ((r["f1"] or 0), r["threshold"]))
    return float(best["threshold"]), rows


def labels_from_frame(df: pd.DataFrame, key_map: dict[int, str] | None = None, key_col: str = "equipment_id") -> list[Label]:
    out = []
    for r in df.itertuples(index=False):
        key = ""
        if key_map is not None:
            v = getattr(r, key_col)
            if v is not None and not (isinstance(v, float) and np.isnan(v)):
                key = key_map.get(int(v), "")
        scn = r.scenario_code if isinstance(r.scenario_code, str) else None
        out.append(Label(code=r.code, start=r.start_ts, end=r.end_ts, key=key, kind=r.event_type, scenario=scn))
    return out


def per_scenario_table(per_label: list[dict]) -> list[dict]:
    """Aggregate per-label results by scenario (None -> 'background')."""
    groups: dict[str, list[dict]] = {}
    for r in per_label:
        groups.setdefault(r["scenario"] or "background", []).append(r)
    out = []
    for k, rows in sorted(groups.items()):
        lat = [r["latency_h"] for r in rows if r["latency_h"] is not None]
        out.append(
            {
                "scenario": k,
                "labels": len(rows),
                "detected": sum(r["detected"] for r in rows),
                "median_latency_h": round(float(np.median(lat)), 2) if lat else None,
                "kinds": sorted({r["kind"] for r in rows}),
            }
        )
    return out
