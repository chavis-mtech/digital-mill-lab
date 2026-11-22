from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

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
