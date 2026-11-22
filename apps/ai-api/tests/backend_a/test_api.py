"""HTTP layer: contract status flipped, RBAC, validation envelopes, alert status copy-on-write + audit (writable copy)."""

from __future__ import annotations

import uuid

import pytest

from app.api.v1 import iter_contract_routes
from tests.backend_a.conftest import needs_db

OWN = ("/api/v1/executive", "/api/v1/production", "/api/v1/process", "/api/v1/energy", "/api/v1/logistics", "/api/v1/alerts", "/api/v1/reports")


def test_all_backend_a_routes_implemented():
    mine = [(p, r) for p, r in iter_contract_routes() if p.startswith(OWN)]
    assert len(mine) >= 31
    assert all(r.openapi_extra["x-status"] == "implemented" for _, r in mine)
    assert all(r.openapi_extra["x-owner"] == "backend-a" for _, r in mine)


GETS = [
    "/api/v1/executive/overview", "/api/v1/executive/kpis?period=30d", "/api/v1/executive/series?metric=energy_kwh_per_t&granularity=week",
    "/api/v1/executive/insights", "/api/v1/executive/bottlenecks", "/api/v1/executive/cost-productivity", "/api/v1/executive/scenario-comparison",
    "/api/v1/production/summary", "/api/v1/production/oer-trend", "/api/v1/production/process-state", "/api/v1/production/shifts",
    "/api/v1/production/losses", "/api/v1/production/batches", "/api/v1/production/quality", "/api/v1/process/stages",
    "/api/v1/process/stages/CLARIFICATION", "/api/v1/energy/summary", "/api/v1/energy/series?metric=idle_kwh", "/api/v1/logistics/queue",
    "/api/v1/logistics/tickets", "/api/v1/logistics/suppliers", "/api/v1/logistics/suppliers/1", "/api/v1/logistics/kpis",
    "/api/v1/logistics/arrival-pattern", "/api/v1/alerts", "/api/v1/alerts/18", "/api/v1/reports/energy?format=csv", "/api/v1/reports/executive/html", "/api/v1/reports/production/html?raw=true",
]  # fmt: skip


@needs_db
@pytest.mark.parametrize("path", GETS)
def test_get_endpoints_ok_for_public_viewer(demo_client, path):
    r = demo_client.get(path)
    assert r.status_code == 200, r.text[:300]


@needs_db
@pytest.mark.parametrize(
    "path,code",
    [
        ("/api/v1/executive/kpis?period=custom", "invalid_period"),
        ("/api/v1/executive/series?metric=nope", "invalid_metric"),
        ("/api/v1/production/summary?business_date=2027-01-01", "future_date"),
        ("/api/v1/executive/kpis?as_of=2030-01-01", "as_of_out_of_window"),
        ("/api/v1/alerts?limit=1000", "validation_error"),
    ],
)
def test_validation_envelopes(demo_client, path, code):
    r = demo_client.get(path)
    assert r.status_code == 422 and r.json()["error"]["code"] == code


@needs_db
def test_alert_raised_after_as_of_is_404(demo_client):
    assert demo_client.get("/api/v1/alerts/18?as_of=2026-11-01").status_code == 404


@needs_db
def test_post_simulation_and_what_if(demo_client):
    r = demo_client.post("/api/v1/logistics/queue-simulation?scenario_id=TRUCK_QUEUE_CONGESTION", json={"seed": 1})
    assert r.status_code == 200 and len(r.json()["results"]) == 2
    r = demo_client.post("/api/v1/energy/what-if", json={"idle_reduction_pct": 50})
    assert r.status_code == 200 and r.json()["saving_kwh"] > 0
    assert demo_client.post("/api/v1/energy/what-if", json={"idle_reduction_pct": 500}).status_code == 422


@needs_db
def test_alert_status_requires_role_and_session(write_client):
    assert write_client.post("/api/v1/alerts/18/status", json={"to_status": "acknowledged"}).status_code == 403  # public viewer
    r = write_client.post("/api/v1/alerts/18/status", json={"to_status": "acknowledged"}, headers={"X-Demo-Role": "maintenance_engineer"})
    assert r.status_code == 428


@needs_db
def test_alert_acknowledge_is_session_scoped_and_audited(write_client):
    sid = str(uuid.uuid4())
    h = {"X-Demo-Role": "maintenance_engineer", "X-Demo-Session": sid}
    r = write_client.post("/api/v1/alerts/18/status", json={"to_status": "acknowledged", "note": "checking"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "acknowledged"
    assert write_client.get("/api/v1/alerts/18", headers=h).json()["status"] == "acknowledged"
    assert write_client.get("/api/v1/alerts/18", headers={"X-Demo-Session": str(uuid.uuid4())}).json()["status"] == "new"  # other visitors untouched
    bad = write_client.post("/api/v1/alerts/18/status", json={"to_status": "new"}, headers=h)
    assert bad.status_code == 422
    write_client.post("/api/v1/alerts/18/status", json={"to_status": "resolved"}, headers=h)
    again = write_client.post("/api/v1/alerts/18/status", json={"to_status": "acknowledged"}, headers=h)
    assert again.status_code == 409
    from sqlalchemy import create_engine, text

    from tests.backend_a.conftest import WRITE_DB

    with create_engine(f"sqlite:///{WRITE_DB}").connect() as c:
        n = c.execute(text("select count(*) from audit_logs where session_id = :s and action = 'alert.status_change'"), {"s": sid}).scalar_one()
    assert n == 2
