"""Database writing + content checksum.

Rows carry explicit integer ids (deterministic FK wiring without flushes). Inserts go through SQLAlchemy Core in
FK-dependency order (portable). sensor_readings on SQLite uses a raw executemany fast path with the exact text
format SQLAlchemy's SQLite DATETIME type stores ('YYYY-MM-DD HH:MM:SS.ffffff', UTC) - verified by a test.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

import numpy as np
from sqlalchemy import Engine, func, select, text

import app.models  # noqa: F401  (registers all tables)
from app.db.base import Base

# Tables owned (written) by the data engine.
OWNED_TABLES = [
    "companies", "facilities", "production_lines", "process_stages", "equipment", "sensors", "sensor_readings",
    "suppliers", "plantations", "truck_trips", "queue_events", "weighbridge_tickets", "ffb_deliveries", "ffb_batches",
    "production_shifts", "production_batches", "batch_inputs", "process_hourly", "cpo_output_lots", "lot_compositions",
    "byproduct_outputs", "quality_measurements", "technicians", "work_orders", "work_order_status_history",
    "maintenance_events", "energy_consumption", "prices", "alerts", "audit_logs", "scenario_runs", "injected_events",
]
# Tables the data engine must NOT write (ML / copilot / visitor-session owned).
FORBIDDEN_TABLES = ["ai_predictions", "model_registry", "anomaly_events", "ai_recommendations", "kb_documents", "kb_chunks",
                    "alert_status_changes", "anomaly_status_changes", "recommendation_decisions", "business_scenarios",
                    "copilot_sessions", "copilot_messages"]


def is_empty(engine: Engine) -> bool:
    from sqlalchemy import inspect

    if "facilities" not in inspect(engine).get_table_names():
        return True
    with engine.connect() as c:
        return (c.execute(select(func.count()).select_from(Base.metadata.tables["facilities"])).scalar() or 0) == 0


def reset_schema(engine: Engine) -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def write_all(engine: Engine, tables: dict[str, list[dict]], readings: dict | None) -> dict[str, int]:
    counts: dict[str, int] = {}
    sqlite = engine.dialect.name == "sqlite"
    with engine.begin() as conn:
        if sqlite:
            conn.exec_driver_sql("PRAGMA synchronous=OFF")
        for t in Base.metadata.sorted_tables:
            if t.name == "sensor_readings":
                if readings is not None:
                    counts[t.name] = _write_readings(conn, sqlite, readings)
                continue
            rows = tables.get(t.name)
            if not rows:
                continue
            for k in range(0, len(rows), 20000):
                conn.execute(t.insert(), rows[k:k + 20000])
            counts[t.name] = len(rows)
    return counts


def _write_readings(conn, sqlite: bool, readings: dict) -> int:
    sid, ts_text, ts_dt, val, qual = readings["sensor_id"], readings["ts_text"], readings["ts_dt"], readings["value"], readings["quality"]
    n = len(sid)
    ids = np.arange(1, n + 1)
    step = 200000
    if sqlite:
        raw = conn.connection.driver_connection
        cur = raw.cursor()
        for k in range(0, n, step):
            sl = slice(k, k + step)
            cur.executemany("INSERT INTO sensor_readings (id, sensor_id, ts, value, quality) VALUES (?, ?, ?, ?, ?)",
                            zip(ids[sl].tolist(), sid[sl].tolist(), ts_text[sl].tolist(), val[sl].tolist(), qual[sl].tolist(), strict=True))
        cur.close()
    else:
        t = Base.metadata.tables["sensor_readings"]
        for k in range(0, n, step):
            sl = slice(k, k + step)
            conn.execute(t.insert(), [{"id": i, "sensor_id": s, "ts": d, "value": v, "quality": q}
                                      for i, s, d, v, q in zip(ids[sl].tolist(), sid[sl].tolist(), ts_dt[sl].tolist(), val[sl].tolist(), qual[sl].tolist(), strict=True)])
    return n


def _norm(v) -> str:
    if v is None:
        return "~"
    if isinstance(v, float):
        return repr(round(v, 6))
    if hasattr(v, "isoformat"):
        s = v.isoformat(sep=" ") if hasattr(v, "hour") else v.isoformat()
        if hasattr(v, "hour"):
            s = s.replace("+00:00", "")
            if "." not in s:
                s += ".000000"
        return s
    if isinstance(v, bool):
        return "1" if v else "0"
    return str(v)


def content_checksum(engine: Engine, tables: Iterable[str] = OWNED_TABLES) -> tuple[str, dict[str, str]]:
    """sha256 over every owned table's rows ordered by id (canonical text form, backend-independent for SQLite text dates)."""
    overall = hashlib.sha256()
    per: dict[str, str] = {}
    with engine.connect() as conn:
        for name in sorted(tables):
            h = hashlib.sha256()
            cols = [c.name for c in Base.metadata.tables[name].columns]
            res = conn.execute(text(f"SELECT {', '.join(cols)} FROM {name} ORDER BY id"))  # noqa: S608 - fixed table names
            while True:
                chunk = res.fetchmany(50000)
                if not chunk:
                    break
                h.update("\n".join("|".join(_norm(v) for v in row) for row in chunk).encode("utf-8"))
                h.update(b"\n")
            per[name] = h.hexdigest()
            overall.update(f"{name}:{per[name]}\n".encode())
    return overall.hexdigest(), per
