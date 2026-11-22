"""Append-only audit log with a SHA-256 hash chain (tamper evidence).

hash_n = sha256(prev_hash || canonical_json(row fields)). Rows are never updated or deleted - a demo session
reset deletes the session's *business* rows and appends an audit row, it does not touch audit_logs.
Limitation: the chain is linearised by the DB's write serialisation; on PostgreSQL with concurrent writers
take `SELECT ... FOR UPDATE` on the tail or an advisory lock (documented in DECISIONS ADR-013).
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.platform import AuditLog
from app.services.demo_context import DemoContext

GENESIS = "0" * 64


def _canonical(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)


def _ts_str(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC).isoformat(timespec="microseconds")


def compute_hash(prev_hash: str, fields: dict[str, Any]) -> str:
    payload = prev_hash + json.dumps(fields, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _fields(row: AuditLog) -> dict[str, Any]:
    return {
        "ts": _ts_str(row.ts),
        "session_id": row.session_id,
        "role": row.role,
        "actor": row.actor,
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "before": row.before_json,
        "after": row.after_json,
        "request_id": row.request_id,
        "demo_as_of": _ts_str(row.demo_as_of) if row.demo_as_of else None,
    }


def _tail_hash(db: Session) -> str:
    last = db.execute(select(AuditLog.hash).order_by(AuditLog.id.desc()).limit(1)).scalar_one_or_none()
    return last or GENESIS


def write_audit(
    db: Session,
    ctx: DemoContext | None,
    action: str,
    entity_type: str,
    entity_id: Any = None,
    before: Any = None,
    after: Any = None,
    *,
    role: str | None = None,
    session_id: str | None = None,
) -> AuditLog:
    """Append one audit row (caller commits, so it is atomic with the business change)."""
    role_value = role or (ctx.role.value if ctx else "system_admin")
    row = AuditLog(
        ts=datetime.now(UTC),
        session_id=session_id if session_id is not None else (ctx.session_id if ctx else None),
        role=role_value,
        actor=f"demo:{role_value}",
        action=action,
        entity_type=entity_type,
        entity_id=None if entity_id is None else str(entity_id),
        before_json=_canonical(before),
        after_json=_canonical(after),
        request_id=ctx.request_id if ctx else None,
        demo_as_of=ctx.as_of if ctx else None,
    )
    row.prev_hash = _tail_hash(db)
    row.hash = compute_hash(row.prev_hash, _fields(row))
    db.add(row)
    db.flush()
    return row


_COLS = (AuditLog.id, AuditLog.ts, AuditLog.session_id, AuditLog.role, AuditLog.actor, AuditLog.action, AuditLog.entity_type,
         AuditLog.entity_id, AuditLog.before_json, AuditLog.after_json, AuditLog.request_id, AuditLog.demo_as_of, AuditLog.prev_hash,
         AuditLog.hash)


def _walk(db: Session, prev: str, after_id: int = 0) -> tuple[bool, int | None, int, str]:
    """Verify rows with id > after_id starting from `prev`. Returns (ok, broken_id, last_id, last_hash)."""
    last_id = after_id
    q = select(*_COLS).where(AuditLog.id > after_id).order_by(AuditLog.id)
    for r in db.execute(q):  # plain column tuples: ~3x cheaper than ORM objects
        row = SimpleNamespace(**r._mapping)
        if row.prev_hash != prev or compute_hash(prev, _fields(row)) != row.hash:
            return False, row.id, last_id, prev
        prev, last_id = row.hash, row.id
    return True, None, last_id, prev


def verify_chain(db: Session) -> tuple[bool, int | None]:
    """Recompute the whole chain from genesis. Returns (ok, id_of_first_broken_row)."""
    ok, broken, _, _ = _walk(db, GENESIS)
    return ok, broken


# QA-10: the audit endpoint used to re-walk the WHOLE global chain on every request (~10 us/row: ~1 s at 100k rows).
# Up to FULL_VERIFY_MAX_ROWS the full walk is kept (strongest check, < ~0.2 s). Above it, the walk continues from the last
# verified checkpoint (id, hash) remembered per database in this process, after re-checking that the checkpoint row is
# unchanged. Trade-off (documented in SECURITY.md): an edit to a row BEFORE the checkpoint is then only caught by a full walk
# (process restart, `python -m app.seed.validate`, or verify_chain()).
FULL_VERIFY_MAX_ROWS = 20_000
_checkpoints: dict[str, tuple[int, str]] = {}
_cp_lock = threading.Lock()


def verify_chain_cached(db: Session) -> bool:
    key = str(db.get_bind().url)
    n = db.execute(select(func.count()).select_from(AuditLog)).scalar_one()
    with _cp_lock:
        cp = _checkpoints.get(key)
    start_id, prev = 0, GENESIS
    if n > FULL_VERIFY_MAX_ROWS and cp is not None:
        r = db.execute(select(*_COLS).where(AuditLog.id == cp[0])).first()
        row = SimpleNamespace(**r._mapping) if r is not None else None
        # the checkpoint row itself is re-hashed: an edit to its content (or its hash) forces a full walk
        if row is not None and row.hash == cp[1] and compute_hash(row.prev_hash, _fields(row)) == cp[1]:
            start_id, prev = cp
    ok, _, last_id, last_hash = _walk(db, prev, start_id)
    with _cp_lock:
        if ok:
            _checkpoints[key] = (last_id, last_hash)
        else:
            _checkpoints.pop(key, None)
    return ok
