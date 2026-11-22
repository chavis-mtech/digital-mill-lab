"""Production, process twin, energy, logistics, queue simulation, insights, reports - real seeded DB (read-only)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import energy, kpi_insights, logistics, logistics_sim, production, production_process
from app.services.kpi_health import equipment_health
from tests.backend_a.conftest import FOCUS, ctx_at, needs_db

pytestmark = needs_db


def test_production_summary_mass_balance(demo_db, demo_settings):
    from datetime import date

    r = production.summary(demo_db, ctx_at(demo_settings), date(2026, 10, 21))
    k = {x["key"]: x for x in r["kpis"]}
    assert k["oer_pct"]["value"] == pytest.approx(k["cpo_t"]["value"] / k["ffb_processed_t"]["value"] * 100, abs=1e-2)
    assert 60 <= r["mass_balance"]["closure_pct"] <= 70  # five outputs ~64% of FFB (DATA_GENERATION)
    assert r["oer_formula"]["result"] == pytest.approx(k["oer_pct"]["value"], abs=1e-3)


def test_losses_components_sum_to_total(demo_db, demo_settings):
    r = production.losses(demo_db, ctx_at(demo_settings, FOCUS["OER_DEGRADATION"]), "today")
    assert sum(c["pct_of_ffb"] for c in r["components"]) == pytest.approx(r["total_loss_pct"], abs=2e-3)
    normal = production.losses(demo_db, ctx_at(demo_settings, FOCUS["NORMAL_DAY"]), "today")
    assert r["total_loss_pct"] > normal["total_loss_pct"]  # OER degradation day loses more oil


def test_oer_trend_band_and_degradation(demo_db, demo_settings):
    r = production.oer_trend(demo_db, ctx_at(demo_settings, "2026-10-04T18:00"), "7d", "day")
    pts = {p["t"].date().isoformat(): p for p in r["expected_band"]["points"]}
    oer = {p["t"].date().isoformat(): p["v"] for p in r["oer"]["points"]}
    day = "2026-10-01"  # UTC 17:00 of 10-01 = mill day 10-02
    assert oer[day] < pts[day]["lower"]  # outside the historical band on the focus day
    assert all(p["lower"] < p["v"] < p["upper"] for p in r["expected_band"]["points"] if p["lower"] is not None)


def test_shifts_and_batches_never_after_as_of(demo_db, demo_settings):
    ctx = ctx_at(demo_settings, "2026-11-14T10:00")
    assert all(s["end_ts"] <= ctx.as_of for s in production.shifts(demo_db, ctx, "7d", 100)["items"])
    assert all(b["end_ts"] <= ctx.as_of for b in production.batches(demo_db, ctx, "today", 100, 0)["items"])


def test_process_twin_consistent_with_health_engine(demo_db, demo_settings):
    ctx = ctx_at(demo_settings, FOCUS["PRESS_VIBRATION_ANOMALY"])
    stages = {s["code"]: s for s in production_process.list_stages(demo_db, ctx)["stages"]}
    health = equipment_health(demo_db, ctx)
    assert stages["PRESSING"]["status"] == "critical"
    d = production_process.stage_detail(demo_db, ctx, "PRESSING")
    prs3 = next(e for e in d["equipment"] if e["code"] == "PRS-03")
    assert prs3["health_state"] == health[prs3["id"]]["state"] == "critical"
    assert stages["PRESSING"]["active_alerts"] >= 1
    normal = {s["code"]: s for s in production_process.list_stages(demo_db, ctx_at(demo_settings, FOCUS["NORMAL_DAY"]))["stages"]}
    assert normal["PRESSING"]["status"] != "critical"


def test_energy_markers_flag_energy_episode_not_normal(demo_db, demo_settings):
    from app.services.kpi_common import Window, local_midnight

    ctx = ctx_at(demo_settings, "2026-09-14T18:00")
    from datetime import date

    w = Window(local_midnight(ctx, date(2026, 9, 7)), ctx.as_of)
    m = energy.daily_markers(demo_db, ctx, w)
    assert sum(1 for x in m if x["abnormal"]) >= 3
    ctxn = ctx_at(demo_settings, "2026-10-21T23:00")
    assert not energy.expected_today(demo_db, ctxn)["abnormal"]


def test_energy_summary_ratios(demo_db, demo_settings):
    r = energy.summary(demo_db, ctx_at(demo_settings), "30d")
    k = {x["key"]: x for x in r["kpis"]}
    assert k["idle_cost_estimate_thb"]["provenance"]["kind"] == "what_if"
    shares = sum(s["share_pct"] for s in r["sources"])
    assert shares == pytest.approx(100, abs=0.5)


def test_energy_what_if_formula(demo_db, demo_settings):
    body = SimpleNamespace(efficiency_improvement_pct=10, idle_reduction_pct=0, grid_import_reduction_pct=0, electricity_tariff_thb_per_kwh=None,
                           biogas_capture=False, days=30)
    r = energy.what_if(demo_db, ctx_at(demo_settings), body)
    inp = r["formulas"][0]["inputs"]
    assert r["scenario_kwh"] == pytest.approx((inp["baseline_kwh"] - inp["idle_kwh"]) * 0.9 + inp["idle_kwh"], rel=1e-4)
    assert r["provenance"]["kind"] == "what_if" and r["limits"]


def test_queue_wait_higher_on_congestion_day(demo_db, demo_settings):
    q = {x["key"]: x["value"] for x in logistics.kpis(demo_db, ctx_at(demo_settings, "2026-11-14T23:30"), "today")["kpis"]}
    n = {x["key"]: x["value"] for x in logistics.kpis(demo_db, ctx_at(demo_settings, "2026-11-05T23:30"), "today")["kpis"]}
    assert q["avg_wait_min"] > 3 * n["avg_wait_min"]
    assert q["avg_turnaround_min"] > n["avg_turnaround_min"]
    now = logistics.queue_now(demo_db, ctx_at(demo_settings, "2026-11-14T12:30"))
    assert now["trucks_waiting"] >= 10
    assert all(t["arrival_ts"] <= now["as_of"] for t in now["trucks"])


def test_tickets_hide_weigh_out_after_as_of(demo_db, demo_settings):
    ctx = ctx_at(demo_settings, "2026-11-14T12:30")
    items = logistics.tickets(demo_db, ctx, "today", None, False, 500, 0)["items"]
    assert items
    for t in items:
        assert t["weigh_in_ts"] <= ctx.as_of
        if t["weigh_out_ts"] is None:
            assert t["net_kg"] is None and t["tare_kg"] is None
        else:
            assert t["weigh_out_ts"] <= ctx.as_of


def test_arrival_pattern_heatmap(demo_db, demo_settings):
    r = logistics.arrival_pattern(demo_db, ctx_at(demo_settings), None, 14)
    assert len(r["by_hour"]["points"]) == 24 and r["heatmap"]
    assert all(0 <= c["weekday"] <= 6 and 0 <= c["hour"] <= 23 for c in r["heatmap"])


def _sim_body(**kw):
    base = dict(business_date=None, policies=["fifo", "slot_based"], weighbridges=2, slot_minutes=30, trucks_per_slot=6, unloading_ramps=3,
                seed=42, ramp_capacity_t=600, replay_observed_outages=True)
    base.update(kw)
    return SimpleNamespace(**base)


def test_queue_simulation_seeded_and_honest(demo_db, demo_settings):
    ctx = ctx_at(demo_settings, "2026-11-14T23:30")
    a = logistics_sim.run(demo_db, ctx, _sim_body())
    b = logistics_sim.run(demo_db, ctx, _sim_body())
    assert a["results"][0]["avg_wait_min"] == b["results"][0]["avg_wait_min"]  # deterministic per seed
    fifo, slot = a["results"]
    assert fifo["avg_deferral_min"] == 0
    assert slot["avg_total_delay_min"] == pytest.approx(slot["avg_wait_min"] + slot["avg_deferral_min"], abs=0.05)
    assert a["observed"]["trucks"] == a["trucks_simulated"]
    assert a["inferred_outages"]  # WB / ramp outage inferred from recorded events on the congestion day
    assert a["provenance"]["kind"] == "what_if" and a["limitations"]


def test_insights_from_facts(demo_db, demo_settings):
    r = kpi_insights.insights(demo_db, ctx_at(demo_settings, FOCUS["OER_DEGRADATION"]))
    assert r["generated_by"] == "deterministic_rules"
    item = r["items"][0]
    assert "OER" in item["headline"] and item["evidence"][0]["observed"] < item["evidence"][0]["expected"]
    assert "proven cause" in item["detail"] or "not proven" in item["detail"] or "check lab" in item["detail"]
    calm = kpi_insights.insights(demo_db, ctx_at(demo_settings, FOCUS["NORMAL_DAY"]))
    assert calm["items"] == []
    press = kpi_insights.insights(demo_db, ctx_at(demo_settings, FOCUS["PRESS_VIBRATION_ANOMALY"]))
    assert any("PRS-03" in i["headline"] for i in press["items"])


def test_bottleneck_one_flagged(demo_db, demo_settings):
    r = kpi_insights.bottlenecks(demo_db, ctx_at(demo_settings), "7d")
    assert any(s["is_bottleneck"] for s in r["stages"])
