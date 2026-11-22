"""Rate limiting under abuse (QA item 5). ADR-012: in-process token buckets per client IP and per X-Demo-Session.

Real-time bursts against the real ASGI stack (no fake clock): 200 rapid requests, recovery after Retry-After, header-spoofing
attempts, memory bound of the limiter, and thread-parallel bursts. Finding QA-13: with TRUST_PROXY_HEADERS=true the limiter keyed on the
LEFT-most X-Forwarded-For entry, which a client controls whenever the proxy appends (nginx $proxy_add_x_forwarded_for) - fixed to the
right-most entry (the address the trusted proxy actually saw).
"""

from __future__ import annotations

import threading
import time
import uuid

from app.security.ratelimit import TokenBucketLimiter

from .support import assert_clean_error, hdr, make_client, new_session, prepare_db


def _limited_client(**kw):
    return make_client(prepare_db("qa-rl"), rate_limit_enabled=True, **kw)


def test_burst_of_200_requests_is_throttled_with_envelope_and_retry_after():
    c = _limited_client(rate_limit_per_ip_per_minute=240, rate_limit_burst=40)  # pinned: this tests the mechanism, not the shipped defaults
    t0 = time.perf_counter()
    codes = [c.get("/api/v1/meta").status_code for _ in range(200)]
    elapsed = time.perf_counter() - t0
    ok, limited = codes.count(200), codes.count(429)
    assert ok + limited == 200 and limited > 100, codes.count(429)
    assert 40 <= ok <= 40 + elapsed * 4 + 2, (ok, elapsed)  # burst + continuous refill (240/min = 4/s) only
    assert codes.index(429) >= 40  # throttling starts only after the burst is spent
    r = c.get("/api/v1/meta")
    err = assert_clean_error(r, status=429, code="rate_limited")
    assert err["details"]["scope"] == "ip" and err["details"]["retry_after_s"] >= 1
    assert r.headers["retry-after"] == str(err["details"]["retry_after_s"])
    assert r.headers["content-type"].startswith("application/json")


def test_limiter_recovers_after_retry_after():
    c = _limited_client(rate_limit_per_ip_per_minute=600, rate_limit_burst=5)  # 10 tokens/s
    assert [c.get("/api/v1/meta").status_code for _ in range(5)] == [200] * 5
    r = c.get("/api/v1/meta")
    assert r.status_code == 429
    wait = int(r.headers["retry-after"])
    assert 1 <= wait <= 2
    time.sleep(wait + 0.1)
    assert c.get("/api/v1/meta").status_code == 200  # recovered
    time.sleep(1.0)  # ~10 tokens refilled, bucket capped at the burst size
    again = [c.get("/api/v1/meta").status_code for _ in range(8)]
    assert again.count(200) in (5, 6) and 429 in again  # never more than burst (+1 refilled during the loop)


def test_health_ready_and_docs_are_exempt_but_the_api_is_not():
    c = _limited_client(rate_limit_per_ip_per_minute=1, rate_limit_burst=1)
    assert c.get("/api/v1/meta").status_code == 200
    assert c.get("/api/v1/meta").status_code == 429
    for p in ("/health", "/ready", "/openapi.json", "/docs"):
        assert [c.get(p).status_code for _ in range(5)] == [c.get(p).status_code] * 5 and c.get(p).status_code != 429, p
    # look-alike paths under /api are never exempt
    for p in ("/api/v1/health", "/api/v1/docs", "/api/v1/openapi.json"):
        assert c.get(p).status_code == 429, p


def test_rotating_session_ids_does_not_evade_the_ip_limit():
    c = _limited_client()
    codes = [c.get("/api/v1/meta", headers={"X-Demo-Session": str(uuid.uuid4())}).status_code for _ in range(120)]
    assert codes.count(200) <= 40 + 120 / 60 * 4 + 2 and codes.count(429) > 60


def test_garbage_session_ids_do_not_evade_or_break_the_limiter():
    c = _limited_client()
    codes = [c.get("/api/v1/meta", headers={"X-Demo-Session": f"not-a-uuid-{i}" + "x" * 80}).status_code for i in range(120)]
    assert set(codes) <= {200, 429} and codes.count(429) > 60


def test_spoofed_forwarded_for_is_ignored_unless_the_proxy_is_trusted():
    c = _limited_client(trust_proxy_headers=False)
    codes = [c.get("/api/v1/meta", headers={"X-Forwarded-For": f"10.0.{i // 250}.{i % 250}"}).status_code for i in range(120)]
    assert codes.count(429) > 60, "X-Forwarded-For must not create fresh buckets when TRUST_PROXY_HEADERS=false"


def test_trusted_proxy_mode_uses_the_address_the_proxy_saw_not_the_client_supplied_prefix():
    """nginx appends the real peer to whatever the client sent: 'spoofed, real'. The limiter must key on 'real' (QA-13)."""
    c = _limited_client(trust_proxy_headers=True)
    # attacker rotates the spoofable left-most entry; the proxy-appended right-most entry is constant
    codes = [c.get("/api/v1/meta", headers={"X-Forwarded-For": f"198.51.100.{i % 250}, 203.0.113.7"}).status_code for i in range(120)]
    assert codes.count(429) > 60, "rotating the client-controlled prefix evaded the per-IP limit"
    # and different real clients behind the proxy keep separate buckets
    other = [c.get("/api/v1/meta", headers={"X-Forwarded-For": "203.0.113.99"}).status_code for _ in range(5)]
    assert other == [200] * 5


def test_per_session_limit_is_independent_of_ip_budget_and_other_sessions():
    c = _limited_client(rate_limit_per_ip_per_minute=100_000, rate_limit_burst=1000, rate_limit_per_session_per_minute=60)  # session burst = 500
    a, b = new_session(), new_session()
    ha = {"X-Demo-Session": a}
    codes = [c.get("/api/v1/meta", headers=ha).status_code for _ in range(520)]
    assert codes.count(429) >= 15 and codes[:400] == [200] * 400
    err = assert_clean_error(c.get("/api/v1/meta", headers=ha), status=429, code="rate_limited")
    assert err["details"]["scope"] == "session"
    assert c.get("/api/v1/meta", headers={"X-Demo-Session": b}).status_code == 200  # another visitor is unaffected


def test_limiter_memory_is_bounded_under_a_key_flood():
    lim = TokenBucketLimiter(rate_per_minute=60, capacity=5, max_keys=1000)
    for i in range(60_000):
        lim.check(f"session:{i}")
    assert len(lim._buckets) <= 1000
    # a legitimate client is still served after the flood
    assert lim.check("session:legit")[0]


def test_parallel_burst_never_exceeds_the_budget_and_never_errors():
    c = _limited_client(rate_limit_per_ip_per_minute=60, rate_limit_burst=30)
    codes: list[int] = []
    lock = threading.Lock()

    def worker():
        got = [c.get("/api/v1/meta").status_code for _ in range(25)]
        with lock:
            codes.extend(got)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    t0 = time.perf_counter()
    [t.start() for t in threads]
    [t.join() for t in threads]
    elapsed = time.perf_counter() - t0
    assert len(codes) == 250 and set(codes) <= {200, 429}
    assert codes.count(200) <= 30 + elapsed + 2, (codes.count(200), elapsed)  # burst + 1 token/s refill, no race-condition over-admission


def test_rate_limited_error_responses_are_counted_too():
    """Hammering with INVALID requests (422/403) spends the same budget: error paths are not a free probe channel."""
    c = _limited_client(rate_limit_per_ip_per_minute=60, rate_limit_burst=10)
    codes = [c.get("/api/v1/executive/kpis", headers=hdr("nonsense-role")).status_code for _ in range(30)]
    assert codes.count(422) <= 12 and codes.count(429) >= 15
