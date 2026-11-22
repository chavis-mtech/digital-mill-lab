"""Input abuse (QA item 5): schema-driven fuzzing of every string / numeric parameter, SQL-injection and path-traversal
payloads in every string parameter and path id, pagination caps, bounds on expensive endpoints, 5xx-free guarantees.

The fuzz driver is generated from the OpenAPI document, so a new endpoint or field is covered automatically.
Pass criteria for every request: no 5xx, error bodies are the envelope, no stack trace / path / SQL in the body, bounded latency,
and (after the GET sweep) the database content is unchanged.

Findings driving code changes: QA-04 (integer ids beyond SQLite's 64-bit range returned 500; now 422 `value_out_of_range`).
"""

from __future__ import annotations

import json
import sqlite3
import time
import urllib.parse
from copy import deepcopy

import pytest

from .support import (
    Op,
    assert_clean_error,
    collect_ops,
    discover_path_ids,
    fill_path,
    hdr,
    leaks_in,
    make_client,
    new_session,
    prepare_db,
    resolve,
)
from .test_authz_matrix import VALID_WRITE_BODIES

OPS, SPEC = collect_ops()
COMP = SPEC["components"]["schemas"]
GETS = [o for o in OPS if o.method == "GET" and o.permission]
JSON_POSTS = [o for o in OPS if o.method == "POST" and o.body_kind == "json" and o.permission]
P = {"as_of": "2026-11-20T08:00:00Z"}
SLOW = 5.0  # seconds: any single abusive request must finish within this

STR_PAYLOADS = [
    "",
    " ",
    "\x00",
    "a\x00b",
    "A" * 10_000,
    "' OR '1'='1",
    "1; DROP TABLE alerts;--",
    "' UNION SELECT name FROM sqlite_master--",
    "../../../../etc/passwd",
    "..\\..\\windows\\win.ini",
    "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
    "....//....//etc/passwd",
    "/etc/passwd",
    "file:///etc/passwd",
    "{{7*7}}",
    "${jndi:ldap://x/a}",
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "\r\nX-Injected: 1",
    "ก" * 3000,
    "\U0001f600" * 500,
    "‮evil‬",
    "%00",
    "%",
    "null",
    "-1",
    "9" * 40,
    "*",
    "`id` $(id) ; ls | cat",
]
INT_PAYLOADS = ["-1", "0", "9223372036854775807", "9223372036854775808", "99999999999999999999999", "1e5", "1.5", "abc", "", "0x10", "+5", "٣", "-9223372036854775809"]
NUM_JSON = [-1, 0, 1, 2**31, 2**63 - 1, 2**63, 2**200, 10**30, 1e308, -1e308, 1e-320, 0.5]
RAW_NUM_TOKENS = ["NaN", "Infinity", "-Infinity", "1e999", "-1e999", "1" + "0" * 400]


@pytest.fixture(scope="module")
def fc():
    return make_client(prepare_db("qa-fuzz"))


@pytest.fixture(scope="module")
def ids(fc):
    return discover_path_ids(fc)


def _counts(path: str) -> dict[str, int]:
    con = sqlite3.connect(path)
    try:
        names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table','index','view') AND name NOT LIKE 'sqlite_%'")]
        out = {}
        for n in names:
            try:
                out[n] = con.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0]
            except sqlite3.Error:
                out[n] = -1  # an index
        return out
    finally:
        con.close()


def _check(r, what: str, elapsed: float, payload: object = None) -> None:
    assert r.status_code < 500, (what, r.status_code, r.text[:200])
    assert elapsed < SLOW, (what, f"{elapsed:.1f}s")
    text = r.text
    if isinstance(payload, str) and payload:
        # an error message may echo the rejected value back (JSON-escaped); that is reflection, not an internal leak
        for form in (payload, json.dumps(payload)[1:-1], json.dumps(payload, ensure_ascii=False)[1:-1], urllib.parse.quote(payload)):
            text = text.replace(form, "")
    assert not leaks_in(text), (what, leaks_in(text))
    assert "root:x:0:0" not in r.text and "[extensions]" not in r.text, what
    if r.status_code >= 400:
        j = r.json()
        assert set(j) == {"error"} and set(j["error"]) == {"code", "message", "details"}, (what, j)


def _param_type(p: dict) -> str:
    s = resolve(p["schema"], COMP)
    if "anyOf" in s:
        s = resolve(next(x for x in s["anyOf"] if resolve(x, COMP).get("type") != "null"), COMP)
    return s.get("type") or ("enum" if "enum" in s else "string")


# ---------------------------------------------------------------------------------------------------- GET fuzz


@pytest.mark.parametrize("op", GETS, ids=lambda o: o.id)
def test_every_get_parameter_survives_hostile_values(fc, ids, op):
    """One path/query parameter at a time is replaced by hostile payloads; everything else stays valid."""
    h = hdr("system_admin")
    base_query = {"as_of": P["as_of"]}
    if op.path == "/api/v1/executive/series":
        base_query["metric"] = "oer_pct"
    base_path = fill_path(op.path, ids)
    targets: list[tuple[str, str, str]] = [("path", name, "string" if name not in ("alert_id", "anomaly_id", "equipment_id", "work_order_id", "supplier_id", "lot_id") else "integer") for name in op.path_params]
    targets += [("query", q["name"], _param_type(q)) for q in op.query if q["name"] not in ("as_of", "scenario_id")]
    for where, name, typ in targets:
        payloads = INT_PAYLOADS + STR_PAYLOADS[:6] if typ in ("integer", "number") else STR_PAYLOADS
        for payload in payloads:
            query = dict(base_query)
            url = base_path
            if where == "path":
                url = op.path
                for pn in op.path_params:
                    val = urllib.parse.quote(payload, safe="") if pn == name else str(ids.get(pn, 1))
                    url = url.replace("{" + pn + "}", val)
            else:
                query[name] = payload
            t0 = time.perf_counter()
            r = fc.get(url, params=query, headers=h)
            _check(r, f"{op.id} {where}:{name}={payload[:30]!r}", time.perf_counter() - t0, payload)


def test_get_fuzz_left_the_database_unchanged(fc, ids):
    """Runs after the sweep above (module order): SQL injection attempts must not have changed a single row or object."""
    path = str(fc.app.state.settings.database_url).removeprefix("sqlite:///")
    before = _counts(path)
    h = hdr("system_admin")
    for payload in ["'; DROP TABLE alerts;--", "' OR 1=1; DELETE FROM work_orders;--", "1; UPDATE equipment SET code='x';--", "\" OR \"\"=\"", "') UNION SELECT 1--"]:
        for op in GETS:
            q = {"as_of": P["as_of"]}
            for p in op.query:
                if p["name"] not in ("as_of", "scenario_id"):
                    q[p["name"]] = payload
            url = op.path
            for pn in op.path_params:
                url = url.replace("{" + pn + "}", urllib.parse.quote(payload, safe=""))
            fc.get(url, params=q, headers=h)
    after = _counts(path)
    lazily_written = {"ai_recommendations", "audit_logs"}  # documented lazy catalog row; copilot audit rows
    changed = {t for t in before if before[t] != after.get(t) and t not in lazily_written}
    assert not changed, changed
    con = sqlite3.connect(path)
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    con.close()


# ---------------------------------------------------------------------------------------------------- POST fuzz


def _fields(schema, path=()):
    s = resolve(schema, COMP)
    if "anyOf" in s:
        non_null = [x for x in s["anyOf"] if resolve(x, COMP).get("type") != "null"]
        if non_null:
            yield from _fields(non_null[0], path)
        return
    if s.get("type") == "object" or "properties" in s:
        for k, v in (s.get("properties") or {}).items():
            yield from _fields(v, path + (k,))
    elif s.get("type") in ("string", "integer", "number"):
        yield path, s


def _set(obj, path, value):
    cur = obj
    for k in path[:-1]:
        cur = cur.setdefault(k, {}) if isinstance(cur, dict) else cur
    cur[path[-1]] = value


def _base_body(op: Op) -> dict:
    from .support import example_value  # noqa: PLC0415

    if op.id in VALID_WRITE_BODIES:
        return deepcopy(VALID_WRITE_BODIES[op.id])
    body = example_value(op.body_schema, COMP) or {}
    return body if isinstance(body, dict) else {}


@pytest.mark.parametrize("op", [o for o in JSON_POSTS if o.permission != "demo:reset_all"], ids=lambda o: o.id)
def test_every_post_field_survives_hostile_values(fc, ids, op):
    session = new_session()
    h = {**hdr("system_admin", session), "content-type": "application/json"}
    url = fill_path(op.path, ids)
    for path, s in _fields(op.body_schema):
        typ = s.get("type")
        payloads: list = STR_PAYLOADS if typ == "string" else NUM_JSON + STR_PAYLOADS[:4]
        for payload in payloads:
            body = _base_body(op)
            _set(body, path, payload)
            t0 = time.perf_counter()
            r = fc.post(url, params=P, headers=h, content=json.dumps(body))
            _check(r, f"{op.id} {'.'.join(path)}={str(payload)[:30]!r}", time.perf_counter() - t0, payload)
        if typ in ("integer", "number"):
            for token in RAW_NUM_TOKENS:  # non-standard JSON literals Python's parser accepts
                body_txt = json.dumps({**_base_body(op), "__x": "@@"}).replace('"@@"', token)
                body = _base_body(op)
                _set(body, path, "@@")
                body_txt = json.dumps(body).replace('"@@"', token)
                t0 = time.perf_counter()
                r = fc.post(url, params=P, headers=h, content=body_txt)
                _check(r, f"{op.id} {'.'.join(path)}={token[:12]}", time.perf_counter() - t0)


def schema_is_id(s: dict) -> bool:
    return s.get("type") == "integer" and "maximum" not in s and "exclusiveMaximum" not in s and s.get("minimum", 0) in (0, 1)


def _extreme(schema, which: str, depth: int = 0):
    s = resolve(schema, COMP)
    if depth > 5:
        return None
    if "anyOf" in s:
        non_null = [x for x in s["anyOf"] if resolve(x, COMP).get("type") != "null"]
        return _extreme(non_null[0], which, depth + 1) if non_null else None
    if "enum" in s:
        return s["enum"][-1 if which == "max" else 0]
    t = s.get("type")
    if t == "object" or "properties" in s:
        props = s.get("properties") or {}
        return {k: _extreme(v, which, depth + 1) for k, v in props.items()} if props else {}
    if t == "array":
        n = min(s.get("maxItems", 20), 50) if which == "max" else s.get("minItems", 0)
        return [_extreme(s.get("items"), which, depth + 1) for _ in range(n)]
    if t == "string":
        if s.get("format") == "date-time":
            return "2026-11-20T08:00:00Z"
        if s.get("format") == "date":
            return "2026-11-14"
        if s.get("pattern"):
            return None
        return "x" * (min(s.get("maxLength", 200), 2000) if which == "max" else s.get("minLength", 1))
    if t in ("integer", "number"):
        key = "maximum" if which == "max" else "minimum"
        if schema_is_id(s):
            return 18
        ex = "exclusiveMaximum" if which == "max" else "exclusiveMinimum"
        v = s.get(key, s.get(ex, (10**6 if which == "max" else 0)))
        return int(v) if t == "integer" else float(v)
    if t == "boolean":
        return which == "max"
    return None


@pytest.mark.parametrize("which", ["max", "min"])
@pytest.mark.parametrize("op", [o for o in JSON_POSTS if o.permission not in ("demo:reset_all",)], ids=lambda o: o.id)
def test_allowed_extreme_inputs_are_answered_in_bounded_time(fc, ids, op, which):
    """Expensive endpoints (queue simulation, ROI, scenarios, what-ifs, model run): the largest/smallest ACCEPTED input
    must complete quickly and never fail with 5xx - the declared schema bounds are the resource bound."""
    body = _extreme(op.body_schema, which)
    body = {k: v for k, v in (body or {}).items() if v is not None}
    h = {**hdr("system_admin", new_session()), "content-type": "application/json"}
    t0 = time.perf_counter()
    r = fc.post(fill_path(op.path, ids), params=P, headers=h, content=json.dumps(body))
    _check(r, f"{op.id} extreme-{which}", time.perf_counter() - t0)


# ---------------------------------------------------------------------------------------------------- pagination


LIMITED = [(o, p) for o in GETS for p in o.query if p["name"] == "limit"]
OFFSET = [(o, p) for o in GETS for p in o.query if p["name"] == "offset"]


def test_list_endpoints_with_limit_are_discovered():
    assert len(LIMITED) >= 8, [o.path for o, _ in LIMITED]


@pytest.mark.parametrize("op,param", LIMITED, ids=lambda x: x.id if isinstance(x, Op) else "limit")
def test_limit_parameter_is_capped(fc, ids, op, param):
    s = resolve(param["schema"], COMP)
    if "anyOf" in s:
        s = resolve(next(x for x in s["anyOf"] if resolve(x, COMP).get("type") != "null"), COMP)
    cap = s.get("maximum") or s.get("exclusiveMaximum")
    assert cap is not None and cap <= 1000, f"{op.id}: `limit` has no sane declared maximum ({s})"
    h = hdr("public_viewer")
    url = fill_path(op.path, ids)
    big = fc.get(url, params={**P, "limit": 10**9}, headers=h)
    assert_clean_error(big, status=422)
    at_cap = fc.get(url, params={**P, "limit": cap}, headers=h)
    assert at_cap.status_code == 200
    items = at_cap.json().get("items") or []
    assert len(items) <= cap
    for bad in (0, -1, "abc", 1.5, "1e3"):
        r = fc.get(url, params={**P, "limit": bad}, headers=h)
        assert r.status_code in (200, 422) and r.status_code < 500, (op.id, bad, r.status_code)
        if r.status_code == 200:
            assert len(r.json().get("items") or []) <= cap


@pytest.mark.parametrize("op,param", OFFSET, ids=lambda x: x.id if isinstance(x, Op) else "offset")
def test_offset_parameter_is_safe(fc, ids, op, param):
    url = fill_path(op.path, ids)
    for off in (0, 10**6, 2**62, 2**63 - 1, 2**63, 10**30, -1, "abc"):
        t0 = time.perf_counter()
        r = fc.get(url, params={**P, "offset": off}, headers=hdr("public_viewer"))
        _check(r, f"{op.id} offset={off}", time.perf_counter() - t0)
        if r.status_code == 200 and isinstance(off, int) and off > 10**6:
            assert (r.json().get("items") or []) == []


def _arrays(schema, prefix, depth=0):
    s = resolve(schema, COMP)
    if depth > 6:
        return
    if "anyOf" in s:
        for o in s["anyOf"]:
            yield from _arrays(o, prefix, depth + 1)
    elif s.get("type") == "array":
        yield prefix, s.get("maxItems")
        yield from _arrays(s.get("items"), prefix + "[]", depth + 1)
    elif s.get("type") == "object" or "properties" in s:
        for k, v in (s.get("properties") or {}).items():
            yield from _arrays(v, f"{prefix}.{k}", depth + 1)


def test_every_list_in_a_request_body_has_a_declared_maximum():
    """QA-12: `QueueSimulationRequest.policies` was unbounded: 5,000 entries = 4.8 s CPU and an 11.5 MB reply from a 55 KB request."""
    unbounded = [p for o in JSON_POSTS for p, m in _arrays(o.body_schema, o.id) if m is None]
    assert not unbounded, unbounded


def test_queue_simulation_cannot_be_used_as_an_amplifier(fc):
    body = {"policies": ["slot_based"] * 5000, "business_date": "2026-11-14"}
    t0 = time.perf_counter()
    r = fc.post("/api/v1/logistics/queue-simulation", params={"as_of": "2026-11-14T10:00:00Z"}, headers={**hdr("public_viewer"), "content-type": "application/json"}, content=json.dumps(body))
    assert_clean_error(r, status=422, code="validation_error")
    assert time.perf_counter() - t0 < 1.0
    ok = fc.post("/api/v1/logistics/queue-simulation", params={"as_of": "2026-11-14T10:00:00Z"}, headers=hdr("public_viewer"), json={"policies": ["fifo", "slot_based"], "business_date": "2026-11-14"})
    assert ok.status_code == 200 and len(ok.content) < 100_000


def test_expensive_read_parameters_are_bounded(fc, ids):
    """Parameters that scale work: horizon, lookback, node caps, sensor resolution, series window."""
    h = hdr("system_admin")
    cases = [
        ("/api/v1/ai/oer/forecast", {"horizon_h": 10**6}),
        ("/api/v1/ai/energy/forecast", {"horizon_h": 10**6}),
        ("/api/v1/ai/logistics/arrival-forecast", {"horizon_h": 10**6}),
        ("/api/v1/logistics/arrival-pattern", {"lookback_days": 10**6}),
        ("/api/v1/traceability/forward", {"supplier_id": ids["supplier_id"], "max_nodes": 10**9}),
        ("/api/v1/traceability/backward", {"lot_id": ids["lot_id"], "max_nodes": 10**9}),
        ("/api/v1/maintenance/equipment/18/sensors", {"resolution": 1, "start": "2000-01-01T00:00:00Z", "end": "2999-01-01T00:00:00Z"}),
        ("/api/v1/executive/kpis", {"period": "custom", "start": "2000-01-01T00:00:00Z", "end": "2999-01-01T00:00:00Z"}),
        ("/api/v1/executive/series", {"metric": "oer_pct", "granularity": "hour", "period": "30d"}),
    ]
    for path, extra in cases:
        t0 = time.perf_counter()
        r = fc.get(path, params={**P, **extra}, headers=h)
        _check(r, f"{path} {extra}", time.perf_counter() - t0)
        if r.status_code == 200:
            assert len(r.content) < 3_000_000, (path, len(r.content))  # response size bounded too


# ---------------------------------------------------------------------------------------------------- XSS / storage


def test_stored_text_comes_back_verbatim_as_json_never_as_html(fc):
    """User strings are returned as JSON data (content-type json + nosniff); the API never renders them into HTML."""
    payload = "<script>alert(1)</script><img src=x onerror=alert(1)>"
    h = hdr("maintenance_engineer", new_session())
    r = fc.post("/api/v1/work-orders", params=P, headers=h, json={"equipment_id": 18, "title": payload[:150], "description": payload, "confirm": True})
    assert r.status_code == 201
    assert r.headers["content-type"].startswith("application/json") and r.headers["x-content-type-options"] == "nosniff"
    assert r.json()["description"] == payload


def test_html_outputs_contain_no_script_or_event_handlers(fc, ids):
    """Printable / raw HTML endpoints: no <script>, no inline event handlers, no javascript: URLs."""
    h = hdr("system_admin")
    docs = []
    r = fc.get("/api/v1/reports/executive/html", params={**P, "raw": "true"}, headers=h)
    docs.append(r.text)
    for rt in ("executive", "production", "maintenance", "logistics", "energy"):
        docs.append(fc.get(f"/api/v1/reports/{rt}/html", params=P, headers=h).json()["html"])
    docs.append(fc.get(f"/api/v1/traceability/lots/{ids['lot_id']}/report/printable", params=P, headers=h).json()["html"])
    from .support import example_value  # noqa: PLC0415

    roi = next(o for o in OPS if o.id == "POST /api/v1/roi/export/printable")
    docs.append(fc.post(roi.path, params=P, headers=h, json=example_value(roi.body_schema, COMP) or {}).json().get("html", ""))
    import re  # noqa: PLC0415

    for html in docs:
        assert len(html) > 500
        low = html.lower()
        assert "<script" not in low and "javascript:" not in low and not re.search(r"\son\w+\s*=", low), low[:200]
