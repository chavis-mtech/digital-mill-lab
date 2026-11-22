"""QA-16 regression: an ML alert row stores the severity of its episode PEAK, which can lie after `raised_at`.
Every reader must show the severity AS SEEN AT THE DEMO CLOCK, and all readers must agree with /alerts.

The press-bearing episode on PRS-03 escalates medium -> high -> critical between 2026-11-13 and 2026-11-20.
"""

from __future__ import annotations

import re

from tests.integration.conftest import PRESS, PRS03

ADMIN = {"X-Demo-Role": "system_admin"}
EARLY = "2026-11-13T07:00:00Z"  # first ML detection just happened
MID = "2026-11-16T08:00:00Z"  # escalated to high
ORDER = ["info", "low", "medium", "high", "critical"]


def _alerts(client, as_of):
    r = client.get("/api/v1/alerts", params={"as_of": as_of, "limit": 200}, headers=ADMIN)
    assert r.status_code == 200, r.text[:200]
    return {a["code"]: a for a in r.json()["items"]}


def _health_alert_severities(client, as_of):
    """{alert code: severity} parsed from the health criteria text ('unresolved <sev> alert <code> ...')."""
    r = client.get(f"/api/v1/maintenance/equipment/{PRS03}/health", params={"as_of": as_of}, headers=ADMIN)
    assert r.status_code == 200, r.text[:200]
    out = {}
    for c in r.json()["criteria"]:
        m = re.search(r"unresolved (\w+) alert (\S+)", c.get("rule") or c.get("label") or str(c))
        if m:
            out[m.group(2)] = m.group(1)
    return out


def test_ml_alert_severity_escalates_with_the_clock_and_readers_agree(client):
    seen = {}
    for clock in (EARLY, MID, PRESS):
        al = _alerts(client, clock)
        ml = {code: a["severity"] for code, a in al.items() if code.startswith("MLA-") and "PRS-03" in (a.get("title") or "")}
        health = _health_alert_severities(client, clock)
        # every ML alert the health view lists must carry the same severity /alerts shows at that clock
        for code, sev in health.items():
            if code.startswith("MLA-"):
                assert code in ml, (clock, code)
                assert ml[code] == sev, (clock, code, ml[code], sev)
        seen[clock] = max(ml.values(), key=ORDER.index) if ml else None
    # no future leak: right after first detection the severity is below critical; it reaches critical by the press focus
    assert seen[EARLY] is not None and ORDER.index(seen[EARLY]) < ORDER.index("critical")
    assert ORDER.index(seen[MID]) >= ORDER.index(seen[EARLY])
    assert seen[PRESS] == "critical"


def test_executive_critical_alert_count_does_not_include_future_peak_severity(client):
    early = client.get("/api/v1/executive/kpis", params={"as_of": EARLY, "period": "today"}, headers=ADMIN).json()
    late = client.get("/api/v1/executive/kpis", params={"as_of": PRESS, "period": "today"}, headers=ADMIN).json()
    k = lambda b: {x["key"]: x for x in b["kpis"]}["active_maintenance_alerts"]  # noqa: E731
    # at the early clock no maintenance alert is critical yet (only the escalated episode is); the KPI status must not say so
    assert k(early)["value"] <= k(late)["value"]
