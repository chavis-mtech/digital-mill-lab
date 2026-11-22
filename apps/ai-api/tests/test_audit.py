from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update

from app.models import AuditLog
from app.models.enums import Role
from app.services.audit import GENESIS, verify_chain, write_audit
from app.services.demo_context import DemoContext


def _ctx(role=Role.maintenance_engineer, session="11111111-1111-1111-1111-111111111111"):
    return DemoContext(
        as_of=datetime(2026, 11, 20, 11, tzinfo=UTC),
        as_of_explicit=True,
        session_id=session,
        role=role,
        request_id="req1",
        window_start=datetime(2026, 7, 23, 17, tzinfo=UTC),
        window_end=datetime(2026, 11, 20, 17, tzinfo=UTC),
    )


def test_append_and_chain(db_session):
    ctx = _ctx()
    a = write_audit(db_session, ctx, "work_order.create", "work_order", 1, None, {"status": "open"})
    b = write_audit(db_session, ctx, "work_order.assign", "work_order", 1, {"tech": None}, {"tech": 3})
    c = write_audit(db_session, ctx, "work_order.transition", "work_order", 1, {"status": "assigned"}, {"status": "in_progress"})
    db_session.commit()
    assert a.prev_hash == GENESIS
    assert b.prev_hash == a.hash and c.prev_hash == b.hash
    assert a.session_id == ctx.session_id and a.role == "maintenance_engineer" and a.actor == "demo:maintenance_engineer"
    rows = db_session.execute(select(AuditLog).order_by(AuditLog.id)).scalars().all()
    assert [r.action for r in rows] == ["work_order.create", "work_order.assign", "work_order.transition"]
    assert rows[0].ts.tzinfo is not None
    assert verify_chain(db_session) == (True, None)


def test_tamper_detected(db_session):
    ctx = _ctx()
    write_audit(db_session, ctx, "a", "x", 1, None, {"v": 1})
    b = write_audit(db_session, ctx, "b", "x", 1, None, {"v": 2})
    write_audit(db_session, ctx, "c", "x", 1, None, {"v": 3})
    db_session.commit()
    db_session.execute(update(AuditLog).where(AuditLog.id == b.id).values(after_json='{"v":999}'))
    db_session.commit()
    db_session.expire_all()
    ok, bad_id = verify_chain(db_session)
    assert not ok and bad_id == b.id
