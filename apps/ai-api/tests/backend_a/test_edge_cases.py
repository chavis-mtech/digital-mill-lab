"""Hand-built fixtures / pure functions: no seeded DB needed."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from app.errors import ApiError
from app.services.kpi_common import kpi_value, oer_status, period_windows, safe_div
from app.services.kpi_health import sensor_state, worst
from app.services.logistics_sim import simulate
from tests.backend_a.conftest import ctx_at
from tests.conftest import make_settings

S = make_settings()


def test_sensor_state_shared_rule():
    assert sensor_state(2.0, 2.8, 4.5, False) == "normal"
    assert sensor_state(2.8, 2.8, 4.5, False) == "warning"
    assert sensor_state(4.5, 2.8, 4.5, False) == "critical"
    assert sensor_state(86, 85, 80, True) == "normal"
    assert sensor_state(85, 85, 80, True) == "warning"
    assert sensor_state(79, 85, 80, True) == "critical"
    assert sensor_state(None, 1, 2, False) is None and sensor_state(1.0, None, None, False) is None
    assert worst(["normal", "maintenance_required", "warning"]) == "maintenance_required"
    assert worst(["critical", "maintenance_required"]) == "critical"


def test_period_windows():
    ctx = ctx_at(S, "2026-10-02T16:00")
    cur, prev = period_windows(ctx, "today")
    assert cur.end == ctx.as_of and (cur.end - cur.start).total_seconds() == 16 * 3600
    assert (cur.start - prev.start).days == 1 and (prev.end - prev.start) == (cur.end - cur.start)
    cur7, prev7 = period_windows(ctx, "7d")
    assert (cur7.start - prev7.start).days == 7
    first = ctx_at(S, "2026-07-24T10:00")
    _, p = period_windows(first, "today")
    assert p is None  # previous day is before the dataset
    with pytest.raises(ApiError):
        period_windows(ctx, "custom", date(2026, 10, 5), date(2026, 10, 1))


def test_null_not_zero_on_missing_denominator():
    assert safe_div(5, 0) is None and safe_div(None, 3) is None
    k = kpi_value(ctx_at(S), "oer_pct", "OER", None, "%", "x", previous=18.0)
    assert k["value"] is None and k["delta"] is None and k["provenance"]["kind"] == "synthetic_actual"


def test_oer_status_thresholds():
    assert oer_status(18.4, 18.5) is None
    assert oer_status(18.0, 18.5) == "medium"
    assert oer_status(17.5, 18.5) == "high"


def _draws(n):
    return {k: np.ones(n) for k in ("m_w1", "m_g", "m_u", "m_w2")} | {"gate": np.zeros(n)}


def test_simulate_single_truck_exact_times():
    r = simulate(np.array([0.0]), np.array([10.0]), _draws(1), weighbridges=1, ramps=1)
    # weigh 2 + grade 4 + unload (3 + 10) + weigh 2 + exit 1 = 22
    assert r["weigh_in_start"][0] == 0 and r["exit"][0] == pytest.approx(22.0)


def test_simulate_fifo_queue_and_outage():
    n = 3
    r = simulate(np.zeros(n), np.full(n, 1.0), _draws(n), weighbridges=1, ramps=3)
    assert sorted(r["weigh_in_start"]) == [0.0, 2.0, 4.0]  # one bridge, 2 min each, weigh-ins served FIFO
    out = simulate(np.zeros(1), np.ones(1), _draws(1), weighbridges=1, ramps=1, outages={"bridge": [(0.0, 30.0)]})
    assert out["weigh_in_start"][0] == pytest.approx(30.0)  # bridge unavailable until the outage ends


def test_simulate_ramp_space_blocks_unloading():
    space = {"t": np.array([0.0, 1000.0]), "cum": np.array([0.0, 0.0]), "stock0": 595.0, "cap": 600.0}
    r = simulate(np.zeros(1), np.array([10.0]), _draws(1), weighbridges=1, ramps=1, ramp_space=space)
    assert np.isnan(r["exit"][0])  # ramp full and never drained -> truck cannot unload
    space["cum"] = np.array([0.0, 100.0])  # mill processes 0.1 t/min
    r = simulate(np.zeros(1), np.array([10.0]), _draws(1), weighbridges=1, ramps=1, ramp_space=space)
    assert r["exit"][0] > 22.0
