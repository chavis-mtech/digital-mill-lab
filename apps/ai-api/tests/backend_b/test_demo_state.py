"""DML-034/037/103: session reset, reset-all, retention purge, simulated-live tick, contract completeness."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.api.v1 import iter_contract_routes
from app.models import AuditLog, BusinessScenario, WorkOrder
from app.services.audit import verify_chain
from app.services.demo_state import purge_idle_sessions

from .conftest import EARLY, FOCUS, err, hdr

WO = "/api/v1/work-orders"
PRESS = {"scenario_id": "PRESS_VIBRATION_ANOMALY"}


def _make_wo(client, h, **over):
    body = {"equipment_id": 17, "title": "Probe work order", "confirm": True, **over}
    r = client.post(WO, params={"as_of": FOCUS}, json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _count(db, model, sid):
    return db.execute(select(func.count()).select_from(model).where(model.session_id == sid)).scalar_one()


def test_session_reset_deletes_only_the_callers_rows_and_keeps_the_audit_log(client, db):
    a, b = hdr("maintenance_engineer"), hdr("maintenance_engineer")
    sa, sb = a["X-Demo-Session"], b["X-Demo-Session"]
    _make_wo(client, a)
    _make_wo(client, b)
    client.post("/api/v1/scenarios/saved", json={"kind": "production", "name": "mine", "inputs": {}, "outputs": {}}, headers=a)
    audit_before = db.execute(select(func.count()).select_from(AuditLog).where(AuditLog.session_id == sa)).scalar_one()
    r = client.post("/api/v1/demo/session/reset", headers=a)
    assert r.status_code == 200
    j = r.json()
    assert j["session_id"] == sa and j["deleted"]["work_orders"] == 1 and j["deleted"]["work_order_status_history"] == 1 and j["deleted"]["business_scenarios"] == 1
    assert _count(db, WorkOrder, sa) == 0 and _count(db, BusinessScenario, sa) == 0
    assert _count(db, WorkOrder, sb) == 1  # the other visitor is untouched
    # audit: append-only - nothing deleted, the reset itself was appended
    audit_after = list(db.execute(select(AuditLog).where(AuditLog.session_id == sa).order_by(AuditLog.id)).scalars())
    assert len(audit_after) == audit_before + 1 and audit_after[-1].action == "demo.session_reset" and "kept" in audit_after[-1].after_json
    assert verify_chain(db) == (True, None)
    assert db.execute(select(func.count()).select_from(WorkOrder).where(WorkOrder.session_id.is_(None))).scalar_one() == 117  # baseline intact
    assert client.get(WO, params={"as_of": FOCUS, "mine_only": True}, headers=a).json()["total"] == 0
    again = client.post("/api/v1/demo/session/reset", headers=a).json()
    assert sum(again["deleted"].values()) == 0  # idempotent


def test_reset_all_is_admin_only_and_clears_every_visitor(client, db):
    a, b = hdr("maintenance_engineer"), hdr("factory_manager")
    _make_wo(client, a)
    _make_wo(client, b)
    for role in ("factory_manager", "maintenance_engineer", "executive", "public_viewer"):
        assert client.post("/api/v1/demo/reset-all", headers=hdr(role)).status_code == 403
    r = client.post("/api/v1/demo/reset-all", headers=hdr("system_admin"))
    assert r.status_code == 200
    j = r.json()
    assert j["sessions_cleared"] >= 2 and j["deleted"]["work_orders"] >= 2
    assert db.execute(select(func.count()).select_from(WorkOrder).where(WorkOrder.session_id.is_not(None))).scalar_one() == 0
    assert db.execute(select(func.count()).select_from(WorkOrder).where(WorkOrder.session_id.is_(None))).scalar_one() == 117
    assert db.execute(select(AuditLog.action).order_by(AuditLog.id.desc()).limit(1)).scalar_one() == "demo.reset_all" and verify_chain(db) == (True, None)


def test_retention_purge_removes_only_idle_sessions(client, db):
    idle, active = hdr("maintenance_engineer"), hdr("maintenance_engineer")
    _make_wo(client, idle)
    _make_wo(client, active)
    now = datetime.now(UTC)
    assert sum(purge_idle_sessions(db, max_idle_hours=72, now=now).values()) == 0  # nobody has been idle for 3 days
    last_active = db.execute(select(func.max(AuditLog.ts)).where(AuditLog.session_id == idle["X-Demo-Session"])).scalar_one()
    t = purge_idle_sessions(db, max_idle_hours=1, now=last_active + timedelta(hours=2))  # both are idle by then
    assert t["work_orders"] >= 2
    assert _count(db, WorkOrder, idle["X-Demo-Session"]) == 0 and _count(db, WorkOrder, active["X-Demo-Session"]) == 0


# ---------------------------------------------------------------- tick
def test_tick_advances_by_step_and_is_labelled_simulation(client):
    r = client.post("/api/v1/demo/tick", params={**PRESS, "as_of": "2026-11-18T09:00:00Z"}, json={"step_minutes": 90}, headers=hdr("public_viewer", None))
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["previous_as_of"] == "2026-11-18T09:00:00Z" and j["next_as_of"] == "2026-11-18T10:30:00Z" and j["wrapped"] is False
    assert "SIMULATION" in j["label"] and j["mode"] == "simulation" and j["scenario_id"] == "PRESS_VIBRATION_ANOMALY"
    assert {k["key"] for k in j["headline"]} >= {"throughput_tph", "oer_4h_pct", "active_alerts", "primary_equipment_risk_index"}
    assert all(k["provenance"]["as_of"] == j["next_as_of"] and k["provenance"]["kind"] == "synthetic_actual" for k in j["headline"])


def test_tick_loops_inside_the_scenario_window_and_server_is_stateless(client):
    h = hdr("public_viewer", None)
    last = client.post("/api/v1/demo/tick", params={**PRESS, "as_of": "2026-11-20T16:55:00Z"}, json={"step_minutes": 10}, headers=h).json()
    assert last["wrapped"] is True and last["next_as_of"] == "2026-11-15T17:00:00Z" == last["window_start"] and last["new_alert_ids"] == []  # back to the scenario start
    same = client.post("/api/v1/demo/tick", params={**PRESS, "as_of": "2026-11-20T16:55:00Z"}, json={"step_minutes": 10}, headers=h).json()
    assert same["next_as_of"] == last["next_as_of"]  # no server-side cursor: same request, same answer
    whole = client.post("/api/v1/demo/tick", params={"as_of": "2026-11-20T16:55:00Z"}, json={"step_minutes": 10}, headers=h).json()
    assert whole["wrapped"] is True and whole["next_as_of"] == "2026-07-23T17:00:00Z"  # dataset window start


def test_tick_reports_alerts_raised_in_the_step_and_never_beyond_the_clock(client):
    j = client.post("/api/v1/demo/tick", params={"as_of": "2026-11-19T03:10:00Z"}, json={"step_minutes": 20}, headers=hdr("public_viewer", None)).json()
    assert j["new_alert_ids"] == [18]  # ALR-20261119-0018 (critical vibration) is raised at 03:20 UTC
    assert j["next_as_of"] == "2026-11-19T03:30:00Z"
    quiet = client.post("/api/v1/demo/tick", params={"as_of": EARLY}, json={"step_minutes": 10}, headers=hdr("public_viewer", None)).json()
    assert quiet["new_alert_ids"] == []


def test_tick_input_validation(client):
    for body in ({"step_minutes": 0}, {"step_minutes": 241}, {"step_minutes": "ten"}):
        assert client.post("/api/v1/demo/tick", json=body, headers=hdr("public_viewer", None)).status_code == 422


def test_roles_are_labelled_as_simulated_viewpoints(client):
    j = client.get("/api/v1/demo/roles").json()
    assert len(j["items"]) == 8 and "not authentication" in j["label"].lower() and "not production authentication" in j["notice"].lower()
    ctx = client.get("/api/v1/demo/context", headers=hdr("public_viewer", None)).json()
    assert ctx["latest_data_ts"].startswith("2026-11-20T17:00:00")


# ---------------------------------------------------------------- contract completeness and demo-clock discipline
def test_every_backend_b_operation_is_implemented_and_x_permission_matches():
    mine = [(p, r) for p, r in iter_contract_routes() if (r.openapi_extra or {}).get("x-owner") == "backend-b"]
    assert len(mine) >= 36
    assert [p for p, r in mine if r.openapi_extra["x-status"] != "implemented"] == []  # no 501 stubs left


def test_no_timestamp_after_the_demo_clock_in_any_actual_data_response(client):
    """Sweep the actual-data endpoints at an early clock: no ISO timestamp later than as_of may appear."""
    as_of = "2026-09-15T08:00:00Z"
    h = hdr("public_viewer", None)
    urls = [
        "/api/v1/maintenance/equipment", "/api/v1/maintenance/equipment/18", "/api/v1/maintenance/equipment/18/health", "/api/v1/maintenance/equipment/18/sensors",
        "/api/v1/maintenance/equipment/16/history", "/api/v1/maintenance/recommendations", "/api/v1/maintenance/downtime", "/api/v1/maintenance/technicians",
        "/api/v1/work-orders", "/api/v1/work-orders/1/audit", "/api/v1/traceability/lots", "/api/v1/traceability/deliveries", "/api/v1/traceability/forward?supplier_id=2",
        "/api/v1/traceability/backward?lot_id=50",
    ]
    iso = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
    for url in urls:
        sep = "&" if "?" in url else "?"
        r = client.get(f"{url}{sep}as_of={as_of}", headers=h)
        assert r.status_code == 200, (url, r.status_code, r.text[:200])
        stamps = [m for m in iso.findall(r.text) if m + "Z" > as_of]
        assert stamps == [], (url, stamps[:3])
    assert err(client.get("/api/v1/work-orders/117", params={"as_of": as_of}, headers=h)) == "not_found"
