"""AI-C01 / AI-C03: health criteria, shared definition with the process twin, risk index, demo-clock discipline."""

from __future__ import annotations

import json
import uuid

import pytest

from app.models.enums import HealthState
from app.services import kpi_health
from app.services.demo_context import DemoContext
from app.services.maintenance_health import classify, iso_zone, linear_fit, percentile, risk_band

from .conftest import BASELINE, EARLY, FOCUS, hdr

PRS03 = 18


# ---------------------------------------------------------------- pure rules
@pytest.mark.parametrize(
    "value,warn,crit,low,expected",
    [
        (2.79, 2.8, 4.5, False, "normal"),
        (2.8, 2.8, 4.5, False, "warning"),  # Warning >= warn (inclusive)
        (4.49, 2.8, 4.5, False, "warning"),
        (4.5, 2.8, 4.5, False, "critical"),  # Critical >= crit (inclusive)
        (86.0, 85.0, 100.0, False, "warning"),
        (85.1, 85.0, 80.0, True, "normal"),  # low_is_bad reversed: Warning <= warn, Critical <= crit
        (85.0, 85.0, 80.0, True, "warning"),
        (80.0, 85.0, 80.0, True, "critical"),
        (1.0, None, None, False, "normal"),
        (9.9, 5.0, None, False, "warning"),
    ],
)
def test_classify_boundaries_and_same_definition_as_process_twin(value, warn, crit, low, expected):
    assert classify(value, warn, crit, low).value == expected
    assert kpi_health.sensor_state(value, warn, crit, low) in (expected, None)  # twin returns None only when there are no limits


def test_iso_zone_boundaries_group2_rigid():
    assert [iso_zone(v, 2.8, 4.5) for v in (1.0, 1.4, 2.79, 2.8, 4.49, 4.5, 6.0)] == ["A", "B", "B", "C", "C", "D", "D"]
    assert iso_zone(1.0, None, None) is None


def test_linear_fit_and_percentile_helpers():
    slope, intercept, r2 = linear_fit([0, 1, 2, 3], [1, 3, 5, 7])
    assert (round(slope, 9), round(intercept, 9), round(r2, 9)) == (2.0, 1.0, 1.0)
    assert linear_fit([0, 1, 2], [5, 5, 5])[2] == 0.0
    assert percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.9) == 9
    assert [risk_band(x) for x in (0, 24.9, 25, 49.9, 50, 75)] == ["low", "low", "elevated", "elevated", "high", "very_high"]


# ---------------------------------------------------------------- PRS-03 evidence
def test_prs03_critical_at_focus_with_evidence(client):
    r = client.get(f"/api/v1/maintenance/equipment/{PRS03}/health", params={"as_of": FOCUS}, headers=hdr("public_viewer", None))
    assert r.status_code == 200, r.text
    h = r.json()
    assert h["state"] == "critical" and h["equipment_code"] == "PRS-03"
    vib = [c for c in h["criteria"] if c["sensor_code"] == "PRS-03-VIB-DE" and c["state_if_breached"] == "critical"][0]
    assert vib["breached"] is True and vib["observed"] >= vib["limit"] == 4.5 and vib["iso_zone"] == "D" and vib["affects_state"] is True
    assert vib["samples_evaluated"] == 3 and vib["observed_ts"] <= FOCUS.replace("Z", "") + "Z" or vib["observed_ts"].startswith("2026-11-20T08:00")
    assert any("PRS-03-VIB-DE" in t for t in h["triggered_by"])
    bearing = [c for c in h["criteria"] if c["sensor_code"] == "PRS-03-TMP-BRG" and c["state_if_breached"] == "warning"][0]
    assert bearing["breached"] is True and bearing["observed"] >= 85.0
    # informational evidence is present but does not drive the state
    assert {c["kind"] for c in h["criteria"]} >= {"sensor_limit", "open_work_order", "service_interval", "open_alert"}
    assert all(c["affects_state"] is False for c in h["criteria"] if c["kind"] in ("service_interval", "open_alert"))
    assert h["provenance"]["kind"] == "synthetic_actual" and "health-rules" in h["provenance"]["model_version"]


def test_prs03_normal_on_baseline_day_with_no_breached_sensor_criteria(client):
    h = client.get(f"/api/v1/maintenance/equipment/{PRS03}/health", params={"as_of": BASELINE}, headers=hdr("public_viewer", None)).json()
    assert h["state"] == "normal"
    assert not any(c["breached"] for c in h["criteria"] if c["kind"] == "sensor_limit")
    assert h["risk_score"] < 25 and h["risk_band"] == "low"


def test_state_matches_process_twin_for_every_equipment(client, db):
    """One definition for the product: maintenance screens and the twin (kpi_health) must agree."""
    from app.config import Settings

    items = client.get("/api/v1/maintenance/equipment", params={"as_of": FOCUS}, headers=hdr("public_viewer", None)).json()["items"]
    assert len(items) == 35
    s = Settings()
    from app.services.demo_context import parse_as_of

    ctx = DemoContext(as_of=parse_as_of(FOCUS, s), as_of_explicit=True, window_start=s.window_start, window_end=s.window_end)
    twin = kpi_health.equipment_health(db, ctx)
    assert {i["id"]: i["health_state"] for i in items} == {eid: rec["state"] for eid, rec in twin.items()}


def test_counts_by_state_sum_and_filters(client):
    j = client.get("/api/v1/maintenance/equipment", params={"as_of": FOCUS}, headers=hdr("public_viewer", None)).json()
    assert sum(j["counts_by_state"].values()) == j["total"] == 35 and set(j["counts_by_state"]) == {s.value for s in HealthState}
    crit = client.get("/api/v1/maintenance/equipment", params={"as_of": FOCUS, "health_state": "critical"}, headers=hdr("public_viewer", None)).json()
    assert [i["code"] for i in crit["items"]] == ["PRS-03"]
    press = client.get("/api/v1/maintenance/equipment", params={"as_of": FOCUS, "stage_code": "PRESSING", "sort": "risk"}, headers=hdr("public_viewer", None)).json()
    assert [i["code"] for i in press["items"]][0] == "PRS-03" and len(press["items"]) == 4
    assert client.get("/api/v1/maintenance/equipment", params={"stage_code": "NOPE"}, headers=hdr("public_viewer", None)).status_code == 422


def test_detail_has_sensors_latest_and_limits(client):
    d = client.get(f"/api/v1/maintenance/equipment/{PRS03}", params={"as_of": FOCUS}, headers=hdr("public_viewer", None)).json()
    assert d["code"] == "PRS-03" and d["running_hours"] > 30000 and d["last_maintenance_at"] <= FOCUS
    vib = [s for s in d["sensors"] if s["code"] == "PRS-03-VIB-DE"][0]
    assert vib["warn_limit"] == 2.8 and vib["crit_limit"] == 4.5 and vib["latest"]["value"] >= 4.5 and vib["latest"]["provenance"]["kind"] == "synthetic_actual"
    assert client.get("/api/v1/maintenance/equipment/9999", headers=hdr("public_viewer", None)).status_code == 404


# ---------------------------------------------------------------- risk index
def test_risk_index_is_not_called_a_probability_and_components_sum(client):
    r = client.get(f"/api/v1/maintenance/equipment/{PRS03}/health", params={"as_of": FOCUS}, headers=hdr("public_viewer", None))
    h = r.json()
    assert "not a calibrated failure probability" in h["risk_meaning"].lower()
    assert "probability of failure" not in r.text.lower()
    assert round(sum(c["points"] for c in h["risk_components"]), 1) == h["risk_score"]
    assert sum(c["weight"] for c in h["risk_components"]) == 100.0 and {c["key"] for c in h["risk_components"]} == {"condition", "trend", "service", "alerts", "corroboration"}
    assert h["risk_score"] > 75 and h["risk_band"] == "very_high"
    assert "judgement" in h["risk_limits"].lower() or "calibrat" in h["risk_limits"].lower()


def test_risk_rises_as_degradation_progresses_and_ranks_prs03_first(client):
    scores = []
    for as_of in ("2026-11-05T08:00:00Z", "2026-11-14T08:00:00Z", "2026-11-18T08:00:00Z", FOCUS):
        scores.append(client.get(f"/api/v1/maintenance/equipment/{PRS03}/health", params={"as_of": as_of}, headers=hdr("public_viewer", None)).json()["risk_score"])
    assert scores == sorted(scores) and scores[-1] - scores[0] > 50, scores
    ranked = client.get("/api/v1/maintenance/equipment", params={"as_of": FOCUS, "sort": "risk"}, headers=hdr("public_viewer", None)).json()["items"]
    assert ranked[0]["code"] == "PRS-03" and ranked[0]["risk_score"] > 3 * ranked[1]["risk_score"]


# ---------------------------------------------------------------- demo clock discipline
def test_health_never_reads_the_future(client):
    h = client.get(f"/api/v1/maintenance/equipment/{PRS03}/health", params={"as_of": EARLY}, headers=hdr("public_viewer", None)).json()
    assert h["state"] != "critical"
    assert not any(c["kind"] == "open_alert" for c in h["criteria"])  # alerts of 11-15 / 11-19 do not exist yet
    for c in h["criteria"]:
        if c["observed_ts"]:
            assert c["observed_ts"] <= EARLY.replace("08:00:00Z", "08:00:00Z")
    assert json.dumps(h).count("ALR-20261119") == 0


def test_sensor_series_downsampled_clipped_to_as_of_with_markers(client):
    p = {"as_of": FOCUS, "sensor_codes": ["PRS-03-VIB-DE", "PRS-03-TMP-BRG"], "resolution": "hour", "end": "2026-11-30T00:00:00Z"}
    j = client.get(f"/api/v1/maintenance/equipment/{PRS03}/sensors", params=p, headers=hdr("public_viewer", None)).json()
    assert j["end"] == FOCUS and j["resolution"] == "hour" and len(j["series"]) == 2
    assert all(pt["t"] <= FOCUS for s in j["series"] for pt in s["points"]) and 160 <= len(j["series"][0]["points"]) <= 170
    assert j["limits"]["PRS-03-VIB-DE"] == {"warn_limit": 2.8, "crit_limit": 4.5, "low_is_bad": False}
    assert {m["code"] for m in j["alert_markers"]} >= {"ALR-20261115-0016", "ALR-20261119-0018"}
    assert j["anomaly_markers"] == []  # anomaly_events is filled by the ML pipeline later: empty is handled gracefully
    assert all(m["start_ts"] <= FOCUS for m in j["alert_markers"])
    raw = client.get(f"/api/v1/maintenance/equipment/{PRS03}/sensors", params={"as_of": FOCUS, "start": "2026-10-01T00:00:00", "resolution": "raw"}, headers=hdr("public_viewer", None)).json()
    assert raw["resolution"] != "raw" and "downsampled" in raw["note"]  # server-side cap keeps payloads small
    assert client.get(f"/api/v1/maintenance/equipment/{PRS03}/sensors", params={"sensor_codes": ["NOPE"]}, headers=hdr("public_viewer", None)).status_code == 422


def test_history_downtime_and_technicians(client):
    h = client.get("/api/v1/maintenance/equipment/16/history", params={"as_of": FOCUS, "period": "30d"}, headers=hdr("public_viewer", None)).json()
    assert h["equipment_id"] == 16 and h["window_end"] <= FOCUS and all(e["start_ts"] <= FOCUS for e in h["items"]) and "calendar basis" in h["mtbf_basis"]
    d = client.get("/api/v1/maintenance/downtime", params={"as_of": FOCUS, "period": "7d"}, headers=hdr("public_viewer", None)).json()
    assert d["total_downtime_h"] >= 0 and len(d["by_hour_of_day"]) == 24 and 80 < d["availability_pct"] <= 100
    assert abs(sum(b["downtime_h"] for b in d["by_hour_of_day"]) - d["total_downtime_h"]) < 0.1
    assert abs(sum(b["downtime_h"] for b in d["by_cause"]) - d["total_downtime_h"]) < 0.1
    t = client.get("/api/v1/maintenance/technicians", params={"as_of": FOCUS}, headers=hdr("public_viewer", None)).json()["items"]
    assert len(t) == 12 and sum(x["open_assignments"] for x in t) == 3  # seeded WO 114 (on hold), 115 (assigned), 116 (in progress)
    assert client.get("/api/v1/maintenance/equipment/16/history", params={"period": "custom"}, headers=hdr("public_viewer", None)).status_code == 422


def test_equipment_list_is_fast_enough(client):
    import time

    t = time.time()
    r = client.get("/api/v1/maintenance/equipment", params={"as_of": FOCUS}, headers=hdr("public_viewer", None))
    assert r.status_code == 200 and time.time() - t < 3.0
    assert uuid.UUID(str(uuid.uuid4()))  # keep uuid import used
