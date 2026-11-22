"""Shared ML constants and helpers (owner: ml).

Honesty rules encoded here:
- SPLIT_TS is the single temporal split (train < 2026-10-15 00:00 Asia/Bangkok, test >= it), per docs/DATA_GENERATION.md.
- FORBIDDEN_FEATURE_TOKENS lists columns that must never be model inputs (targets, outputs derived from the target,
  ground-truth labels). tests/ml/test_leakage.py asserts every model's feature list avoids them.
- `injected_events` is read ONLY by app/ml/evaluation code paths (labels), never by feature builders or the API.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.config import REPO_ROOT

SEED = 20261120
MODELS_DIR = REPO_ROOT / "data" / "models"
MODEL_VERSION = "1.0.0"

LOCAL_OFFSET = timedelta(hours=7)  # Asia/Bangkok has no DST
SPLIT_TS = pd.Timestamp("2026-10-14 17:00:00", tz="UTC")  # = 2026-10-15 00:00 local
WINDOW_START = pd.Timestamp("2026-07-23 17:00:00", tz="UTC")
WINDOW_END = pd.Timestamp("2026-11-20 17:00:00", tz="UTC")

# Columns / tokens that must never appear in a feature list (target leakage or ground truth).
FORBIDDEN_FEATURE_TOKENS = (
    "oer",
    "ker",
    "cpo_t",
    "kernel_t",
    "oil_loss",
    "injected",
    "scenario",
    "label",
)

MODEL_NAMES = (
    "oer_forecast",
    "production_anomaly",
    "equipment_anomaly",
    "energy_forecast",
    "energy_anomaly",
    "queue_time",
    "arrival_forecast",
    "logistics_anomaly",
)


def assert_no_forbidden(features: list[str], allow: tuple[str, ...] = ()) -> None:
    """Raise if a feature name contains a forbidden token (allow-list for explicitly time-lagged target features)."""
    for f in features:
        if f in allow:
            continue
        low = f.lower()
        for tok in FORBIDDEN_FEATURE_TOKENS:
            if tok in low:
                raise ValueError(f"forbidden feature {f!r} (token {tok!r})")


# ---------------------------------------------------------------------------- DB access
def sqlite_path(database_url: str) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError("the ML pipeline supports SQLite DATABASE_URLs only in this demo")
    return Path(database_url[len(prefix) :])


def ro_connect(database_url: str) -> sqlite3.Connection:
    """Read-only SQLite connection (training and evaluation never write to the source DB)."""
    path = sqlite_path(database_url)
    if not path.exists():
        raise FileNotFoundError(path)
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def read_sql(con: sqlite3.Connection, sql: str, ts_cols: tuple[str, ...] = ("ts",), params: tuple = ()) -> pd.DataFrame:
    df = pd.read_sql_query(sql, con, params=params)
    for c in ts_cols:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], utc=True, format="mixed")
    return df


def to_local(ts: pd.Series | pd.DatetimeIndex) -> Any:
    return ts + pd.Timedelta(hours=7)


def utc_dt(ts: pd.Timestamp | datetime | None) -> datetime | None:
    if ts is None or (isinstance(ts, float) and np.isnan(ts)) or ts is pd.NaT:
        return None
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return t.tz_convert("UTC").floor("us").to_pydatetime()


def db_fingerprint(con: sqlite3.Connection) -> str:
    """Cheap fingerprint of the source data (row counts + last timestamps) stored with each model."""
    parts = []
    for t, c in (("process_hourly", "ts"), ("sensor_readings", "ts"), ("truck_trips", "arrival_ts"), ("energy_consumption", "ts")):
        n, mx = con.execute(f"SELECT COUNT(*), MAX({c}) FROM {t}").fetchone()  # noqa: S608 - constant table names
        parts.append(f"{t}:{n}:{mx}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------- metrics
def mae(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean(np.abs(np.asarray(y) - np.asarray(p))))


def rmse(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.sqrt(np.mean((np.asarray(y) - np.asarray(p)) ** 2)))


def r4(x: float | None) -> float | None:
    if x is None:
        return None
    try:
        if np.isnan(x):
            return None
    except TypeError:
        return x
    return round(float(x), 4)


# ---------------------------------------------------------------------------- results container
@dataclass
class ModelResult:
    name: str
    task: str  # regression | anomaly | forecast | classification
    algorithm: str
    features: list[str]
    metrics: dict[str, Any]
    beats_baseline: bool | None
    train_window: tuple[pd.Timestamp, pd.Timestamp]
    test_window: tuple[pd.Timestamp, pd.Timestamp]
    artifact: dict[str, Any] = field(default_factory=dict)  # objects persisted with joblib
    headline: list[dict[str, Any]] = field(default_factory=list)  # [{name, model, baseline, baseline_name, better_is}]

    @property
    def dir(self) -> Path:
        return MODELS_DIR / self.name / MODEL_VERSION

    def save(self) -> Path:
        import joblib  # noqa: PLC0415

        self.dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.artifact, self.dir / "model.joblib", compress=3)
        meta = {
            "name": self.name,
            "version": MODEL_VERSION,
            "task": self.task,
            "algorithm": self.algorithm,
            "features": self.features,
            "beats_baseline": self.beats_baseline,
            "train_window": [str(self.train_window[0]), str(self.train_window[1])],
            "test_window": [str(self.test_window[0]), str(self.test_window[1])],
            "headline": self.headline,
            "metrics": self.metrics,
            "seed": SEED,
        }
        (self.dir / "metrics.json").write_text(json.dumps(meta, indent=2, default=_json_default) + "\n")
        return self.dir


def _json_default(o: Any) -> Any:
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, (pd.Timestamp, datetime)):
        return o.isoformat()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def load_metrics(name: str) -> dict[str, Any] | None:
    p = MODELS_DIR / name / MODEL_VERSION / "metrics.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def now_utc() -> datetime:
    return datetime.now(UTC)
