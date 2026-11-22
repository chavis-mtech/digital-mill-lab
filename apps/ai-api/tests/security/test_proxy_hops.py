"""QA-20: client-IP selection behind a CHAIN of trusted proxies (TRUSTED_PROXY_HOPS).

Each trusted proxy that APPENDS to X-Forwarded-For counts as one hop; with N such hops the client is the N-th entry from the right.
(Next.js rewrites pass the header through without appending - verified 2026-11-22 - so Next.js itself is not a hop; see DEPLOYMENT.md.)
Taking the right-most entry behind two appending hops keys every visitor on the inner proxy's address (one shared bucket); taking the
left-most is client-controlled.
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.security.ratelimit import RateLimitMiddleware

from .support import make_client, prepare_db


def _ip(hops: int, xff: str | None, peer: str = "127.0.0.1", trust: bool = True) -> str:
    mw = RateLimitMiddleware(None, enabled=True, per_ip_per_minute=60, per_session_per_minute=60, burst=10, trust_proxy=trust, trusted_proxy_hops=hops)
    headers = {"x-forwarded-for": xff} if xff is not None else {}
    return mw._client_ip({"client": (peer, 5555)}, headers)


@pytest.mark.parametrize(
    "hops,xff,expected",
    [
        (1, "203.0.113.7", "203.0.113.7"),  # browser -> nginx (appends) -> Next.js (passes through) -> API
        (1, "198.51.100.1, 203.0.113.7", "203.0.113.7"),  # spoofed prefix ignored
        (2, "203.0.113.7, 10.0.0.5", "203.0.113.7"),  # browser -> CDN (appends) -> nginx (appends) -> API
        (2, "6.6.6.6, 203.0.113.7, 10.0.0.5", "203.0.113.7"),  # spoofed prefix ignored with 2 hops
        (2, "evil, also-evil, 203.0.113.7, 10.0.0.5", "203.0.113.7"),
        (2, "10.0.0.5", "127.0.0.1"),  # fewer entries than hops: did not pass the whole chain -> TCP peer, not a client value
        (1, "", "127.0.0.1"),  # empty header
        (2, " , 10.0.0.5", "127.0.0.1"),  # blank client slot -> peer
    ],
)
def test_client_ip_is_n_hops_from_the_right(hops, xff, expected):
    assert _ip(hops, xff) == expected


def test_forwarded_header_is_ignored_when_proxies_are_not_trusted():
    assert _ip(2, "203.0.113.7, 10.0.0.5", trust=False) == "127.0.0.1"
    assert _ip(1, None) == "127.0.0.1"


def test_selected_value_is_length_bounded():
    assert len(_ip(1, "x" * 5000)) == 64


def test_setting_is_validated_and_defaults_to_one():
    assert Settings(database_url="sqlite:///x.db").trusted_proxy_hops == 1
    with pytest.raises(ValueError):
        Settings(database_url="sqlite:///x.db", trusted_proxy_hops=0)


def test_two_hops_end_to_end_separate_buckets_and_spoofing_does_not_help():
    c = make_client(  # pinned small buckets: this tests proxy-hop handling, not the shipped defaults
        prepare_db("qa-rl"), rate_limit_enabled=True, rate_limit_per_ip_per_minute=240, rate_limit_per_session_per_minute=120, rate_limit_burst=40, trust_proxy_headers=True, trusted_proxy_hops=2
    )
    proxy = "10.0.0.5"  # the inner appending proxy saw the outer proxy - identical for every visitor
    # attacker rotates the spoofable prefix: still one bucket (its real address 203.0.113.7)
    codes = [c.get("/api/v1/meta", headers={"X-Forwarded-For": f"198.51.100.{i % 250}, 203.0.113.7, {proxy}"}).status_code for i in range(120)]
    assert codes.count(429) > 60
    # a different visitor behind the same proxy chain is NOT throttled by the attacker's traffic
    other = [c.get("/api/v1/meta", headers={"X-Forwarded-For": f"203.0.113.99, {proxy}"}).status_code for _ in range(5)]
    assert other == [200] * 5
