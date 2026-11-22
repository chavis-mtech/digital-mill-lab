"""Shared helpers for the QA / security / integration suites (owner: qa-security).

Everything here is generated from the live OpenAPI document or from the database, so new endpoints are picked up
automatically by the sweeps instead of being hand-listed.
"""

from __future__ import annotations

import re
import shutil
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.db.session import get_sessionmaker
from app.main import create_app
from app.models.enums import Role

REPO = Path(__file__).resolve().parents[4]
DEV = REPO / "data" / "dev"
SNAPSHOTS = [DEV / "snapshot-with-ml-v2.db", DEV / "snapshot-with-ml.db"]
QA_DB = DEV / "qa.db"

ROLES: list[str] = [r.value for r in Role]

# Operations that are intentionally reachable without a permission dependency.
# Anything else without `x-permission` in the OpenAPI document is a defect (test_authz_matrix).
PUBLIC_OPERATIONS = {
    ("GET", "/health"),
    ("GET", "/ready"),
    ("GET", "/api/v1/meta"),
    ("GET", "/api/v1/demo/roles"),
}

FORBIDDEN_IN_BODIES = (
    "Traceback (most recent call last)",
    'File "',
    "site-packages",
    "/Users/",
    "/home/",
    "/private/var",
    ".py\", line",
    "sqlalchemy.",
    "sqlite3.",
    "OperationalError",
    "IntegrityError",
    "ProgrammingError",
    "SELECT ",
    "INSERT INTO",
    "pydantic_core",
    "starlette.",
    "uvicorn",
)


def _has_ml_rows(p: Path) -> bool:
    import sqlite3  # noqa: PLC0415

    try:
        con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        try:
            return (con.execute("select count(*) from anomaly_events").fetchone() or (0,))[0] > 0
        finally:
            con.close()
    except sqlite3.Error:
        return False


def snapshot_path() -> Path | None:
    """Seeded + ML-trained source DB for the QA suites (copied, never written).

    Order: $DML_TEST_SNAPSHOT, the dev snapshots, then - for a clean clone / CI - data/dev/ml.db (CI trains there) or
    data/demo.db after `make demo-data` (seed + models write into the same file). Only DBs that contain ML rows qualify.
    """
    import os  # noqa: PLC0415

    env = os.environ.get("DML_TEST_SNAPSHOT")
    candidates = ([Path(env)] if env else []) + SNAPSHOTS + [DEV / "ml.db", REPO / "data" / "demo.db"]
    for p in candidates:
        if p.exists() and p.stat().st_size > 1_000_000 and _has_ml_rows(p):
            return p
    return None


def prepare_db(name: str) -> str:
    """Fresh copy of the seeded + ML snapshot at data/dev/<name>.db (the canonical data/demo.db is never touched)."""
    src = snapshot_path()
    if src is None:
        pytest.skip("no seeded + ML-trained database found (run `make demo-data`)")
    dst = DEV / f"{name}.db"
    for suffix in ("", "-wal", "-shm", "-journal"):
        Path(str(dst) + suffix).unlink(missing_ok=True)
    shutil.copyfile(src, dst)
    return f"sqlite:///{dst}"


def make_client(db_url: str, **overrides: Any) -> TestClient:
    base = {"database_url": db_url, "rate_limit_enabled": False, "app_env": "test", "log_level": "ERROR"}
    base.update(overrides)
    # raise_server_exceptions=False: an unhandled exception must surface as the 500 envelope, like in production
    return TestClient(create_app(Settings(**base)), raise_server_exceptions=False)


def collect_ops() -> tuple[list[Op], dict]:
    """Operations + OpenAPI document at import time (pytest.mark.parametrize needs them during collection; no DB access)."""
    app = create_app(Settings(database_url=f"sqlite:///{QA_DB}", rate_limit_enabled=False, app_env="test", log_level="ERROR"))
    spec = app.openapi()
    return load_ops(spec), spec


def new_session() -> str:
    return str(uuid.uuid4())


def hdr(role: str = "public_viewer", session: str | None = None) -> dict[str, str]:
    h = {"X-Demo-Role": role}
    if session:
        h["X-Demo-Session"] = session
    return h


# --------------------------------------------------------------------------- OpenAPI -> operations


@dataclass(frozen=True)
class Op:
    method: str
    path: str
    operation_id: str
    permission: str | None
    roles: tuple[str, ...]  # declared x-roles ("*" = no check)
    status: str | None
    body_schema: dict | None
    body_kind: str | None  # "json" | "multipart" | None
    query: tuple[dict, ...] = field(default_factory=tuple)
    path_params: tuple[str, ...] = field(default_factory=tuple)

    @property
    def id(self) -> str:
        return f"{self.method} {self.path}"

    @property
    def is_write(self) -> bool:
        return self.method != "GET"


def load_ops(spec: dict) -> list[Op]:
    ops: list[Op] = []
    for path, item in spec["paths"].items():
        for method, op in item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            body = None
            kind = None
            rb = op.get("requestBody")
            if rb:
                content = rb.get("content", {})
                if "application/json" in content:
                    body, kind = content["application/json"].get("schema"), "json"
                elif "multipart/form-data" in content:
                    body, kind = content["multipart/form-data"].get("schema"), "multipart"
            params = op.get("parameters", [])
            ops.append(
                Op(
                    method=method.upper(),
                    path=path,
                    operation_id=op["operationId"],
                    permission=op.get("x-permission"),
                    roles=tuple(op.get("x-roles", ())),
                    status=op.get("x-status"),
                    body_schema=body,
                    body_kind=kind,
                    query=tuple(p for p in params if p["in"] == "query"),
                    path_params=tuple(p["name"] for p in params if p["in"] == "path"),
                )
            )
    return sorted(ops, key=lambda o: (o.path, o.method))


def resolve(schema: dict | None, components: dict) -> dict:
    schema = schema or {}
    seen = 0
    while "$ref" in schema and seen < 20:
        schema = components[schema["$ref"].rsplit("/", 1)[-1]]
        seen += 1
    return schema


def example_value(schema: dict | None, components: dict, depth: int = 0) -> Any:
    """Minimal schema-valid example (required properties only). Good enough to reach the handler, not to succeed."""
    s = resolve(schema, components)
    if depth > 6:
        return None
    if "const" in s:
        return s["const"]
    if "enum" in s:
        return s["enum"][0]
    if "default" in s and s["default"] is not None:
        return s["default"]
    for key in ("anyOf", "oneOf"):
        if key in s:
            options = [o for o in s[key] if resolve(o, components).get("type") != "null"]
            return example_value(options[0], components, depth + 1) if options else None
    if "allOf" in s:
        merged: dict = {}
        for part in s["allOf"]:
            v = example_value(part, components, depth + 1)
            if isinstance(v, dict):
                merged.update(v)
        return merged
    t = s.get("type")
    if t == "object" or "properties" in s:
        out = {}
        for name, prop in (s.get("properties") or {}).items():
            if name in (s.get("required") or []):
                out[name] = example_value(prop, components, depth + 1)
        return out
    if t == "array":
        n = s.get("minItems", 0)
        return [example_value(s.get("items"), components, depth + 1) for _ in range(n)]
    if t == "string":
        fmt = s.get("format")
        if fmt == "uuid":
            return str(uuid.uuid4())
        if fmt == "date-time":
            return "2026-11-20T08:00:00Z"
        if fmt == "date":
            return "2026-11-20"
        n = max(s.get("minLength", 1), 1)
        return "x" * min(n, 50)
    if t == "integer":
        return int(s.get("minimum", s.get("exclusiveMinimum", 0) + 1 if "exclusiveMinimum" in s else 1))
    if t == "number":
        return float(s.get("minimum", 1.0))
    if t == "boolean":
        return False
    return None


# --------------------------------------------------------------------------- sample path ids


def discover_path_ids(client: TestClient, scenario_id: str = "PRESS_VIBRATION_ANOMALY") -> dict[str, Any]:
    """Real ids for every path parameter name used in the contract (so GET sweeps hit real rows, not 404s)."""
    h = hdr("system_admin")
    q = {"scenario_id": scenario_id}

    def first(path: str, key: str = "id", params: dict | None = None):
        r = client.get(path, params={**q, **(params or {})}, headers=h)
        items = (r.json() or {}).get("items") or []
        return items[0].get(key) if items else None

    ids: dict[str, Any] = {
        "alert_id": first("/api/v1/alerts"),
        "anomaly_id": first("/api/v1/ai/anomalies/equipment"),
        "equipment_id": 18,
        "work_order_id": first("/api/v1/work-orders"),
        "supplier_id": first("/api/v1/logistics/suppliers"),
        "lot_id": first("/api/v1/traceability/lots"),
        "recommendation_id": first("/api/v1/maintenance/recommendations"),
        "slug": first("/api/v1/kb/documents", "slug"),
        "name": "oer_forecast",
        "code": scenario_id,
        "report_type": "executive",
        "copilot_session_id": 1,
        "ref": "kb:demo-data-dictionary#0",
        "stage_code": "PRESSING",
    }
    stages = client.get("/api/v1/process/stages", params=q, headers=h).json().get("stages") or []
    if stages:
        ids["stage_code"] = stages[0].get("code") or stages[0].get("stage_code") or ids["stage_code"]
    models = client.get("/api/v1/ai/models", params=q, headers=h).json().get("items") or []
    if models:
        ids["name"] = models[0].get("name") or models[0].get("model_name") or ids["name"]
    return ids


def fill_path(path: str, ids: dict[str, Any]) -> str:
    def repl(m: re.Match) -> str:
        return str(ids.get(m.group(1), 1))

    return re.sub(r"\{([^}]+)\}", repl, path)


# --------------------------------------------------------------------------- scenario focus times


def focus_times(db_url: str) -> dict[str, datetime]:
    from app.models.platform import ScenarioRun  # noqa: PLC0415

    with get_sessionmaker(db_url)() as s:
        rows = s.execute(select(ScenarioRun.code, ScenarioRun.focus_ts)).all()
    return {code: ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts for code, ts in rows}


def iso(ts: datetime) -> str:
    return ts.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- response inspection

_ISO_TS = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?$")


def parse_ts(value: str) -> datetime | None:
    if not isinstance(value, str) or not _ISO_TS.match(value):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00").replace(" ", "T"))
    except ValueError:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def walk(obj: Any, path: str = "$") -> Iterator[tuple[str, str | None, Any, dict | None]]:
    """Yield (json_path, key, value, parent_dict) for every scalar in the document."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}"
            if isinstance(v, dict | list):
                yield from walk(v, p)
            else:
                yield p, k, v, obj
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            p = f"{path}[{i}]"
            if isinstance(v, dict | list):
                yield from walk(v, p)
            else:
                yield p, None, v, None


def leaks_in(text: str) -> list[str]:
    found = [needle for needle in FORBIDDEN_IN_BODIES if needle in text]
    if str(REPO) in text:
        found.append("<repo path>")
    return found


def assert_clean_error(resp, *, status: int | None = None, code: str | None = None) -> dict:
    """Every non-2xx body must be the error envelope and must not leak internals."""
    if status is not None:
        assert resp.status_code == status, (resp.status_code, resp.text[:300])
    j = resp.json()
    assert set(j) == {"error"}, j
    assert set(j["error"]) == {"code", "message", "details"}, j
    if code is not None:
        assert j["error"]["code"] == code, j
    assert not leaks_in(resp.text), (leaks_in(resp.text), resp.text[:400])
    return j["error"]
