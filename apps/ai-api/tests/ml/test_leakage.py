"""Leakage guards: forbidden features, time split, causal features/baselines."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.ml import energy, logistics, oer
from app.ml.common import FORBIDDEN_FEATURE_TOKENS, SPLIT_TS, WINDOW_START, assert_no_forbidden, ro_connect
from app.ml.data import delivery_quality_features
from app.ml.events import expanding_robust_stats, walk_forward
from tests.ml.conftest import needs_ml_db


def test_split_is_2026_10_15_local_midnight():
    assert SPLIT_TS.tz_convert("Asia/Bangkok") == pd.Timestamp("2026-10-15 00:00", tz="Asia/Bangkok")


@pytest.mark.parametrize("features", [oer.FEATURES, energy.FEATURES, logistics.Q_FEATURES, logistics.A_FEATURES])
def test_feature_lists_have_no_forbidden_columns(features):
    assert_no_forbidden(features)
    for f in features:
        assert not any(t in f.lower() for t in FORBIDDEN_FEATURE_TOKENS), f


def test_only_the_lagged_level_is_an_allowed_target_derived_feature():
    derived = [f for f in oer.LEVEL_FEATURES if any(t in f.lower() for t in FORBIDDEN_FEATURE_TOKENS)]
    assert derived == [oer.LAG_LEVEL]
    with pytest.raises(ValueError):
        assert_no_forbidden(["oer_pct"])
    with pytest.raises(ValueError):
        assert_no_forbidden(["oil_loss_total_pct"])


def test_no_feature_builder_reads_injected_events():
    import inspect

    from app.ml import production, service

    for mod in (oer, production, energy, logistics, service):
        src = inspect.getsource(mod)
        assert "from injected_events" not in src.lower(), mod.__name__
        assert "load_labels" not in src, mod.__name__


def test_delivery_features_use_only_past_hours():
    idx = pd.date_range("2026-08-01", periods=6, freq="h", tz="UTC")
    d = pd.DataFrame({"ts": idx + pd.Timedelta(minutes=10), "net_kg": [1000] * 6, "unripe_pct": [1, 1, 1, 50, 1, 1],
                      "harvest_to_mill_h": [10] * 6})
    f = delivery_quality_features(d, idx, window_h=12)
    assert f.loc[idx[3], "recv_unripe_pct_12h"] == pytest.approx(1.0)  # the hour-3 spike is not visible at hour 3
    assert f.loc[idx[4], "recv_unripe_pct_12h"] > 1.0


def test_expanding_baseline_ignores_future_values():
    idx = pd.date_range(WINDOW_START, periods=24 * 30, freq="h")
    x = pd.Series(np.random.default_rng(0).normal(size=len(idx)), index=idx)
    y = x.copy()
    y.iloc[24 * 20 :] += 100  # change the future
    m1, s1 = expanding_robust_stats(x)
    m2, s2 = expanding_robust_stats(y)
    cut = 24 * 20
    pd.testing.assert_series_equal(m1.iloc[:cut], m2.iloc[:cut])
    pd.testing.assert_series_equal(s1.iloc[:cut], s2.iloc[:cut])


def test_walk_forward_trains_strictly_before_each_block():
    idx = pd.date_range(WINDOW_START, periods=24 * 60, freq="h")
    seen = []

    def fp(tr, bl):
        assert idx[tr].max() < idx[bl].min()
        seen.append(1)
        return np.zeros(bl.sum())

    walk_forward(idx, fp)
    assert len(seen) > 3


@needs_ml_db
def test_oer_features_do_not_change_when_future_rows_are_removed(ml_url):
    con = ro_connect(ml_url)
    end = pd.Timestamp("2026-10-20 12:00", tz="UTC")
    full = oer.build_frame(con, start="2026-10-10 00:00:00", end="2026-10-25 00:00:00")
    cut = oer.build_frame(con, start="2026-10-10 00:00:00", end=end.strftime("%Y-%m-%d %H:%M:%S"))
    cols = oer.FEATURES + oer.DELTAS + [oer.LAG_LEVEL, "bl_persistence", "bl_rolling_24"]
    a = full.loc[full.index <= end, cols]
    b = cut.loc[cut.index <= end, cols]
    pd.testing.assert_frame_equal(a, b)
