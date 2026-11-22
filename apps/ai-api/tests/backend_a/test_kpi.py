"""KPI services against the real seeded DB (read-only): reconciliation with direct SQL, as_of wall, provenance,
scenario contrasts computed from data."""

from __future__ import annotations

import sqlite3

import pytest

from app.services import kpi
from app.services.kpi_common import period_windows
from tests.backend_a.conftest import DEMO_DB, FOCUS, ctx_at, needs_db

pytestmark = needs_db


def _sql(q: str, *args):
    con = sqlite3.connect(f"file:{DEMO_DB}?mode=ro", uri=True)
    try:
        return con.execute(q, args).fetchone()
    finally:
        con.close()


def _kpis(demo_db, demo_settings, as_of=None, period="today"):
    r = kpi.executive_kpis(demo_db, ctx_at(demo_settings, as_of), period)
    return {k["key"]: k for k in r["kpis"]}, r


def test_twelve_kpis_with_provenance(demo_db, demo_settings):
    k, r = _kpis(demo_db, demo_settings)
    assert list(k) == kpi.EXEC_KEYS and len(k) == 12
    for v in k.values():
        assert v["provenance"]["kind"] == "synthetic_actual"
        assert v["provenance"]["source"]
        assert v["provenance"]["as_of"] == demo_settings.default_as_of
    assert r["period_end"] == demo_settings.default_as_of


def test_oer_reconciles_with_direct_sql_ratio_of_sums(demo_db, demo_settings):
    ctx = ctx_at(demo_settings)
    cur, _ = period_windows(ctx, "7d")
    k, _ = _kpis(demo_db, demo_settings, period="7d")
    fmt = "%Y-%m-%d %H:%M:%S.%f"
    lo = cur.start.strftime(fmt)
    hi = cur.end.strftime(fmt)
    cpo, ffb, ker = _sql(
        "select sum(cpo_t), sum(ffb_processed_t), sum(kernel_t) from process_hourly where ts >= ? and datetime(ts, '+1 hour') <= datetime(?)", lo, hi
    )
    assert k["ffb_processed_t"]["value"] == pytest.approx(ffb, abs=1e-2)
    assert k["oer_pct"]["value"] == pytest.approx(cpo / ffb * 100, abs=1e-3)
    assert k["ker_pct"]["value"] == pytest.approx(ker / ffb * 100, abs=1e-3)
    # not the mean of daily ratios
    acc = _sql("select sum(accepted_kg)/1000.0 from ffb_deliveries where received_ts >= ? and received_ts <= ?", lo, hi)[0]
    assert k["ffb_received_t"]["value"] == pytest.approx(acc, abs=1e-2)


def test_window_sum_equals_sum_of_days(demo_db, demo_settings):
    ctx = ctx_at(demo_settings)
    s = kpi.kpi_series(demo_db, ctx, "ffb_processed_t", "7d", "day", False)
    total = sum(p["v"] for p in s["series"][0]["points"] if p["v"] is not None)
    k, _ = _kpis(demo_db, demo_settings, period="7d")
    assert total == pytest.approx(k["ffb_processed_t"]["value"], rel=1e-6)


def test_as_of_never_leaks_future_rows(demo_db, demo_settings):
    """KPIs at as_of must equal KPIs computed after deleting nothing - i.e. moving as_of forward changes them,
    and a window ending at as_of ignores the (complete) hour that starts at as_of."""
    a = "2026-10-02T12:00"
    k1, r1 = _kpis(demo_db, demo_settings, a)
    k2, _ = _kpis(demo_db, demo_settings, "2026-10-02T12:59")  # same complete hours (11:00 is the last complete)
    assert k1["ffb_processed_t"]["value"] == k2["ffb_processed_t"]["value"]
    k3, _ = _kpis(demo_db, demo_settings, "2026-10-02T13:00")
    assert k3["ffb_processed_t"]["value"] >= k1["ffb_processed_t"]["value"]
    # series points never later than as_of
    s = kpi.kpi_series(demo_db, ctx_at(demo_settings, a), "oer_pct", "today", "hour", False)
    assert all(p["t"] < r1["period_end"] for p in s["series"][0]["points"])


def test_scenario_contrasts_computed(demo_db, demo_settings):
    normal, _ = _kpis(demo_db, demo_settings, FOCUS["NORMAL_DAY"])
    oer_deg, _ = _kpis(demo_db, demo_settings, FOCUS["OER_DEGRADATION"])
    assert oer_deg["oer_pct"]["value"] < normal["oer_pct"]["value"] - 0.5
    assert oer_deg["oer_pct"]["status"] in ("medium", "high")
    press, _ = _kpis(demo_db, demo_settings, FOCUS["PRESS_VIBRATION_ANOMALY"])
    assert press["active_maintenance_alerts"]["value"] >= 1 and press["active_maintenance_alerts"]["status"] in ("medium", "high")
    assert normal["active_maintenance_alerts"]["value"] == 0


def test_scenario_comparison_omits_future_scenarios(demo_db, demo_settings):
    r = kpi.scenario_comparison(demo_db, ctx_at(demo_settings, "2026-10-25T12:00"))
    codes = {row["scenario_code"] for row in r["rows"]}
    assert "NORMAL_DAY" in codes and "OER_DEGRADATION" in codes
    assert "TRUCK_QUEUE_CONGESTION" not in codes and "PRESS_VIBRATION_ANOMALY" not in codes


def test_custom_period_validation(demo_db, demo_settings):
    from app.errors import ApiError

    with pytest.raises(ApiError):
        kpi.executive_kpis(demo_db, ctx_at(demo_settings), "custom")


def test_impact_cards_are_what_if_with_formula(demo_db, demo_settings):
    cards = kpi.impact_cards(demo_db, ctx_at(demo_settings, FOCUS["OER_DEGRADATION"]))
    lost = next(c for c in cards if c["key"] == "lost_cpo_t")
    assert lost["provenance"]["kind"] == "what_if"
    i = lost["formula"]["inputs"]
    assert lost["value"] == pytest.approx(i["ffb_processed_t"] * (i["baseline_oer_pct"] - i["oer_pct"]) / 100, abs=0.02)
    assert lost["value"] > 0
