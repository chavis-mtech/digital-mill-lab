"""In-memory token-bucket rate limiting per client IP and per X-Demo-Session.

Single-process only (fine for the demo's one API container). For multiple replicas, swap TokenBucketLimiter
for a Redis-backed implementation with the same `check()` signature (documented in SECURITY / ADR-012).
"""

from __future__ import annotations

import json
import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from starlette.types import ASGIApp, Receive, Scope, Send

from app.errors import envelope

EXEMPT_PATHS = ("/health", "/ready", "/docs", "/redoc", "/openapi.json")


@dataclass
class _Bucket:
    tokens: float
    updated: float


class TokenBucketLimiter:
    """capacity tokens, refilled continuously at rate_per_minute / 60 tokens per second."""

    def __init__(
        self,
        rate_per_minute: int,
        capacity: int,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = 50_000,
    ) -> None:
        self.rate = rate_per_minute / 60.0
        self.capacity = float(capacity)
        self.clock = clock
        self.max_keys = max_keys
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def check(self, key: str, cost: float = 1.0) -> tuple[bool, float]:
        """Consume `cost` tokens. Returns (allowed, retry_after_seconds)."""
        now = self.clock()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                if len(self._buckets) >= self.max_keys:
                    self._prune(now)
                bucket = _Bucket(tokens=self.capacity, updated=now)
                self._buckets[key] = bucket
            bucket.tokens = min(self.capacity, bucket.tokens + (now - bucket.updated) * self.rate)
            bucket.updated = now
            if bucket.tokens >= cost:
                bucket.tokens -= cost
                return True, 0.0
            return False, (cost - bucket.tokens) / self.rate if self.rate > 0 else math.inf

    def _prune(self, now: float) -> None:
        full = [k for k, b in self._buckets.items() if b.tokens + (now - b.updated) * self.rate >= self.capacity]
        for k in full:
            del self._buckets[k]
        if len(self._buckets) >= self.max_keys:  # still full: drop oldest half
            for k, _ in sorted(self._buckets.items(), key=lambda kv: kv[1].updated)[: self.max_keys // 2]:
                del self._buckets[k]


class RateLimitMiddleware:
    """Pure ASGI middleware. Responds 429 with the standard error envelope and Retry-After."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        enabled: bool,
        per_ip_per_minute: int,
        per_session_per_minute: int,
        burst: int,
        trust_proxy: bool = False,
        trusted_proxy_hops: int = 1,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.app = app
        self.enabled = enabled
        self.trust_proxy = trust_proxy
        self.hops = max(1, int(trusted_proxy_hops))
        self.ip_limiter = TokenBucketLimiter(per_ip_per_minute, max(burst, 1), clock)
        self.session_limiter = TokenBucketLimiter(per_session_per_minute, max(burst // 2, 1), clock)

    def _client_ip(self, scope: Scope, headers: dict[str, str]) -> str:
        client = scope.get("client")
        peer = client[0] if client else "unknown"
        if self.trust_proxy and headers.get("x-forwarded-for"):
            # Each trusted proxy APPENDS the address it saw. With N trusted hops in front of the API (TRUSTED_PROXY_HOPS),
            # the N-th entry from the right is the address the outermost trusted proxy saw = the client. Entries further left
            # are client-supplied (QA-13). Fewer entries than hops = the request did not pass the whole trusted chain:
            # fall back to the TCP peer (one shared bucket - never a client-chosen key) (QA-20).
            entries = [e.strip() for e in headers["x-forwarded-for"].split(",")]
            if len(entries) >= self.hops and entries[-self.hops]:
                return entries[-self.hops][:64]
        return peer

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self.enabled or scope["type"] != "http" or scope.get("path", "").startswith(EXEMPT_PATHS):
            await self.app(scope, receive, send)
            return
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        ok, retry = self.ip_limiter.check(f"ip:{self._client_ip(scope, headers)}")
        scope_name = "ip"
        session = headers.get("x-demo-session")
        if ok and session:
            ok, retry = self.session_limiter.check(f"session:{session[:64]}")
            scope_name = "session"
        if ok:
            await self.app(scope, receive, send)
            return
        retry_after = max(1, math.ceil(retry))
        body = json.dumps(
            envelope("rate_limited", "Too many requests - please slow down.", {"scope": scope_name, "retry_after_s": retry_after})
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"retry-after", str(retry_after).encode()),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
