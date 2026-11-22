"""DML-050/087/089: scenario catalog (measured effects only), production what-if reproducibility, saved scenarios."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.models import ScenarioRun
from app.services import scenarios as scn

from .conftest import FOCUS, err, hdr

PV = hdr("public_viewer", None)


def test_catalog_matches_scenario_runs_and_activation_info(client, db):
    j = client.get("/api/v1/scenarios", params={"as_of": FOCUS}, headers=PV).json()
    runs = {r.code: r for r in db.execute(select(ScenarioRun)).scalars()}
    assert {i["code"] for i in j["items"]} == set(runs) and len(j["items"]) == 6
    for it in j["items"]:
        r = runs[it["code"]]
        assert it["focus_ts"].startswith(r.focus_ts.strftime("%Y-%m-%dT%H:%M")) and it["activate_as_of"] == it["focus_ts"]
        assert f"scenario_id={it['code']}" in it["activate_query"] and it["highlights_available"] is True
        assert it["name_th"]  # bilingual names
    # activating = sending focus_ts as as_of: the demo context resolves scenario_id to the same time
    ctx = client.get("/api/v1/demo/context", params={"scenario_id": "PRESS_VIBRATION_ANOMALY"}, headers=PV).json()["context"]
    press = [i for i in j["items"] if i["code"] == "PRESS_VIBRATION_ANOMALY"][0]
    assert ctx["as_of"] == press["focus_ts"]


def test_effects_are_measured_not_designed_intent(client, db):
    items = {i["code"]: i for i in client.get("/api/v1/scenarios", params={"as_of": FOCUS}, headers=PV).json()["items"]}
    run = db.execute(select(ScenarioRun).where(ScenarioRun.code == "PRESS_VIBRATION_ANOMALY")).scalar_one()
    press = items["PRESS_VIBRATION_ANOMALY"]
    designed = json.loads(run.expected_effects_json)
    designed_text = {d["description"] for d in designed} | {run.description}
    assert not ({e["description"] for e in press["expected_effects"]} & designed_text) and press["description"] != run.description
    by_metric = {e["metric"]: e for e in press["expected_effects"]}
    assert by_metric["oer_pct"]["basis"].startswith("measured") and by_metric["oer_pct"]["delta"] is not None
    # the data-grounded statement: plant OER barely moves, within normal variation (the build plan ruling), while the sensor does
    assert abs(by_metric["oer_pct"]["delta"]) < 0.5 and "within normal day-to-day variation" in by_metric["oer_pct"]["significance"]
    vib = [e for e in press["expected_effects"] if e["metric"].startswith("peak_PRS-03-VIB")][0]
    assert vib["focus_value"] > 4.5 > vib["baseline_value"] and vib["entity_code"] == "PRS-03"
    health = [e for e in press["expected_effects"] if e["metric"] == "health_state"][0]
    assert "critical at the focus time" in health["description"] and "normal at the baseline time" in health["description"]
    queue = items["TRUCK_QUEUE_CONGESTION"]
    wait = [e for e in queue["expected_effects"] if e["metric"] == "truck_wait_to_weigh_min"][0]
    assert wait["focus_value"] > wait["baseline_value"]  # measured, not asserted from the design
    oer = items["OER_DEGRADATION"]["expected_effects"][0]
    assert oer["metric"] == "oer_pct" and oer["delta"] < -0.5 and "x the normal" in oer["significance"]  # outside normal variation


def test_scenarios_after_the_demo_clock_read_no_future_data(client):
    items = {i["code"]: i for i in client.get("/api/v1/scenarios", params={"as_of": "2026-10-03"}, headers=PV).json()["items"]}
    assert items["OER_DEGRADATION"]["highlights_available"] is True and items["ENERGY_EFFICIENCY_DROP"]["highlights_available"] is True
    for code in ("NORMAL_DAY", "STEAM_PRESSURE_DEVIATION", "TRUCK_QUEUE_CONGESTION", "PRESS_VIBRATION_ANOMALY"):
        assert items[code]["highlights_available"] is False and items[code]["expected_effects"] == [] and "after the current demo clock" in items[code]["highlights_note"]
        assert items[code]["focus_ts"]  # the schedule itself is still listed for navigation
    one = client.get("/api/v1/scenarios/PRESS_VIBRATION_ANOMALY", params={"as_of": "2026-10-03"}, headers=PV).json()
    assert one["highlights_available"] is False
    assert client.get("/api/v1/scenarios/NOPE", headers=PV).status_code == 422


# ---------------------------------------------------------------- production what-if
def _calc(client, body, headers=PV, **params):
    r = client.post("/api/v1/scenarios/production/calculate", params={"as_of": FOCUS, **params}, json=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _kpi(j, section, key):
    return [k for k in j[section] if k["key"] == key][0]


def test_no_changes_means_zero_delta_and_provenance_kinds(client):
    j = _calc(client, {})
    assert all(d["value"] == 0 for d in j["delta"]) and j["warnings"] == []
    assert {k["provenance"]["kind"] for k in j["baseline"]} == {"synthetic_actual"} and {k["provenance"]["kind"] for k in j["scenario"]} == {"what_if"}


def test_calculation_example_is_flagged_and_exact(client):
    j = _calc(client, {})
    ex = [f for f in j["formulas"] if f["key"] == "calculation_example"][0]
    assert ex["result"] == 1000.0 * 0.5 / 100 == 5.0 and "not a forecast" in ex["label"] and ex["inputs"] == {"ffb_t": 1000.0, "delta_oer_pp": 0.5}
    assert j["calculation_example"] == "Calculation example: 1,000 t FFB x +0.5 pp OER = +5 t CPO"


def test_formulas_reproduce_by_hand_from_the_returned_baseline(client):
    base = _calc(client, {})["baseline_inputs"]
    body = {"oer_pct": 19.0, "availability_pct": 95.0, "processing_hours_per_day": 18.0, "ffb_intake_t_per_day": 1000.0, "cpo_price_thb_per_kg": 40.0, "energy_cost_thb_per_kwh": 2.0, "days": 30}
    j = _calc(client, body)
    cap = 60.0
    running = 18.0 * 0.95
    processed = min(1000.0, running * cap)  # 1000: below the 1026 t/day capacity
    cpo_day = processed * (19.0 + (base["oil_loss_pct"] - base["oil_loss_pct"])) / 100
    assert round(_kpi(j, "scenario", "cpo_t")["value"], 2) == round(cpo_day * 30, 2)
    assert round(_kpi(j, "scenario", "cpo_revenue_thb")["value"], 0) == round(cpo_day * 30 * 1000 * 40.0, 0)
    energy_kwh_per_t = [a for a in j["assumptions"] if a["key"] == "energy_per_tonne"][0]["value"]
    assert abs(_kpi(j, "scenario", "energy_cost_thb")["value"] - processed * 30 * energy_kwh_per_t * 2.0) < 50  # kWh/t is rounded in the assumption
    assert round(_kpi(j, "scenario", "running_hours_per_day")["value"], 3) == round(running, 3)
    f = {x["key"]: x for x in j["formulas"]}
    assert f["processed_t"]["result"] == round(processed, 1) and f["capacity_t"]["result"] == round(running * cap, 1)
    d = _kpi(j, "delta", "cpo_t")
    assert abs(d["value"] - (_kpi(j, "scenario", "cpo_t")["value"] - _kpi(j, "baseline", "cpo_t")["value"])) < 0.01


def test_oer_and_oil_loss_levers_follow_mass_balance(client):
    base = _calc(client, {})
    ffb = _kpi(base, "baseline", "ffb_processed_t")["value"]
    up = _calc(client, {"oer_pct": base["baseline_inputs"]["oer_pct"] + 0.5})
    assert abs(_kpi(up, "delta", "cpo_t")["value"] - ffb * 0.5 / 100) < 0.5  # +0.5 pp on the processed FFB
    less_loss = _calc(client, {"oil_loss_pct": base["baseline_inputs"]["oil_loss_pct"] - 0.2})
    assert abs(_kpi(less_loss, "delta", "oer_pct")["value"] - 0.2) < 1e-3  # 0.2 pp less oil lost = 0.2 pp more OER


def test_intake_above_capacity_is_not_produced(client):
    j = _calc(client, {"ffb_intake_t_per_day": 1500})
    proc = _kpi(j, "scenario", "ffb_processed_t")["value"]
    assert proc < 1500 * 30 and _kpi(j, "scenario", "unprocessed_ffb_t")["value"] > 0 and "waiting on the ramp" in " ".join(j["warnings"]).replace("would wait on the ramp", "waiting on the ramp")


@pytest.mark.parametrize("body", [{"oer_pct": 36}, {"oer_pct": 0}, {"availability_pct": 101}, {"days": 0}, {"days": 400}, {"ffb_intake_t_per_day": -5}, {"oil_loss_pct": 11}, {"cpo_price_thb_per_kg": 0}])
def test_what_if_inputs_are_bounded(client, body):
    r = client.post("/api/v1/scenarios/production/calculate", params={"as_of": FOCUS}, json=body, headers=PV)
    assert r.status_code == 422 and err(r) == "validation_error"


def test_what_if_needs_history_at_the_clock(client):
    r = client.post("/api/v1/scenarios/production/calculate", params={"as_of": "2026-07-24T06:00:00Z"}, json={}, headers=PV)
    assert r.status_code == 422 and err(r) == "insufficient_data"


# ---------------------------------------------------------------- saved scenarios
def test_saved_scenarios_are_session_scoped_validated_and_audited(client, db):
    a, b = hdr("executive"), hdr("executive")
    r = client.post("/api/v1/scenarios/saved", params={"as_of": FOCUS}, json={"kind": "production", "name": "+0.5 pp OER", "inputs": {"oer_pct": 18.9}, "outputs": {"cpo": 1}}, headers=a)
    assert r.status_code == 201 and r.json()["demo_as_of"] == FOCUS
    assert [x["name"] for x in client.get("/api/v1/scenarios/saved", headers=a).json()["items"]] == ["+0.5 pp OER"]
    assert client.get("/api/v1/scenarios/saved", headers=b).json()["items"] == []
    assert client.get("/api/v1/scenarios/saved", params={"kind": "roi"}, headers=a).json()["items"] == []
    assert client.post("/api/v1/scenarios/saved", json={"kind": "bogus", "name": "x", "inputs": {}, "outputs": {}}, headers=a).status_code == 422
    big = {"k": "x" * (scn.MAX_SAVED_JSON_BYTES + 10)}
    assert err(client.post("/api/v1/scenarios/saved", json={"kind": "roi", "name": "big", "inputs": big, "outputs": {}}, headers=a)) == "payload_too_large"
    from app.models import AuditLog

    assert db.execute(select(AuditLog.action).where(AuditLog.session_id == a["X-Demo-Session"])).scalars().all() == ["scenario.save"]


def test_saved_scenario_quota(client, monkeypatch):
    monkeypatch.setattr(scn, "MAX_SAVED_SCENARIOS", 2)
    h = hdr("executive")
    for i in range(2):
        assert client.post("/api/v1/scenarios/saved", json={"kind": "production", "name": f"s{i}", "inputs": {}, "outputs": {}}, headers=h).status_code == 201
    assert err(client.post("/api/v1/scenarios/saved", json={"kind": "production", "name": "s3", "inputs": {}, "outputs": {}}, headers=h)) == "session_quota_exceeded"
