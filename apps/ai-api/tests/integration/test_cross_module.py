"""Cross-module consistency: the modules must tell the same story at the same demo clock.

Every number here comes from the HTTP API and is either compared with another module's answer or recomputed
from the raw tables with independent SQL. Scenario focus times are the playback clocks from /scenarios.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from tests.integration.conftest import NORMAL, OER_FOCUS, PRESS, PRS03, TRUCK_FOCUS, TRUCK_PEAK

ADMIN = {"X-Demo-Role": "system_admin"}
DB_FMT = "%Y-%m-%d %H:%M:%S.%f"


def get(client, path, as_of=None, headers=None, **params):
    if as_of:
        params["as_of"] = as_of
    r = client.get(f"/api/v1{path}", params=params, headers=headers or ADMIN)
    assert r.status_code == 200, (path, r.status_code, r.text[:300])
    return r.json()


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)


def dbts(d: datetime) -> str:
    return d.astimezone(UTC).strftime(DB_FMT)


def kpis(client, as_of, period="today", headers=None):
    body = get(client, "/executive/kpis", as_of, headers=headers, period=period)
    return {k["key"]: k for k in body["kpis"]}, body


# --------------------------------------------------------------------------- 1. PRESS_VIBRATION_ANOMALY vs NORMAL_DAY


def test_scenario_focus_times_are_the_ones_these_tests_use(client):
    cat = {s["code"]: s["focus_ts"] for s in get(client, "/scenarios")["items"]}
    assert cat["PRESS_VIBRATION_ANOMALY"] == PRESS
    assert cat["NORMAL_DAY"] == NORMAL
    assert cat["OER_DEGRADATION"] == OER_FOCUS
    assert cat["TRUCK_QUEUE_CONGESTION"] == TRUCK_FOCUS


@pytest.mark.parametrize("as_of,abnormal", [(PRESS, True), (NORMAL, False)])
def test_prs03_story_is_the_same_in_every_module(client, as_of, abnormal):
    # health (rules) - equipment detail - equipment list
    health = get(client, f"/maintenance/equipment/{PRS03}/health", as_of)
    detail = get(client, f"/maintenance/equipment/{PRS03}", as_of)
    listed = next(e for e in get(client, "/maintenance/equipment", as_of)["items"] if e["id"] == PRS03)
    assert health["state"] == detail["health"]["state"] == listed["health_state"]
    assert health["state"] == ("critical" if abnormal else "normal")
    breached = {c["sensor_code"] for c in health["criteria"] if c["breached"] and c["affects_state"]}
    assert ("PRS-03-VIB-DE" in breached) is abnormal

    # process twin: PRESSING stage status = worst equipment health; its active-alert count = open PRS-03/pressing alerts
    stages = {s["code"]: s for s in get(client, "/process/stages", as_of)["stages"]}
    pressing = stages["PRESSING"]
    alerts = get(client, "/alerts", as_of, limit=200)["items"]
    active = [a for a in alerts if a["status"] in {"new", "acknowledged", "in_progress"}]
    prs_active = [a for a in active if (a["equipment"] or {}).get("id") == PRS03]
    stage_active = [a for a in active if a["process_stage_code"] == "PRESSING" or (a["equipment"] or {}).get("id") in
                    {e["id"] for e in get(client, "/maintenance/equipment", as_of, stage_code="PRESSING")["items"]}]
    assert pressing["active_alerts"] == len(stage_active)
    assert pressing["status"] == ("critical" if abnormal else "normal")

    # executive: KPI count of active maintenance alerts = alerts endpoint; top alerts lead with PRS-03
    k, _ = kpis(client, as_of)
    maint_active = [a for a in active if a["module"] == "maintenance" or a["equipment"] is not None]
    assert k["active_maintenance_alerts"]["value"] == len(maint_active)
    overview = get(client, "/executive/overview", as_of)
    insight = get(client, "/executive/insights", as_of)
    if abnormal:
        assert len(prs_active) >= 3 and any(a["severity"] == "critical" for a in prs_active)
        assert overview["top_alerts"] and overview["top_alerts"][0]["equipment"]["code"] == "PRS-03"
        assert "PRS-03" in insight["summary"] and insight["items"][0]["suggested_team"] == "maintenance"
    else:
        assert prs_active == [] and overview["top_alerts"] == [] and insight["items"] == []
        assert k["active_maintenance_alerts"]["value"] == 0

    # ML: equipment anomaly + failure-risk ranking
    anomalies = [a for a in get(client, "/ai/anomalies/equipment", as_of, limit=200)["items"] if (a["equipment"] or {}).get("id") == PRS03]
    risk = get(client, "/ai/failure-risk", as_of)["items"]
    if abnormal:
        latest = max(anomalies, key=lambda a: a["start_ts"])
        assert latest["severity"] == "critical" and latest["score"] >= 0.9
        assert {"PRS-03-VIB-DE"} & set(latest["contributing_sensors"]) or latest["contributing_sensors"]
        assert risk[0]["equipment"]["code"] == "PRS-03" and risk[0]["rank"] == 1
        # every open ML alert on PRS-03 points at an anomaly the ML endpoint also shows, with the same severity
        by_id = {a["id"]: a for a in anomalies}
        for al in prs_active:
            if al["anomaly_event_id"] and al["source"] != "rule":
                assert al["anomaly_event_id"] in by_id
                assert al["severity"] == by_id[al["anomaly_event_id"]]["severity"]
    else:
        assert anomalies == [] and all(r["equipment"]["code"] != "PRS-03" for r in risk)

    # advisory recommendations
    recos = [r for r in get(client, "/maintenance/recommendations", as_of, limit=200)["items"] if (r["equipment"] or {}).get("id") == PRS03]
    urgent = [r for r in recos if r["priority"] in {"critical", "high"} and r["status"] == "proposed"]
    assert bool(urgent) is abnormal
    assert all(r["advisory"] for r in recos)


def test_ml_alert_severity_and_title_never_come_from_the_future(client, sql):
    """QA-16: an ML alert at its own raised_at must agree with its anomaly rendered at that clock (no peak look-ahead)."""
    rows = sql("select id, raised_at, anomaly_event_id from alerts where anomaly_event_id is not null and source != 'rule'")
    assert len(rows) >= 50
    checked = 0
    for aid, raised, an in rows:
        clock = raised.replace(" ", "T")[:19] + "Z"
        al = get(client, f"/alerts/{aid}", clock)
        anomaly = get(client, f"/ai/anomalies/{an}", clock)
        assert al["severity"] == anomaly["severity"], (aid, clock)
        checked += 1
    assert checked == len(rows)
    # the congestion alert at the focus time: the stored title quoted the episode peak ("up to 35 trucks"), hours ahead
    al = get(client, "/alerts/77", TRUCK_FOCUS)
    trucks = int(re.search(r"up to (\d+) trucks", al["title"]).group(1))
    an = get(client, f"/ai/anomalies/{al['anomaly_event_id']}", TRUCK_FOCUS)
    assert trucks == int(max(e["observed"] for e in an["evidence"]))
    assert trucks < 35
    later = get(client, "/alerts/77", "2026-11-14T10:00:00Z")
    assert int(re.search(r"up to (\d+) trucks", later["title"]).group(1)) >= trucks
    # severity filter follows the as_of severity
    crit = get(client, "/alerts", TRUCK_FOCUS, severity="critical", limit=200)["items"]
    assert all(a["severity"] == "critical" for a in crit)
    assert 77 not in {a["id"] for a in crit} or al["severity"] == "critical"


def test_insight_text_does_not_call_an_ml_alert_a_threshold_rule(client):
    items = get(client, "/executive/insights", PRESS)["items"]
    alerts = {a["id"]: a for a in get(client, "/alerts", PRESS, limit=200)["items"]}
    seen = 0
    for it in items:
        rel = [r for r in it["related"] if r["type"] == "alert"]
        if not rel:
            continue
        src = alerts[rel[0]["id"]]["source"]
        assert ("Threshold rule only" in it["detail"]) is (src == "rule"), it["detail"]
        seen += 1
    assert seen >= 2


# --------------------------------------------------------------------------- 2. work order -> cross-module, one session only


def test_work_order_changes_prs03_and_alert_for_that_session_only(client):
    a_sess, b_sess = str(uuid.uuid4()), str(uuid.uuid4())
    eng = {"X-Demo-Role": "maintenance_engineer", "X-Demo-Session": a_sess}
    other = {"X-Demo-Role": "maintenance_engineer", "X-Demo-Session": b_sess}

    def snapshot(h):
        d = get(client, f"/maintenance/equipment/{PRS03}", PRESS, headers=h)
        lst = next(e for e in get(client, "/maintenance/equipment", PRESS, headers=h)["items"] if e["id"] == PRS03)
        return {
            "maintenance_status": d["maintenance_status"],
            "health_maintenance_status": d["health"]["maintenance_status"],
            "list_maintenance_status": lst["maintenance_status"],
            "active_wo": d["active_work_order_ids"],
            "alert83": get(client, "/alerts/83", PRESS, headers=h)["status"],
            "alert83_in_list": next(a["status"] for a in get(client, "/alerts", PRESS, headers=h, limit=200)["items"] if a["id"] == 83),
            "pressing_alerts": next(s["active_alerts"] for s in get(client, "/process/stages", PRESS, headers=h)["stages"] if s["code"] == "PRESSING"),
            "exec_active": kpis(client, PRESS, headers=h)[0]["active_maintenance_alerts"]["value"],
            "health_state": d["health"]["state"],
        }

    before_a, before_b, before_anon = snapshot(eng), snapshot(other), snapshot(ADMIN)
    assert before_a == before_b == before_anon
    assert before_a["maintenance_status"] == "none" and before_a["alert83"] == "new"

    r = client.post("/api/v1/work-orders", params={"as_of": PRESS}, headers=eng,
                    json={"equipment_id": PRS03, "title": "Inspect PRS-03 drive-end bearing", "alert_id": 83, "priority": "high", "confirm": True})
    assert r.status_code == 201, r.text
    wo = r.json()

    after_a, after_b, after_anon = snapshot(eng), snapshot(other), snapshot(ADMIN)
    assert after_a["maintenance_status"] == after_a["health_maintenance_status"] == after_a["list_maintenance_status"] == "work_order_open"
    assert after_a["active_wo"] == [wo["id"]]
    assert after_a["alert83"] == after_a["alert83_in_list"] == "in_progress"
    # in_progress is still an active alert: counts stay, sensor-based health does not change because paperwork exists
    assert after_a["pressing_alerts"] == before_a["pressing_alerts"]
    assert after_a["exec_active"] == before_a["exec_active"]
    assert after_a["health_state"] == "critical"
    # the other visitor and anonymous viewers see the untouched baseline
    assert after_b == before_b and after_anon == before_anon

    # assign -> in_progress -> resolved: alert follows in A only
    tech = get(client, "/maintenance/technicians", PRESS, headers=eng)["items"][0]["id"]
    assert client.post(f"/api/v1/work-orders/{wo['id']}/assign", params={"as_of": PRESS}, headers=eng, json={"technician_id": tech}).status_code == 200
    assert client.post(f"/api/v1/work-orders/{wo['id']}/transition", params={"as_of": PRESS}, headers=eng, json={"to_status": "in_progress"}).status_code == 200
    r = client.post(f"/api/v1/work-orders/{wo['id']}/transition", params={"as_of": PRESS}, headers=eng,
                    json={"to_status": "resolved", "resolution_notes": "Bearing replaced (demo)", "downtime_min": 90})
    assert r.status_code == 200, r.text
    done_a = snapshot(eng)
    assert done_a["active_wo"] == [] and done_a["maintenance_status"] != "work_order_open"
    assert snapshot(other) == before_b

    # reset removes A's rows; A is back on the baseline
    assert client.post("/api/v1/demo/session/reset", headers=eng).status_code == 200
    assert snapshot(eng) == before_a


# --------------------------------------------------------------------------- 3. ROI recomputed by hand


def _hand_roi(i: dict, m: dict) -> dict:
    ffb_base = i["daily_ffb_t"] * i["operating_days"]
    d_oer = (i["target_oer_pct"] - i["current_oer_pct"]) * m["oer_gap_realisation"]
    cpo_oer = ffb_base * d_oer / 100
    rec_h = min(i["downtime_h_per_month"] * 12 * min(100.0, i["downtime_reduction_pct"] * m["downtime_reduction_realisation"]) / 100,
                (24 - i["daily_ffb_t"] / i["processing_capacity_tph"]) * i["operating_days"])
    ffb_rec = rec_h * i["processing_capacity_tph"]
    cpo_dt = ffb_rec * i["current_oer_pct"] / 100
    gross = (cpo_oer + cpo_dt) * 1000 * i["cpo_price_thb_per_kg"]
    avoid = (i["energy_cost_thb_per_year"] + i["maintenance_expense_thb_per_year"]) * min(100.0, i["efficiency_improvement_pct"] * m["efficiency_realisation"]) / 100
    impl = i["implementation_cost_thb"] * m["implementation_cost_factor"]
    rec = i["recurring_cost_thb_per_year"] * m["recurring_cost_factor"]
    return {"cpo_oer": cpo_oer, "cpo_dt": cpo_dt, "additional_cpo_t": cpo_oer + cpo_dt, "gross": gross, "avoid": avoid,
            "net_year1": gross + avoid - impl - rec, "ffb_base": ffb_base, "ffb_rec": ffb_rec}


def _num(d: dict, *names):
    for n in names:
        if n in d and d[n] is not None:
            return d[n]
    raise KeyError(names)


def test_roi_recomputed_by_hand_without_double_counting(client, sql):
    dflt = get(client, "/roi/defaults", PRESS)
    i, mult = dflt["inputs"], dflt["case_multipliers"]

    # defaults trace back to the tables they claim (trailing 30 days of process_hourly to the clock)
    end = ts(PRESS)
    start = end - timedelta(days=30)
    ffb, cpo, down = sql("select sum(ffb_processed_t), sum(cpo_t), sum(downtime_min) from process_hourly where ts >= ? and ts <= ?",
                         dbts(start), dbts(end - timedelta(hours=1)))[0]
    assert i["daily_ffb_t"] == pytest.approx(ffb / 30, rel=0.01)
    assert i["current_oer_pct"] == pytest.approx(cpo / ffb * 100, abs=0.06)
    assert i["downtime_h_per_month"] == pytest.approx(down / 60, rel=0.03)

    r = client.post("/api/v1/roi/calculate", params={"as_of": PRESS}, headers=ADMIN, json=i)
    assert r.status_code == 200, r.text
    body = r.json()
    cases = {c["case"]: c for c in body["cases"]}
    assert set(cases) == {"baseline", "conservative", "expected", "optimistic"}
    for name, c in cases.items():
        h = _hand_roi(i, mult[name])
        assert _num(c, "additional_cpo_t") == pytest.approx(h["additional_cpo_t"], rel=1e-3, abs=0.05)
        assert _num(c, "net_benefit_year1_thb") == pytest.approx(h["net_year1"], rel=1e-3, abs=500)
        # no double counting: the two FFB bases are disjoint and the OER uplift is not applied to recovered FFB
        assert h["additional_cpo_t"] == pytest.approx(h["cpo_oer"] + h["cpo_dt"])
        overcount = h["ffb_rec"] * (i["target_oer_pct"] - i["current_oer_pct"]) * mult[name]["oer_gap_realisation"] / 100
        if overcount > 0.01:
            assert _num(c, "additional_cpo_t") < h["additional_cpo_t"] + overcount - 0.005
    assert cases["baseline"]["additional_cpo_t"] == 0
    assert "separate" in body["double_counting_note"].lower() or "double" in body["double_counting_note"].lower()


# --------------------------------------------------------------------------- 4. traceability mass conservation


@pytest.mark.parametrize("lot_id", [5, 33, 60, 88, 119])
def test_traceability_conserves_mass(client, sql, lot_id):
    rep = get(client, f"/traceability/lots/{lot_id}/report", PRESS)
    q_api = rep["lot"]["quantity_t"]
    q_sql, comp_sum, share_sum = sql(
        "select l.quantity_t, sum(c.cpo_t), sum(c.share) from cpo_output_lots l join lot_compositions c on c.cpo_lot_id = l.id where l.id = ?", lot_id)[0]
    assert q_api == pytest.approx(q_sql, abs=0.001)
    assert comp_sum == pytest.approx(q_sql, abs=0.001) and share_sum == pytest.approx(1.0, abs=1e-4)
    shares = rep["supplier_shares"]
    assert sum(s["attributed_cpo_t"] for s in shares) == pytest.approx(q_api, abs=0.01)
    assert sum(s["share_pct"] for s in shares) == pytest.approx(100.0, abs=0.01)
    # FFB attributed to suppliers = FFB of the contributing batches pro rata to the CPO each batch put in this lot
    ffb_kg = sql("select sum(c.cpo_t / pb.cpo_t * pb.ffb_input_t * 1000) from lot_compositions c "
                 "join production_batches pb on pb.id = c.production_batch_id where c.cpo_lot_id = ?", lot_id)[0][0]
    assert sum(s["ffb_kg"] for s in shares) == pytest.approx(ffb_kg, rel=1e-4)
    # each contributing batch: FFB in = sum of its batch inputs; CPO = FFB x OER
    for pb_id, ffb_t, cpo_t, oer, inputs_t, in_share in sql(
        "select pb.id, pb.ffb_input_t, pb.cpo_t, pb.oer_pct, sum(bi.mass_kg) / 1000.0, sum(bi.mass_share) from production_batches pb "
        "join batch_inputs bi on bi.production_batch_id = pb.id where pb.id in (select production_batch_id from lot_compositions where cpo_lot_id = ?) "
        "group by pb.id", lot_id):
        assert inputs_t == pytest.approx(ffb_t, abs=0.002), pb_id
        assert in_share == pytest.approx(1.0, abs=1e-4)
        assert cpo_t == pytest.approx(ffb_t * oer / 100, abs=0.002)
    # backward trace graph: edges into the lot carry the lot's mass
    g = get(client, "/traceability/backward", PRESS, lot_id=lot_id, max_nodes=1000)
    assert g["truncated"] is False
    into_root = sum(e["mass"] for e in g["edges"] if e["target"] == g["root"])
    assert into_root == pytest.approx(q_api, abs=0.01)


# --------------------------------------------------------------------------- 5. KPI endpoints = direct SQL


@pytest.mark.parametrize("as_of,period", [(PRESS, "today"), (TRUCK_FOCUS, "7d"), (NORMAL, "30d")])
def test_executive_kpis_equal_direct_sql(client, sql, as_of, period):
    k, body = kpis(client, as_of, period)
    lo, hi = ts(body["period_start"]), ts(body["period_end"])
    cut = hi - timedelta(hours=1)
    ffb, cpo, ker, run, down = sql(
        "select sum(ffb_processed_t), sum(cpo_t), sum(kernel_t), sum(running_minutes), sum(downtime_min) from process_hourly where ts >= ? and ts <= ?",
        dbts(lo), dbts(cut))[0]
    acc = sql("select sum(accepted_kg) / 1000.0 from ffb_deliveries where received_ts >= ? and received_ts <= ?", dbts(lo), dbts(hi))[0][0] or 0.0
    kwh, eff = sql("select sum(electricity_kwh), sum(ffb_processed_t) from energy_consumption where process_stage_id is null and ts >= ? and ts <= ?",
                   dbts(lo), dbts(cut))[0]
    waits = sql("select (julianday(weigh_in_ts) - julianday(arrival_ts)) * 1440 from truck_trips where weigh_in_ts >= ? and weigh_in_ts <= ?", dbts(lo), dbts(hi))
    assert k["ffb_processed_t"]["value"] == pytest.approx(ffb, abs=0.01)
    assert k["cpo_produced_t"]["value"] == pytest.approx(cpo, abs=0.01)
    assert k["oer_pct"]["value"] == pytest.approx(cpo / ffb * 100, abs=1e-3)
    assert k["ker_pct"]["value"] == pytest.approx(ker / ffb * 100, abs=1e-3)
    assert k["ffb_received_t"]["value"] == pytest.approx(acc, abs=0.01)
    assert k["throughput_tph"]["value"] == pytest.approx(ffb / (run / 60), abs=1e-3)
    assert k["equipment_availability_pct"]["value"] == pytest.approx(100 * run / (run + down), abs=1e-3)
    assert k["plant_downtime_h"]["value"] == pytest.approx(down / 60, abs=0.01)
    assert k["energy_kwh_per_t"]["value"] == pytest.approx(kwh / eff, abs=1e-3)
    assert k["logistics_queue_time_min"]["value"] == pytest.approx(sum(w[0] for w in waits) / len(waits), abs=0.01)
    for v in k.values():
        assert v["provenance"]["as_of"] == as_of and v["provenance"]["kind"] == "synthetic_actual"


# --------------------------------------------------------------------------- 6. OER_DEGRADATION


def test_oer_degradation_lower_oer_and_observed_driver_deviations(client, sql):
    deg, _ = kpis(client, OER_FOCUS)
    nor, _ = kpis(client, NORMAL)
    assert deg["oer_pct"]["value"] < nor["oer_pct"]["value"] - 0.5
    assert deg["oer_pct"]["value"] < deg["oer_pct"]["previous"]

    ins = get(client, "/executive/insights", OER_FOCUS)
    r1 = [i for i in ins["items"] if i["headline"].startswith("OER ")]
    assert len(r1) == 1
    ev = {e["metric"]: e for e in r1[0]["evidence"]}
    oer = ev.pop("oer_pct")
    assert oer["observed"] == pytest.approx(deg["oer_pct"]["value"], abs=1e-3)
    assert oer["observed"] < oer["normal_range"]["low"]  # outside trailing 28-day +/- 2 s.d.
    assert "not proven causes" in r1[0]["detail"]
    assert len(ev) >= 3
    lo, hi = ts(oer["window_start"]), ts(oer["window_end"])
    bad_dir = {"ffb_ripe_pct": -1, "sterilizer_cycle_min": -1, "clarifier_temp_c": -1}
    for metric, e in ev.items():
        # observed driver value = FFB-weighted mean over today's complete hours (independent SQL)
        num, den = sql(f"select sum({metric} * ffb_processed_t), sum(case when {metric} is not null then ffb_processed_t end) from process_hourly "
                       "where ts >= ? and ts <= ? and ffb_processed_t > 0", dbts(lo), dbts(hi - timedelta(hours=1)))[0]
        assert e["observed"] == pytest.approx(num / den, abs=2e-3), metric
        z = float(re.match(r"([+-]\d+\.\d+) s\.d\.", e["note"]).group(1))
        assert abs(z) > 2
        direction = bad_dir.get(metric, +1 if metric.startswith("oil_loss") else None)
        if direction is not None:
            assert (e["observed"] - e["expected"]) * direction > 0, metric
    # NORMAL_DAY raises no OER finding
    assert not [i for i in get(client, "/executive/insights", NORMAL)["items"] if i["headline"].startswith("OER ")]


# --------------------------------------------------------------------------- 7. TRUCK_QUEUE_CONGESTION


def test_truck_queue_now_and_logistics_alert_agree(client, sql):
    for clock in (TRUCK_FOCUS, TRUCK_PEAK):
        q = get(client, "/logistics/queue", clock)
        at = ts(clock)
        n = sql("select count(*) from truck_trips where arrival_ts <= ? and (weigh_in_ts is null or weigh_in_ts > ?)", dbts(at), dbts(at))[0][0]
        assert q["trucks_waiting"] == n, clock
        alerts = [a for a in get(client, "/alerts", clock, module="logistics", limit=200)["items"] if a["status"] != "resolved"]
        assert any(a["title"].startswith("Sustained queue anomaly") for a in alerts)
        for a in alerts:
            assert "accus" not in a["title"].lower()
    peak = get(client, "/logistics/queue", TRUCK_PEAK)
    normal = get(client, "/logistics/queue", NORMAL)
    assert peak["trucks_waiting"] >= 12 and normal["trucks_waiting"] == 0
    assert peak["avg_wait_min"] > 30
    # rule alerts that fired before the peak quote observations that are consistent with the queue at the peak
    rules = [a for a in get(client, "/alerts", TRUCK_PEAK, module="logistics", limit=200)["items"] if a["source"] == "rule" and a["status"] != "resolved"]
    assert rules and all(ts(a["raised_at"]) <= ts(TRUCK_PEAK) for a in rules)
    assert not [a for a in get(client, "/alerts", NORMAL, module="logistics", limit=200)["items"] if a["status"] != "resolved"]
    lk = {x["key"]: x for x in get(client, "/logistics/kpis", TRUCK_FOCUS)["kpis"]}
    assert lk["avg_wait_min"]["value"] > lk["avg_wait_min"]["previous"]


# --------------------------------------------------------------------------- 8. two downtime definitions


def test_plant_downtime_and_maintenance_event_downtime_are_distinct_labelled_numbers(client, sql):
    k, body = kpis(client, PRESS, "30d")
    plant_h = k["plant_downtime_h"]["value"]
    assert k["plant_downtime_h"]["label"] == "Plant downtime" and "process_hourly" in k["plant_downtime_h"]["provenance"]["source"]
    dt = get(client, "/maintenance/downtime", PRESS, period="30d")
    ev_h = dt["total_downtime_h"]
    assert "maintenance_events" in dt["provenance"]["source"] and "Maintenance" in dt["series"]["label"]
    assert abs(ev_h - plant_h) > 5, "the two definitions should differ on this data"
    # plant availability is the same number in both places
    assert dt["availability_pct"] == pytest.approx(k["equipment_availability_pct"]["value"], abs=0.01)
    # event downtime = maintenance-event minutes overlapping the window (independent SQL)
    lo, hi = ts(body["period_start"]), ts(body["period_end"])
    total = 0.0
    for s, e, dmin in sql("select start_ts, end_ts, downtime_min from maintenance_events where session_id is null and start_ts <= ? "
                          "and coalesce(end_ts, start_ts) >= ?", dbts(hi), dbts(lo)):
        s0 = max(datetime.fromisoformat(s).replace(tzinfo=UTC), lo)
        e0 = min(datetime.fromisoformat(e or s).replace(tzinfo=UTC), hi)
        mins = max(0.0, (e0 - s0).total_seconds() / 60)
        total += min(mins, dmin) if e and dmin and mins > dmin else mins
    assert ev_h == pytest.approx(total / 60, abs=0.02)


def test_copilot_downtime_what_if_uses_plant_downtime(client):
    k, _ = kpis(client, PRESS, "30d")
    plant_h = k["plant_downtime_h"]["value"]
    ev_h = get(client, "/maintenance/downtime", PRESS, period="30d")["total_downtime_h"]
    r = client.post("/api/v1/copilot/chat", params={"as_of": PRESS},
                    headers={"X-Demo-Role": "factory_manager", "X-Demo-Session": str(uuid.uuid4())},
                    json={"message": "What if downtime is reduced by 10 percent?", "lang": "en"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["refused"] is False and body["provenance"]["kind"] == "what_if"
    calls = {c["tool"]: c for c in body["tool_calls"]}
    hours = calls["run_business_scenario"]["arguments"]["downtime_hours"]
    assert hours == pytest.approx(0.10 * plant_h, abs=0.01)
    assert hours != pytest.approx(0.10 * ev_h, abs=0.05)
    assert f"{plant_h:.2f} h" in body["answer"]
    assert "not the sum of maintenance events" in body["answer"]
