"""Request-body size cap with the standard error envelope (QA-03).

Starlette/FastAPI can cap bodies but answer with a plain-text 413; this pure ASGI middleware enforces the same cap
(Content-Length pre-check + byte counting for chunked bodies) and answers with `{"error": {"code": "payload_too_large", ...}}`.
Before it existed a 60 MB JSON body was read and parsed completely before the handler rejected it.
`path_limits` raises the cap for specific routes (the CV upload accepts `upload_max_bytes` + multipart overhead).
"""

from __future__ import annotations

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.errors import envelope

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class _BodyTooLarge(Exception):
    pass


def _contains_too_large(exc: BaseException) -> bool:
    if isinstance(exc, _BodyTooLarge):
        return True
    if isinstance(exc, BaseExceptionGroup):
        return any(_contains_too_large(e) for e in exc.exceptions)
    return False


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, *, max_bytes: int, path_limits: dict[str, int] | None = None) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.path_limits = path_limits or {}

    @staticmethod
    def _body(limit: int) -> bytes:
        return json.dumps(envelope("payload_too_large", "Request body is too large.", {"max_bytes": limit})).encode()

    async def _reject_start(self, send: Send, limit: int) -> None:
        body = self._body(limit)
        await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()), (b"connection", b"close")]})

    async def _reject(self, send: Send, limit: int) -> None:
        await self._reject_start(send, limit)
        await send({"type": "http.response.body", "body": self._body(limit)})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method", "GET") in SAFE_METHODS:
            await self.app(scope, receive, send)
            return
        limit = self.path_limits.get(scope.get("path", ""), self.max_bytes)
        declared = next((v for k, v in scope.get("headers", []) if k == b"content-length"), b"")
        if declared.isdigit() and int(declared) > limit:
            await self._reject(send, limit)
            return
        seen = 0
        started = False
        exceeded = False
        body_sent = False

        async def limited_receive() -> Message:
            nonlocal seen, exceeded
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
                    exceeded = True
                    raise _BodyTooLarge
            return message

        async def tracking_send(message: Message) -> None:
            # Whatever the inner app answers once the cap was hit (FastAPI turns the aborted read into a 400 "error parsing
            # the body"), the client gets the 413 envelope.
            nonlocal started, body_sent
            if exceeded:
                if message["type"] == "http.response.start" and not started:
                    started = True
                    await self._reject_start(send, limit)
                elif message["type"] == "http.response.body" and not body_sent:
                    body_sent = True
                    await send({"type": "http.response.body", "body": self._body(limit)})
                return
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except BaseException as exc:
            if not started and _contains_too_large(exc):
                await self._reject(send, limit)
                return
            raise
