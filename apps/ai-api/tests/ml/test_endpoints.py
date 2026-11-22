"""AI endpoint contract + as_of tests (on data/dev/ml.db after python -m app.ml.train)."""

from __future__ import annotations

import uuid

import pandas as pd
import pytest

from tests.ml.conftest import needs_ml_db

H = {"X-Demo-Role": "ai_analyst"}
pytestmark = needs_ml_db


@pytest.mark.parametrize("path", [
    "/api/v1/ai/oer/forecast?horizon_h=6", "/api/v1/ai/oer/explanation", "/api/v1/ai/oer/model", "/api/v1/ai/anomalies/production",
    "/api/v1/ai/anomalies/equipment", "/api/v1/ai/failure-risk", "/api/v1/ai/energy/forecast?horizon_h=6", "/api/v1/ai/energy/anomalies",
    "/api/v1/ai/logistics/queue-prediction", "/api/v1/ai/logistics/arrival-forecast?horizon_h=6", "/api/v1/ai/logistics/anomalies",
    "/api/v1/ai/models", "/api/v1/ai/models/oer_forecast", "/api/v1/cv/protocol",
])
def test_get_endpoints_ok(ml_client, path):
    r = ml_client.get(path, headers=H)
    assert r.status_code == 200, r.text


def test_oer_forecast_provenance_and_as_of(ml_client):
    as_of = "2026-11-20T15:00"
    r = ml_client.get(f"/api/v1/ai/oer/forecast?horizon_h=12&as_of={as_of}", headers=H).json()
    t_asof = pd.Timestamp(as_of, tz="Asia/Bangkok")
    assert r["forecast"]["provenance"]["kind"] == "forecast"
    assert r["forecast"]["provenance"]["model_version"] == "oer_forecast@1.0.0"
    assert r["actual"]["provenance"]["kind"] == "synthetic_actual"
    assert all(pd.Timestamp(p["t"]) + pd.Timedelta(hours=1) <= t_asof for p in r["actual"]["points"])
    assert len(r["forecast"]["points"]) == 12
    assert all(p["lower"] <= p["v"] <= p["upper"] for p in r["forecast"]["points"])
    names = {m["name"]: m for m in r["model"]["metrics"]}
    assert names["mae"]["beats_baseline"] is False  # measured: the model does not beat the rolling-mean baseline


def test_anomalies_respect_as_of(ml_client):
    as_of = "2026-11-13T12:00"
    t = pd.Timestamp(as_of, tz="Asia/Bangkok")
    later = ml_client.get("/api/v1/ai/anomalies/equipment?period=30d", headers=H).json()
    early = ml_client.get(f"/api/v1/ai/anomalies/equipment?period=30d&as_of={as_of}", headers=H).json()
    assert early["total"] < later["total"]
    for o in early["items"]:
        assert pd.Timestamp(o["start_ts"]) <= t
        assert o["end_ts"] is None or pd.Timestamp(o["end_ts"]) <= t
        assert o["peak_ts"] is None or pd.Timestamp(o["peak_ts"]) <= t
        for e in o["evidence"]:
            assert e["window_end"] is None or pd.Timestamp(e["window_end"]) <= t
    ids = {o["id"] for o in later["items"]} - {o["id"] for o in early["items"]}
    hidden = next(iter(ids))
    assert ml_client.get(f"/api/v1/ai/anomalies/{hidden}?as_of={as_of}", headers=H).status_code == 404


def test_press_anomaly_detected_before_critical_alarm(ml_client):
    # the rule critical alarm on PRS-03 is raised 2026-11-19 10:20 local; ML must already show PRS-03 the day before
    r = ml_client.get("/api/v1/ai/anomalies/equipment?period=7d&as_of=2026-11-18T18:00", headers=H).json()
    assert any(o["equipment"] and o["equipment"]["code"] == "PRS-03" for o in r["items"])
    o = next(o for o in r["items"] if o["equipment"] and o["equipment"]["code"] == "PRS-03")
    assert o["contributing_sensors"] and o["contributing_factors"] and o["recommended_investigation"]
    assert any(e["normal_range"] for e in o["evidence"])


def test_status_change_requires_session_and_is_session_scoped(ml_client):
    items = ml_client.get("/api/v1/ai/anomalies/production?period=30d", headers=H).json()["items"]
    aid = items[0]["id"]
    assert ml_client.post(f"/api/v1/ai/anomalies/{aid}/status", json={"to_status": "verified"}, headers=H).status_code == 428
    s = str(uuid.uuid4())
    r = ml_client.post(f"/api/v1/ai/anomalies/{aid}/status", json={"to_status": "verified", "note": "checked"},
                       headers={**H, "X-Demo-Session": s})
    assert r.status_code == 200 and r.json()["status"] == "verified"
    assert ml_client.get(f"/api/v1/ai/anomalies/{aid}", headers=H).json()["status"] == "new"  # other visitors unaffected
    assert ml_client.post(f"/api/v1/ai/anomalies/{aid}/status", json={"to_status": "verified"},
                          headers={"X-Demo-Role": "public_viewer", "X-Demo-Session": s}).status_code == 403


def test_model_cards_have_all_spec_fields(ml_client):
    items = ml_client.get("/api/v1/ai/models", headers=H).json()["items"]
    assert len(items) == 8
    for c in items:
        for k in ("purpose", "input_features", "training_data", "synthetic_data_assumptions", "algorithm", "evaluation_method",
                  "metrics", "limitations", "known_failure_modes", "deployment_status"):
            assert c[k], (c["name"], k)


def test_unknown_model_404(ml_client):
    assert ml_client.get("/api/v1/ai/models/not_a_model", headers=H).status_code == 404


def test_model_run(ml_client):
    r = ml_client.post("/api/v1/ai/models/equipment_anomaly/run?as_of=2026-11-20T15:00", json={}, headers=H)
    assert r.status_code == 200 and r.json()["provenance"]["kind"] == "forecast"


def test_ml_alerts_hidden_before_detection(ml_client):
    j = ml_client.get("/api/v1/alerts?as_of=2026-11-10T12:00&limit=200", headers=H).json()
    t = pd.Timestamp("2026-11-10T12:00", tz="Asia/Bangkok")
    ml = [a for a in j["items"] if a["code"].startswith("MLA-")]
    assert ml and all(pd.Timestamp(a["raised_at"]) <= t for a in ml)
    assert not any("PRS-03" in a["title"] for a in ml)


def test_truck_level_wait_flags_raise_no_alerts_but_queue_window_does():
    from app.ml.common import load_metrics

    q = load_metrics("logistics_anomaly")["metrics"]["queue_window_alerts"]["window_check"]
    assert q["normal_day_alerts"] == 0 and q["truck_queue_congestion_alerts"] >= 1


def test_explanation_has_nowcast_and_granularity_note(ml_client):
    j = ml_client.get("/api/v1/ai/oer/explanation?as_of=2026-11-20T15:00", headers=H).json()
    n = j["nowcast"]
    assert n["granularity"] == "day" and n["residual_band_pp"] > 0
    assert abs(n["actual_oer_pct"] - n["expected_oer_pct"] - n["residual_pp"]) < 1e-3
    assert "No granularity" in j["granularity_note"]
