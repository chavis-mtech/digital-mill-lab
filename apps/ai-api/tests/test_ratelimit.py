from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.security.ratelimit import TokenBucketLimiter
from tests.conftest import make_settings


class FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def test_token_bucket_refills():
    clock = FakeClock()
    lim = TokenBucketLimiter(rate_per_minute=60, capacity=3, clock=clock)
    assert [lim.check("k")[0] for _ in range(3)] == [True, True, True]
    ok, retry = lim.check("k")
    assert not ok and 0 < retry <= 1.0
    clock.t += 1.0  # 1 token/s
    assert lim.check("k")[0]
    assert lim.check("other")[0]  # independent keys


def test_token_bucket_prunes_when_full():
    clock = FakeClock()
    lim = TokenBucketLimiter(rate_per_minute=60, capacity=1, clock=clock, max_keys=10)
    for i in range(25):
        lim.check(f"k{i}")
    assert len(lim._buckets) <= 10


def test_middleware_per_ip_429_envelope_and_exemptions():
    app = create_app(make_settings(rate_limit_enabled=True, rate_limit_per_ip_per_minute=1, rate_limit_burst=2))
    c = TestClient(app)
    assert c.get("/api/v1/meta").status_code == 200
    assert c.get("/api/v1/meta").status_code == 200
    r = c.get("/api/v1/meta")
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"
    assert int(r.headers["retry-after"]) >= 1
    assert c.get("/health").status_code == 200  # exempt


def test_middleware_per_session_limit():
    app = create_app(
        make_settings(rate_limit_enabled=True, rate_limit_per_ip_per_minute=1, rate_limit_burst=10, rate_limit_per_session_per_minute=1)
    )
    c = TestClient(app)
    s1 = {"X-Demo-Session": str(uuid.uuid4())}
    codes = [c.get("/api/v1/meta", headers=s1).status_code for _ in range(6)]  # session burst = burst // 2 = 5
    assert codes == [200] * 5 + [429]
    r = c.get("/api/v1/meta", headers=s1)
    assert r.json()["error"]["details"]["scope"] == "session"
    assert c.get("/api/v1/meta", headers={"X-Demo-Session": str(uuid.uuid4())}).status_code == 200


# --- shipped defaults versus a real page load -------------------------------------------------------------------------------
# Measured 2026-11-23 (production web build, Playwright, 16 demo pages): one page load fires at most 13 API requests, all inside
# one second, and one visitor browsing 8 pages in 48 s used 71 requests (about 90 a minute). Behind the web app's proxy every
# visitor reaches the API from ONE address (TRUST_PROXY_HEADERS=false), so the per-IP bucket is shared by all visitors. The earlier
# defaults (240 per minute, burst 40, session bucket 20) were drained by three quick reloads on the public deployment (HTTP 429).
PAGE_LOAD_REQUESTS = 13


def _shipped_defaults() -> Settings:
    """Settings with the limiter on and the three limiter numbers taken from the field defaults, whatever a developer's .env or environment says."""
    numbers = {
        n: Settings.model_fields[n].default
        for n in ("rate_limit_per_ip_per_minute", "rate_limit_per_session_per_minute", "rate_limit_burst")
    }
    return make_settings(rate_limit_enabled=True, **numbers)


def _page_load(client: TestClient, session: str) -> list[int]:
    return [client.get("/api/v1/meta", headers={"X-Demo-Session": session}).status_code for _ in range(PAGE_LOAD_REQUESTS)]


def test_shipped_defaults_hold_ten_visitors_opening_a_page_at_the_same_moment():
    c = TestClient(create_app(_shipped_defaults()))  # every other number is the shipped default
    codes = [code for _ in range(10) for code in _page_load(c, str(uuid.uuid4()))]  # 10 x 13 = 130 requests from one address
    assert len(codes) == 130
    assert codes.count(429) == 0, codes.count(429)


def test_shipped_defaults_hold_one_visitor_reloading_a_page_five_times_in_a_row():
    c = TestClient(create_app(_shipped_defaults()))
    s = str(uuid.uuid4())
    codes = [code for _ in range(5) for code in _page_load(c, s)]  # 5 x 13 = 65 requests, one session
    assert codes.count(429) == 0, codes.count(429)


def test_shipped_defaults_still_throttle_a_flood_from_one_session():
    c = TestClient(create_app(_shipped_defaults()))
    s = {"X-Demo-Session": str(uuid.uuid4())}
    first_refused = None
    for i in range(400):
        r = c.get("/api/v1/meta", headers=s)
        if r.status_code == 429:
            first_refused = (i, r.json()["error"]["details"]["scope"])
            break
    assert first_refused is not None  # a flood is throttled ...
    assert first_refused[0] >= 100  # ... only after the session bucket (100 requests, about seven page loads) is spent ...
    assert first_refused[1] == "session"  # ... and it is the session bucket that refuses first
