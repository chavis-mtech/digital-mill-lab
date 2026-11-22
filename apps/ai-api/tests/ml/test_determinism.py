"""Same seed + same data -> same metrics."""

from __future__ import annotations

from app.ml import energy, logistics
from app.ml.common import SPLIT_TS, load_metrics, ro_connect
from app.ml.data import load_energy_plant_hourly, load_process_hourly, load_trucks
from tests.ml.conftest import needs_ml_db


@needs_ml_db
def test_logistics_models_are_deterministic_and_match_saved_metrics(ml_url):
    con = ro_connect(ml_url)
    tr = load_trucks(con)
    q1 = logistics.train_queue(tr)  # same seed -> identical to the metrics saved by `python -m app.ml.train`
    saved = load_metrics("queue_time")["metrics"]["test"]["hgb"]["mae"]
    assert abs(q1.metrics["test"]["hgb"]["mae"] - saved) < 1e-6
    idx = load_process_hourly(con).index
    a1, a2 = logistics.train_arrivals(tr, idx), logistics.train_arrivals(tr, idx)
    assert a1.metrics["test"] == a2.metrics["test"]


@needs_ml_db
def test_energy_forecast_is_deterministic(ml_url):
    """Fit-only part (the walk-forward anomaly refits are covered by the saved-metrics reproduction in evaluate)."""
    con = ro_connect(ml_url)
    df = energy.build_frame(load_process_hourly(con), load_energy_plant_hourly(con))
    tr = df[df.index < SPLIT_TS]
    p1 = energy.make_hgb().fit(tr[energy.FEATURES], tr[energy.TARGET]).predict(tr[energy.FEATURES][:200])
    p2 = energy.make_hgb().fit(tr[energy.FEATURES], tr[energy.TARGET]).predict(tr[energy.FEATURES][:200])
    assert (p1 == p2).all()


@needs_ml_db
def test_saved_oer_metrics_reproduce(ml_url):
    from app.ml.evaluate import reproduce_oer

    r = reproduce_oer(ro_connect(ml_url))
    assert r["match"], r
