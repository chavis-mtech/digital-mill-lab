"""Generic as_of leak sweep (QA item 3) - ADR-005: services never read "actual" data with ts > as_of.

For the six scenario focus times plus four pseudo-random hours, EVERY GET operation of the OpenAPI document is called
and the JSON is walked: no ISO timestamp of `synthetic_actual` data may exceed as_of.

What is excluded (and why) is listed explicitly in EXEMPT_* below - nothing is skipped silently:
  * sub-trees whose own `provenance.kind` is `forecast` or `what_if` (they are SUPPOSED to extend past the clock),
  * `{t, v: null}` axis slots (an hour that has not happened yet carries no value),
  * a short list of metadata keys that are not data (planned dates, dataset bounds, model/report wall-clock stamps, the
    scenario catalogue that tells the UI which `as_of` activates which episode).
`as_of` outside the dataset window must be rejected cleanly.
"""

from __future__ import annotations

import random
import re
from datetime import timedelta

import pytest

from .support import (
    Op,
    assert_clean_error,
    collect_ops,
    discover_path_ids,
    fill_path,
    focus_times,
    hdr,
    iso,
    leaks_in,
    make_client,
    parse_ts,
    prepare_db,
)

OPS, _SPEC = collect_ops()
GETS = [o for o in OPS if o.method == "GET" and o.permission]

# operations addressed by an id in the query string: they may 404 at a clock before the entity exists
ID_QUERY_OPS = {"/api/v1/traceability/backward", "/api/v1/traceability/forward"}

# key -> reason. Applies to any depth.
EXEMPT_KEYS = {
    "due_at": "work-order due date: a plan, future by nature",
    "trained_at": "wall-clock time the model artifact was trained (not demo data)",
    "train_window": "model metadata: period the artifact was fitted on (documented limitation: not shifted with as_of)",
    "test_window": "model metadata: temporal hold-out period",
    "generated_at": "wall-clock time the report/document was rendered",
    "window_start": "dataset bounds",
    "window_end": "dataset bounds",
    "default_as_of": "dataset default clock",
    "latest_data_ts": "dataset bounds",
}
# (path prefix, key) -> reason. The scenario catalogue lists playback targets so the UI can set as_of to them.
EXEMPT_PATH_KEYS = {
    ("/api/v1/scenarios", k): "scenario catalogue: playback target, not measured data (measured effects are null before focus_ts)"
    for k in ("start_ts", "end_ts", "focus_ts", "baseline_ts", "activate_as_of")
}
# JSON paths (index-stripped) that are profiles over PAST days laid on the as_of business day's hour axis
EXEMPT_JSON_PATHS = {"$.typical_by_hour.points[].t": "average of the previous 14 days, plotted on today's hour axis"}


def future_stamps(doc, as_of, endpoint: str) -> list[tuple[str, str]]:
    """Timestamps of non-forecast, non-what-if data later than as_of (after the documented exemptions)."""
    found: list[tuple[str, str]] = []
    limit = as_of + timedelta(seconds=1)

    def scan(node, path):
        if isinstance(node, dict):
            prov = node.get("provenance")
            if isinstance(prov, dict) and prov.get("kind") in ("forecast", "what_if"):
                return
            for k, v in node.items():
                p = f"{path}.{k}"
                if k in EXEMPT_KEYS or any(endpoint.startswith(ep) and k == ek for (ep, ek) in EXEMPT_PATH_KEYS):
                    continue
                if isinstance(v, dict | list):
                    scan(v, p)
                elif isinstance(v, str):
                    dt = parse_ts(v)
                    if dt and dt > limit and not ("v" in node and node["v"] is None):
                        generic = re.sub(r"\[\d+\]", "[]", p)
                        if generic not in EXEMPT_JSON_PATHS:
                            found.append((generic, v))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                if isinstance(v, dict | list):
                    scan(v, f"{path}[{i}]")
                elif isinstance(v, str):
                    dt = parse_ts(v)
                    if dt and dt > limit:
                        found.append((re.sub(r"\[\d+\]", "[]", f"{path}[{i}]"), v))

    scan(doc, "$")
    return found


@pytest.fixture(scope="module")
def asof_url() -> str:
    return prepare_db("qa-asof")


@pytest.fixture(scope="module")
def ac(asof_url):
    return make_client(asof_url)


@pytest.fixture(scope="module")
def clocks(asof_url, ac):
    """Six scenario focus times + four deterministic pseudo-random hours inside the dataset window."""
    ft = focus_times(asof_url)
    assert len(ft) == 6
    st = ac.app.state.settings
    rng = random.Random(20261120)
    extra = [(st.window_start + timedelta(hours=rng.randrange(72, 24 * 115))).replace(minute=0, second=0, microsecond=0) for _ in range(4)]
    return sorted(ft.values()) + sorted(extra)


def _params_for(op: Op, as_of: str, ids: dict, kpi_keys: list[str]) -> list[dict]:
    params = {"as_of": as_of}
    if op.path == "/api/v1/executive/series":
        return [{**params, "metric": k} for k in kpi_keys[:2]]
    if op.path == "/api/v1/traceability/forward":
        params["supplier_id"] = ids["supplier_id"]
    if op.path == "/api/v1/traceability/backward":
        params["lot_id"] = ids["lot_id"]
    return [params]


def test_every_get_operation_is_part_of_the_sweep():
    assert len(GETS) >= 60
    assert all(o.method == "GET" for o in GETS)


@pytest.mark.parametrize("slot", range(10))
def test_no_actual_timestamp_exceeds_as_of_on_any_get_endpoint(ac, clocks, slot):
    t = clocks[slot]
    as_of = iso(t)
    ids = discover_path_ids(ac)  # ids that exist at the latest clock; earlier clocks may legitimately 404 (entity not raised yet)
    h = hdr("system_admin")
    kp = ac.get("/api/v1/executive/kpis", params={"as_of": as_of}, headers=h).json()
    kpi_keys = [k["key"] for k in kp["kpis"]]
    assert kpi_keys, "executive/kpis returned no KPI keys"
    violations: list[str] = []
    covered = 0
    for op in GETS:
        for params in _params_for(op, as_of, ids, kpi_keys):
            r = ac.get(fill_path(op.path, ids), params=params, headers=h)
            assert r.status_code < 500, (op.id, as_of, r.status_code, r.text[:200])
            assert not leaks_in(r.text), (op.id, leaks_in(r.text))
            if r.status_code == 404:
                # only id-addressed resources may be missing at an earlier clock: they must not exist yet (hidden, not leaked)
                assert op.path_params or op.path in ID_QUERY_OPS, f"{op.id} returned 404 without an id at {as_of}"
                assert_clean_error(r, status=404, code="not_found")
                covered += 1
                continue
            assert r.status_code == 200, (op.id, as_of, r.status_code, r.text[:200])
            covered += 1
            if "json" not in r.headers.get("content-type", ""):
                continue
            for path, value in future_stamps(r.json(), t, op.path):
                violations.append(f"{op.id} {path} = {value} (as_of {as_of})")
    assert covered >= len(GETS)
    assert not violations, "future timestamps in actual data:\n" + "\n".join(sorted(set(violations))[:25])


def test_exemptions_are_narrow(clocks):
    """The sweep must still bite: a future stamp in plain data is reported, an exempted key / forecast subtree is not."""
    t = clocks[0]
    future = iso(t + timedelta(hours=5))
    assert future_stamps({"rows": [{"ts": future}]}, t, "/x") == [("$.rows[].ts", future)]
    assert future_stamps({"due_at": future}, t, "/x") == []
    assert future_stamps({"series": {"points": [{"t": future, "v": 1}], "provenance": {"kind": "forecast"}}}, t, "/x") == []
    assert future_stamps({"series": {"points": [{"t": future, "v": 1}], "provenance": {"kind": "synthetic_actual"}}}, t, "/x")
    assert future_stamps({"points": [{"t": future, "v": None}]}, t, "/x") == []  # empty axis slot
    assert future_stamps({"items": [{"focus_ts": future}]}, t, "/api/v1/scenarios") == []
    assert future_stamps({"items": [{"focus_ts": future}]}, t, "/api/v1/alerts") != []


# ---------------------------------------------------------------------------------------------------- explicit future-seeking inputs


def test_future_seeking_query_parameters_do_not_leak(ac, clocks):
    """business_date / start / end beyond the clock: clipped or rejected, never answered with future actuals."""
    t = clocks[3]
    as_of = iso(t)
    future_day = (t + timedelta(days=3)).strftime("%Y-%m-%d")
    future_end = iso(t + timedelta(days=3))
    h = hdr("system_admin")
    cases = [
        ("/api/v1/production/summary", {"business_date": future_day}),
        ("/api/v1/logistics/arrival-pattern", {"business_date": future_day}),
        ("/api/v1/executive/kpis", {"period": "custom", "start": iso(t - timedelta(days=1)), "end": future_end}),
        ("/api/v1/maintenance/equipment/18/sensors", {"start": iso(t - timedelta(days=1)), "end": future_end}),
    ]
    for path, extra in cases:
        r = ac.get(path, params={"as_of": as_of, **extra}, headers=h)
        assert r.status_code < 500, (path, r.status_code, r.text[:200])
        if r.status_code == 200:
            assert not future_stamps(r.json(), t, path), (path, future_stamps(r.json(), t, path)[:3])
        else:
            assert_clean_error(r)


def test_scenario_without_as_of_resolves_to_its_focus_time_and_ignores_nothing_else(ac, asof_url):
    ft = focus_times(asof_url)
    for code, ts in ft.items():
        r = ac.get("/api/v1/demo/context", params={"scenario_id": code}, headers=hdr("public_viewer"))
        assert r.json()["context"]["as_of"] == iso(ts), (code, r.json()["context"]["as_of"], iso(ts))
        # an explicit as_of always wins over the scenario focus
        r = ac.get("/api/v1/demo/context", params={"scenario_id": code, "as_of": "2026-08-01"}, headers=hdr("public_viewer"))
        assert r.json()["context"]["as_of"].startswith("2026-08-01")


def test_as_of_timezone_rules(ac):
    """ADR-016: date -> 18:00 mill time; naive datetime = Asia/Bangkok; offset datetimes as given."""
    ctx = lambda v: ac.get("/api/v1/demo/context", params={"as_of": v}, headers=hdr("public_viewer")).json()["context"]["as_of"]  # noqa: E731
    assert ctx("2026-11-20") == "2026-11-20T11:00:00Z"
    assert ctx("2026-11-20T15:00:00") == "2026-11-20T08:00:00Z"
    assert ctx("2026-11-20T15:00:00+07:00") == "2026-11-20T08:00:00Z"
    assert ctx("2026-11-20T08:00:00Z") == "2026-11-20T08:00:00Z"
    assert ctx("2026-11-20T08:00:00+00:00") == "2026-11-20T08:00:00Z"


# ---------------------------------------------------------------------------------------------------- outside the window


BAD_AS_OF = {
    "before_window": ("2026-07-22T23:59:00Z", "as_of_out_of_window"),
    "after_window": ("2026-11-20T17:00:00Z", "as_of_out_of_window"),  # window_end is exclusive
    "tomorrow": ("2026-11-21", "as_of_out_of_window"),
    "far_future": ("2999-01-01T00:00:00Z", "as_of_out_of_window"),
    "year_1": ("0001-01-01T00:00:00Z", "as_of_out_of_window"),
    "epoch": ("1970-01-01", "as_of_out_of_window"),
    "garbage": ("yesterday", "invalid_as_of"),
    "sql": ("2026-11-20'; DROP TABLE alerts;--", "invalid_as_of"),
    "nul": ("2026-11-20\x00", "invalid_as_of"),
    "unix_time": ("1795000000", "invalid_as_of"),
    "month_13": ("2026-13-01", "invalid_as_of"),
    "feb_30": ("2026-02-30", "invalid_as_of"),
    "thai_digits": ("๒๐๒๖-ฑฑ-๒๐", "invalid_as_of"),
}


@pytest.mark.parametrize("name", sorted(BAD_AS_OF))
def test_as_of_outside_the_window_or_malformed_is_rejected_cleanly_everywhere(ac, name):
    value, code = BAD_AS_OF[name]
    ids = {"alert_id": 1, "anomaly_id": 1, "equipment_id": 18, "work_order_id": 1, "supplier_id": 1, "lot_id": 1, "recommendation_id": 1, "slug": "kb", "name": "oer_forecast", "code": "NORMAL_DAY", "report_type": "executive", "copilot_session_id": 1, "ref": "kb:x#0", "stage_code": "PRESSING"}
    for op in GETS:
        r = ac.get(fill_path(op.path, ids), params={"as_of": value}, headers=hdr("system_admin"))
        assert_clean_error(r, status=422)
        assert r.json()["error"]["code"] in (code, "validation_error"), (op.id, r.json()["error"]["code"])


def test_as_of_longer_than_the_declared_maximum_is_a_validation_error(ac):
    r = ac.get("/api/v1/executive/kpis", params={"as_of": "2026-11-20T08:00:00Z" + " " * 40}, headers=hdr("public_viewer"))
    assert_clean_error(r, status=422, code="validation_error")


def test_window_boundaries(ac):
    st = ac.app.state.settings
    ok = lambda ts: ac.get("/api/v1/executive/kpis", params={"as_of": iso(ts)}, headers=hdr("public_viewer")).status_code  # noqa: E731
    assert ok(st.window_start) == 200  # inclusive
    assert ok(st.window_end - timedelta(minutes=1)) == 200
    assert ok(st.window_end) == 422  # exclusive
    assert ok(st.window_start - timedelta(seconds=1)) == 422
    # at the very first hour there is no history: endpoints answer (possibly empty) instead of failing
    r = ac.get("/api/v1/executive/overview", params={"as_of": iso(st.window_start)}, headers=hdr("public_viewer"))
    assert r.status_code == 200, r.text[:300]


def test_copilot_answers_do_not_cite_data_after_the_clock(ac, clocks):
    """The Copilot HTTP endpoint at three earlier clocks: no timestamp of actual data after as_of anywhere in the reply."""
    h = hdr("public_viewer", "11111111-2222-4333-8444-555555555555")
    for t in (clocks[0], clocks[2], clocks[7]):
        for q in ("Why did OER change today?", "Which machine should I inspect first?", "How many trucks are waiting now?"):
            r = ac.post("/api/v1/copilot/chat", params={"as_of": iso(t)}, json={"message": q, "lang": "en"}, headers=h)
            assert r.status_code == 200, (r.status_code, r.text[:200])
            assert not leaks_in(r.text)
            assert not future_stamps(r.json(), t, "/api/v1/copilot/chat"), (iso(t), q, future_stamps(r.json(), t, "/api/v1/copilot/chat")[:3])
