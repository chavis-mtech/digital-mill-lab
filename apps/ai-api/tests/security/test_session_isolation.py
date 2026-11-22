"""Session isolation sweep + audit hash-chain tamper tests (QA item 2).

ADR-006: mutable records are scoped by X-Demo-Session; the seeded rows are a shared read-only baseline.
Every session-scoped read/write endpoint is exercised with two visitors (A, B) and an anonymous caller:
  * A's rows are never visible to B or to the anonymous caller (lists, detail, audit trail, effective status),
  * seeded rows are visible to everyone and are never changed by visitor activity (row-level fingerprint of the DB),
  * reset removes only the caller's rows and appends (never deletes) audit rows,
  * the audit hash chain verifies after all of it, and tampering with the database is detected.
A scratch copy of the QA database is used so that destructive tests cannot disturb other suites.
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from app.db.session import get_engine, get_sessionmaker
from app.services.audit import GENESIS, compute_hash, verify_chain

from .support import REPO, assert_clean_error, hdr, make_client, new_session, prepare_db

F = "2026-11-20T08:00:00Z"  # PRESS_VIBRATION_ANOMALY focus: PRS-03 critical, ML anomaly 162, alert 83, recommendation 9001802
P = {"as_of": F}
ALERT, ANOMALY, REC, EQUIP = 83, 162, 9001802, 18


@pytest.fixture(scope="module")
def iso_url() -> str:
    return prepare_db("qa-iso")


@pytest.fixture(scope="module")
def iso(iso_url):
    return make_client(iso_url)


def _db_path(url: str) -> str:
    return url.removeprefix("sqlite:///")


def _counts(path: str) -> dict[str, int]:
    con = sqlite3.connect(path)
    try:
        names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'")]
        return {n: con.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in names}
    finally:
        con.close()


def _null_counts(path: str) -> dict[str, int]:
    con = sqlite3.connect(path)
    try:
        out = {}
        for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
            if "session_id" in [r[1] for r in con.execute(f'PRAGMA table_info("{name}")')]:
                out[name] = con.execute(f'SELECT COUNT(*) FROM "{name}" WHERE session_id IS NULL').fetchone()[0]
        return out
    finally:
        con.close()


def _baseline_fingerprint(path: str, max_rows: int = 60_000) -> dict[str, str]:
    """Content hash of every *shared baseline* row: session_id IS NULL rows of scoped tables, all rows of the others.

    Large time-series tables (> max_rows) are covered by the row-count check only.
    """
    con = sqlite3.connect(path)
    out: dict[str, str] = {}
    try:
        for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
            cols = [r[1] for r in con.execute(f'PRAGMA table_info("{name}")')]
            if con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] > max_rows:
                continue
            where = ""
            if "session_id" in cols:
                where = " WHERE session_id IS NULL"
            if name == "ai_recommendations":
                where = " WHERE id < 9000000"  # lazily created catalog rows (documented) are excluded
            if name == "audit_logs":
                where = " WHERE id <= 575"  # append-only: the seeded prefix must stay byte-identical
            h = hashlib.sha256()
            for row in con.execute(f'SELECT * FROM "{name}"{where} ORDER BY 1'):
                h.update(repr(row).encode())
            out[name] = h.hexdigest()
        return out
    finally:
        con.close()


def _visitor_actions(client, s: str, tag: str) -> dict:
    """One visitor performs every kind of session-scoped write. Returns the created ids."""
    me = hdr("maintenance_engineer", s)
    ex = hdr("executive", s)
    wo = client.post("/api/v1/work-orders", params=P, headers=me, json={"equipment_id": EQUIP, "title": f"{tag} work order", "confirm": True, "alert_id": ALERT, "source_type": "alert"})
    assert wo.status_code == 201, wo.text
    wid = wo.json()["id"]
    assert client.post(f"/api/v1/work-orders/{wid}/assign", params=P, headers=me, json={"technician_id": 1}).status_code == 200
    assert client.post("/api/v1/work-orders/117/assign", params=P, headers=me, json={"technician_id": 2}).status_code == 200  # copy-on-write of a SEEDED order
    assert client.post(f"/api/v1/ai/anomalies/{ANOMALY}/status", params=P, headers=me, json={"to_status": "verified", "note": tag}).status_code == 200
    assert client.post(f"/api/v1/maintenance/recommendations/{REC}/decision", params=P, headers=me, json={"decision": "approved", "note": tag}).status_code == 200
    sc = client.post("/api/v1/scenarios/saved", params=P, headers=ex, json={"kind": "production", "name": f"{tag} scenario", "inputs": {"a": 1}, "outputs": {"b": 2}})
    assert sc.status_code == 201, sc.text
    chat = client.post("/api/v1/copilot/chat", params=P, headers=hdr("public_viewer", s), json={"message": "How many trucks are waiting now?", "lang": "en"})
    assert chat.status_code == 200, chat.text
    return {"wo": wid, "scenario": sc.json()["id"], "copilot": chat.json()["copilot_session_id"], "session": s}


@pytest.fixture(scope="module")
def two_visitors(iso, iso_url):
    """A and B act; the DB is fingerprinted before. Module-scoped: the isolation tests below only read."""
    before_counts = _counts(_db_path(iso_url))
    before_fp = _baseline_fingerprint(_db_path(iso_url))
    before_null = _null_counts(_db_path(iso_url))
    a, b = new_session(), new_session()
    ids_a = _visitor_actions(iso, a, "visitor-A")
    ids_b = _visitor_actions(iso, b, "visitor-B")
    return {"a": ids_a, "b": ids_b, "before_counts": before_counts, "before_fp": before_fp, "before_null": before_null}


# ---------------------------------------------------------------------------------------------------- visibility


def test_a_rows_are_invisible_to_b_and_to_anonymous(iso, two_visitors):
    a, b = two_visitors["a"], two_visitors["b"]
    for who in (hdr("public_viewer", b["session"]), hdr("public_viewer")):
        wos = iso.get("/api/v1/work-orders", params=P, headers=who).json()
        ids = {i["id"] for i in wos["items"]}
        assert a["wo"] not in ids, "visitor A's work order leaked into another view"
        # anonymous sees exactly the 117 seeded orders; B sees those + its own only
        expected = 117 + (1 if who.get("X-Demo-Session") else 0)
        assert wos["total"] == expected, (wos["total"], expected)
        r = iso.get(f"/api/v1/work-orders/{a['wo']}", params=P, headers=who)
        assert_clean_error(r, status=404, code="not_found")
        r = iso.get(f"/api/v1/work-orders/{a['wo']}/audit", params=P, headers=who)
        assert_clean_error(r, status=404, code="not_found")
        saved = iso.get("/api/v1/scenarios/saved", params=P, headers=who).json()["items"]
        assert all(s["name"] != "visitor-A scenario" for s in saved)
        sessions = iso.get("/api/v1/copilot/sessions", params=P, headers=who).json()["items"]
        assert a["copilot"] not in {s["id"] for s in sessions}
        r = iso.get(f"/api/v1/copilot/sessions/{a['copilot']}", params=P, headers=who)
        assert r.status_code == 404, r.text
        assert_clean_error(r)


def test_effective_status_of_seeded_rows_is_per_visitor(iso, two_visitors):
    """Copy-on-write (ADR-014): A's anomaly verification / recommendation decision / work-order clone is A's alone."""
    a, b = two_visitors["a"], two_visitors["b"]
    anon = hdr("public_viewer")
    fresh = hdr("public_viewer", new_session())
    assert iso.get(f"/api/v1/ai/anomalies/{ANOMALY}", params=P, headers=hdr("public_viewer", a["session"])).json()["status"] == "verified"
    assert iso.get(f"/api/v1/ai/anomalies/{ANOMALY}", params=P, headers=anon).json()["status"] != "verified"
    assert iso.get(f"/api/v1/ai/anomalies/{ANOMALY}", params=P, headers=fresh).json()["status"] != "verified"
    recs = lambda h: {r["id"]: r["status"] for r in iso.get("/api/v1/maintenance/recommendations", params=P, headers=h).json()["items"]}  # noqa: E731
    assert recs(hdr("public_viewer", a["session"]))[REC] != recs(anon)[REC]
    assert recs(fresh)[REC] == recs(anon)[REC]
    # alert + equipment status follow the visitor's own work order (alert -> in_progress, PRS-03 -> work_order_open)
    alert_of = lambda h: iso.get(f"/api/v1/alerts/{ALERT}", params=P, headers=h).json()["status"]  # noqa: E731
    assert alert_of(hdr("public_viewer", a["session"])) == "in_progress"
    assert alert_of(anon) == alert_of(fresh) == "new"
    prs = lambda h: iso.get(f"/api/v1/maintenance/equipment/{EQUIP}", params=P, headers=h).json()["maintenance_status"]  # noqa: E731
    assert prs(hdr("public_viewer", a["session"])) in {"work_order_open", "assigned"}  # A created and assigned its order
    assert prs(anon) == prs(fresh) == "none"
    # the clone of seeded WO 117 exists only for its owner; for others the seeded row is unchanged
    assert iso.get("/api/v1/work-orders/117", params=P, headers=anon).json()["assigned_technician"] == iso.get("/api/v1/work-orders/117", params=P, headers=fresh).json()["assigned_technician"]
    assert b["session"] != a["session"]


def test_seeded_rows_are_visible_to_every_visitor_identically(iso, two_visitors):
    a, b = two_visitors["a"], two_visitors["b"]
    views = {}
    for name, h in (("a", hdr("public_viewer", a["session"])), ("b", hdr("public_viewer", b["session"])), ("fresh", hdr("public_viewer", new_session())), ("anon", hdr("public_viewer"))):
        items = iso.get("/api/v1/work-orders", params={**P, "limit": 200}, headers=h).json()["items"]
        # a visitor who acted on a seeded order sees ITS copy in place of the baseline row (copy-on-write, ADR-014)
        seeded_ids = {i["id"] for i in items if i["is_baseline"]} | {i["cloned_from_id"] for i in items if i["cloned_from_id"]}
        alerts = iso.get("/api/v1/alerts", params={**P, "limit": 200}, headers=h).json()
        views[name] = (seeded_ids, alerts["total"], sorted(i["id"] for i in alerts["items"]))
    assert all(v[0] == set(range(1, 118)) for v in views.values()), {k: len(v[0]) for k, v in views.items()}
    assert views["a"][1:] == views["b"][1:] == views["fresh"][1:] == views["anon"][1:]


def test_foreign_ids_behave_like_missing_ids(iso, two_visitors):
    """No existence oracle: acting on / reading another visitor's id is indistinguishable from an id that never existed."""
    a, b = two_visitors["a"], two_visitors["b"]
    hb = hdr("maintenance_engineer", b["session"])
    ghost = 9_999_999
    for suffix, body in (("", None), ("/audit", None), ("/assign", {"technician_id": 1}), ("/transition", {"to_status": "on_hold"})):
        url = "/api/v1/work-orders/{}" + suffix
        kw = {"json": body} if body else {}
        method = "POST" if body else "GET"
        foreign = iso.request(method, url.format(a["wo"]), params=P, headers=hb, **kw)
        missing = iso.request(method, url.format(ghost), params=P, headers=hb, **kw)
        assert foreign.status_code == missing.status_code == 404, (suffix, foreign.status_code, missing.status_code)
        f, m = foreign.json()["error"], missing.json()["error"]
        assert (f["code"], f["message"]) == (m["code"], m["message"])


def test_visitor_activity_never_modifies_the_shared_baseline(iso_url, two_visitors):
    """Row-level proof: every seeded row is byte-identical after two visitors used every write endpoint."""
    path = _db_path(iso_url)
    after_counts = _counts(path)
    before_counts = two_visitors["before_counts"]
    session_tables = set()
    con = sqlite3.connect(path)
    for name in after_counts:
        if "session_id" in [r[1] for r in con.execute(f'PRAGMA table_info("{name}")')]:
            session_tables.add(name)
    con.close()
    grown = {t for t in after_counts if after_counts[t] != before_counts[t]}
    allowed_growth = session_tables | {"audit_logs", "ai_recommendations"}  # catalog row for rule recommendations: documented lazy write
    assert grown <= allowed_growth, f"tables changed outside the session-scoped set: {sorted(grown - allowed_growth)}"
    assert {"work_orders", "audit_logs", "anomaly_status_changes", "recommendation_decisions", "business_scenarios", "copilot_sessions"} <= grown
    assert after_counts["ai_recommendations"] - before_counts["ai_recommendations"] <= 1  # one catalog row for REC, shared by A and B
    # baseline (session_id IS NULL) row counts of every scoped table are unchanged, also for the tables that grew
    assert _null_counts(path) == two_visitors["before_null"]
    # every row of the shared baseline is byte-identical
    assert _baseline_fingerprint(path) == two_visitors["before_fp"]


def test_audit_log_is_append_only_and_chain_verifies_after_visitor_activity(iso, iso_url, two_visitors):
    with get_sessionmaker(iso_url)() as db:
        assert verify_chain(db) == (True, None)
        n = db.execute(text("SELECT COUNT(*) FROM audit_logs")).scalar_one()
        by_session = dict(db.execute(text("SELECT session_id, COUNT(*) FROM audit_logs GROUP BY session_id")).all())
    assert n > two_visitors["before_counts"]["audit_logs"]
    assert by_session.get(two_visitors["a"]["session"], 0) >= 7 and by_session.get(two_visitors["b"]["session"], 0) >= 7
    a = two_visitors["a"]
    trail = iso.get(f"/api/v1/work-orders/{a['wo']}/audit", params=P, headers=hdr("public_viewer", a["session"])).json()
    assert trail["chain_verified"] is True and len(trail["items"]) >= 3
    # a visitor's trail contains only that visitor's work order
    assert {i["entity_id"] for i in trail["items"] if i["entity_type"] == "work_order"} <= {trail["entity_id"]}


# ---------------------------------------------------------------------------------------------------- reset


def test_reset_removes_only_the_callers_rows_in_every_scoped_table(iso, iso_url, two_visitors):
    a, b = two_visitors["a"], two_visitors["b"]
    path = _db_path(iso_url)
    con = sqlite3.connect(path)
    scoped = [n for (n,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'") if "session_id" in [r[1] for r in con.execute(f'PRAGMA table_info("{n}")')]]
    count = lambda t, s: con.execute(f'SELECT COUNT(*) FROM "{t}" WHERE session_id = ?', (s,)).fetchone()[0]  # noqa: E731
    before_a = {t: count(t, a["session"]) for t in scoped}
    before_b = {t: count(t, b["session"]) for t in scoped}
    audit_total_before = con.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
    assert sum(before_a.values()) > 5 and sum(before_b.values()) > 5

    r = iso.post("/api/v1/demo/session/reset", headers=hdr("public_viewer", a["session"]))
    assert r.status_code == 200 and r.json()["session_id"] == a["session"]

    for t in scoped:
        if t == "audit_logs":
            continue
        assert count(t, a["session"]) == 0, f"{t} still holds rows of the reset session"
        assert count(t, b["session"]) == before_b[t], f"{t}: reset removed rows of ANOTHER session"
    assert con.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0] == audit_total_before + 1  # appended, never deleted
    con.close()
    # visible effects: A is back to the baseline, B is untouched
    assert iso.get("/api/v1/work-orders", params={**P, "mine_only": True}, headers=hdr("public_viewer", a["session"])).json()["total"] == 0
    assert iso.get("/api/v1/work-orders", params={**P, "mine_only": True}, headers=hdr("public_viewer", b["session"])).json()["total"] == 2  # B's new order + its copy-on-write clone of seeded WO 117
    assert iso.get(f"/api/v1/alerts/{ALERT}", params=P, headers=hdr("public_viewer", a["session"])).json()["status"] == "new"
    assert iso.get(f"/api/v1/alerts/{ALERT}", params=P, headers=hdr("public_viewer", b["session"])).json()["status"] == "in_progress"
    with get_sessionmaker(iso_url)() as db:
        assert verify_chain(db) == (True, None)
    assert _baseline_fingerprint(path) == two_visitors["before_fp"]


def test_reset_needs_a_session_and_cannot_target_another_one(iso):
    assert_clean_error(iso.post("/api/v1/demo/session/reset", headers=hdr("public_viewer")), status=428, code="session_required")
    # the target session is only ever taken from the caller's own header: a session id in query/body is ignored
    victim, attacker = new_session(), new_session()
    wid = iso.post("/api/v1/work-orders", params=P, headers=hdr("maintenance_engineer", victim), json={"equipment_id": EQUIP, "title": "victim order", "confirm": True}).json()["id"]
    r = iso.post("/api/v1/demo/session/reset", params={"session_id": victim, "x_demo_session": victim}, json={"session_id": victim}, headers=hdr("public_viewer", attacker))
    assert r.status_code == 200 and r.json()["session_id"] == attacker
    assert iso.get(f"/api/v1/work-orders/{wid}", params=P, headers=hdr("public_viewer", victim)).status_code == 200


def test_reset_all_is_admin_only_and_keeps_baseline_and_audit(iso, iso_url, two_visitors):
    for role in ("public_viewer", "executive", "factory_manager", "maintenance_engineer", "ai_analyst", "logistics_officer", "production_engineer"):
        assert_clean_error(iso.post("/api/v1/demo/reset-all", headers=hdr(role, new_session())), status=403, code="forbidden")
    audit_before = _counts(_db_path(iso_url))["audit_logs"]
    r = iso.post("/api/v1/demo/reset-all", headers=hdr("system_admin"))
    assert r.status_code == 200 and r.json()["sessions_cleared"] >= 1
    after = _counts(_db_path(iso_url))
    assert after["audit_logs"] == audit_before + 1 and after["work_orders"] == 117
    with get_sessionmaker(iso_url)() as db:
        assert verify_chain(db) == (True, None)
    assert _baseline_fingerprint(_db_path(iso_url)) == two_visitors["before_fp"]


# ---------------------------------------------------------------------------------------------------- concurrency


def test_concurrent_visitors_do_not_corrupt_each_other_or_the_audit_chain(iso_url):
    """8 visitors create work orders at the same time. Writers are serialised by SQLite: no 5xx, unique codes, valid chain."""
    results: list[tuple[int, str, str | None]] = []
    lock = threading.Lock()
    sessions = [new_session() for _ in range(8)]

    def worker(s: str) -> None:
        c = make_client(iso_url)
        for i in range(4):
            r = c.post("/api/v1/work-orders", params=P, headers=hdr("maintenance_engineer", s), json={"equipment_id": EQUIP, "title": f"concurrent {s[:6]} {i}", "confirm": True})
            code = r.json().get("code") if r.status_code == 201 else r.text[:120]
            with lock:
                results.append((r.status_code, s, code))

    threads = [threading.Thread(target=worker, args=(s,)) for s in sessions]
    [t.start() for t in threads]
    [t.join() for t in threads]
    statuses = [r[0] for r in results]
    assert len(results) == 32
    bad = [r for r in results if r[0] != 201]
    assert not bad, f"{len(bad)}/32 concurrent creates failed: {bad[:3]}"
    codes = [r[2] for r in results]
    assert len(set(codes)) == 32, "duplicate work-order codes under concurrency"
    with get_sessionmaker(iso_url)() as db:
        assert verify_chain(db) == (True, None), "audit chain forked / broken by concurrent writers"
    assert statuses.count(201) == 32


# ---------------------------------------------------------------------------------------------------- tamper


@pytest.fixture
def scratch():
    """Private DB copy per test (unique file name: an engine must never see its file replaced underneath it)."""
    name = f"qa-tamper-{uuid.uuid4().hex[:8]}"
    url = prepare_db(name)
    c = make_client(url)
    s = new_session()
    wid = c.post("/api/v1/work-orders", params=P, headers=hdr("maintenance_engineer", s), json={"equipment_id": EQUIP, "title": "tamper probe", "confirm": True}).json()["id"]
    c.post(f"/api/v1/work-orders/{wid}/assign", params=P, headers=hdr("maintenance_engineer", s), json={"technician_id": 1})
    yield {"url": url, "client": c, "session": s, "wo": wid, "path": _db_path(url)}
    get_engine(url).dispose()
    Path(_db_path(url)).unlink(missing_ok=True)


def _trail(sc):
    return sc["client"].get(f"/api/v1/work-orders/{sc['wo']}/audit", params=P, headers=hdr("public_viewer", sc["session"])).json()


def _first_visitor_row(path: str) -> tuple[int, int]:
    con = sqlite3.connect(path)
    try:
        first = con.execute("SELECT MIN(id) FROM audit_logs WHERE session_id IS NOT NULL").fetchone()[0]
        last = con.execute("SELECT MAX(id) FROM audit_logs").fetchone()[0]
        return first, last
    finally:
        con.close()


def test_intact_chain_verifies_from_genesis(scratch):
    with get_sessionmaker(scratch["url"])() as db:
        assert verify_chain(db) == (True, None)
        assert db.execute(text("SELECT prev_hash FROM audit_logs ORDER BY id LIMIT 1")).scalar_one() == GENESIS
    assert _trail(scratch)["chain_verified"] is True


@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE audit_logs SET after_json = '{\"status\":\"resolved\"}' WHERE id = <VISITOR>",
        "UPDATE audit_logs SET role = 'system_admin' WHERE id = <VISITOR>",
        "UPDATE audit_logs SET action = 'work_order.deleted' WHERE id = <VISITOR>",
        "UPDATE audit_logs SET session_id = NULL WHERE id = <VISITOR>",
        "UPDATE audit_logs SET ts = '2026-01-01 00:00:00.000000' WHERE id = <VISITOR>",
        "UPDATE audit_logs SET after_json = '{\"x\":1}' WHERE id = 10",  # a SEEDED row, far from the visitor's rows
        "UPDATE audit_logs SET hash = '<ZEROS>' WHERE id = <VISITOR>",
        "UPDATE audit_logs SET prev_hash = '<ZEROS>' WHERE id = <VISITOR>",
        "DELETE FROM audit_logs WHERE id = 100",  # a row in the middle of the chain
        "DELETE FROM audit_logs WHERE id = <VISITOR>",
    ],
    ids=["after_json", "role", "action", "session_id", "ts", "seeded_row", "hash", "prev_hash", "delete_middle", "delete_visitor_row"],
)
def test_any_edit_to_the_audit_table_is_detected(scratch, mutation):
    first, _last = _first_visitor_row(scratch["path"])
    con = sqlite3.connect(scratch["path"])
    con.execute(mutation.replace("<VISITOR>", str(first)).replace("<ZEROS>", "0" * 64))
    con.commit()
    con.close()
    with get_sessionmaker(scratch["url"])() as db:
        ok, broken_id = verify_chain(db)
    assert ok is False and broken_id is not None
    # the API exposes the same verdict to the user (trail still readable, flag false)
    trail = _trail(scratch)
    assert trail["chain_verified"] is False


def test_forged_row_with_wrong_hash_is_detected(scratch):
    con = sqlite3.connect(scratch["path"])
    tail = con.execute("SELECT hash FROM audit_logs ORDER BY id DESC LIMIT 1").fetchone()[0]
    con.execute(
        "INSERT INTO audit_logs (ts, session_id, role, actor, action, entity_type, entity_id, before_json, after_json, request_id, demo_as_of, prev_hash, hash) "
        "VALUES ('2026-11-20 08:00:00.000000', NULL, 'system_admin', 'demo:system_admin', 'work_order.forged', 'work_order', '1', NULL, NULL, NULL, NULL, ?, ?)",
        (tail, "f" * 64),
    )
    con.commit()
    con.close()
    with get_sessionmaker(scratch["url"])() as db:
        assert verify_chain(db)[0] is False


def test_documented_limitation_truncating_the_tail_is_not_detectable(scratch):
    """ADR-013: tamper-EVIDENT, not tamper-PROOF. Dropping the newest rows leaves a valid chain (no external anchor)."""
    con = sqlite3.connect(scratch["path"])
    con.execute("DELETE FROM audit_logs WHERE id = (SELECT MAX(id) FROM audit_logs)")
    con.commit()
    con.close()
    with get_sessionmaker(scratch["url"])() as db:
        assert verify_chain(db) == (True, None)


def test_documented_limitation_a_full_rewrite_with_recomputed_hashes_is_not_detectable(scratch):
    """Someone with DB write access who recomputes every hash can rewrite history (ADR-013). SECURITY.md cites this test."""
    from app.models.platform import AuditLog  # noqa: PLC0415
    from app.services.audit import _fields  # noqa: PLC0415

    with get_sessionmaker(scratch["url"])() as db:
        row = db.get(AuditLog, 10)
        row.after_json = '{"rewritten":true}'
        prev = GENESIS
        from sqlalchemy import select  # noqa: PLC0415

        for r in db.execute(select(AuditLog).order_by(AuditLog.id)).scalars():
            r.prev_hash = prev
            r.hash = compute_hash(prev, _fields(r))
            prev = r.hash
        db.commit()
        assert verify_chain(db) == (True, None)


def test_tamper_fixture_uses_a_scratch_copy_not_the_canonical_db(scratch):
    assert "qa-tamper" in scratch["path"] and str(REPO / "data" / "demo.db") != scratch["path"]
