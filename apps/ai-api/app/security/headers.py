"""Security response headers for API responses (QA-02).

Pure ASGI middleware, outermost so that 4xx/429 produced by inner middleware are covered as well.
Scope:
  * every response: `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`
  * `/api/*` responses: `Cache-Control: no-store` (session-scoped data must not be cached by shared caches),
    `Content-Security-Policy` (JSON: `default-src 'none'`; HTML print views: no scripts, inline styles only),
    `X-Frame-Options`
  * `/docs`, `/redoc`, `/openapi.json` (interactive docs load their own assets) only get the first two.
Existing headers set by a handler are never overwritten. HSTS is intentionally NOT set here: it is only meaningful
behind TLS and is the reverse proxy's job (docs/DEPLOYMENT.md).
"""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

CSP_JSON = b"default-src 'none'; frame-ancestors 'none'"
CSP_HTML = b"default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        is_api = scope.get("path", "").startswith("/api/")

        async def _send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {k.lower() for k, _ in headers}
                add: list[tuple[bytes, bytes]] = [(b"x-content-type-options", b"nosniff"), (b"referrer-policy", b"no-referrer")]
                if is_api:
                    ctype = next((v for k, v in headers if k.lower() == b"content-type"), b"")
                    is_html = ctype.lower().startswith(b"text/html")
                    add += [
                        (b"cache-control", b"no-store"),
                        (b"content-security-policy", CSP_HTML if is_html else CSP_JSON),
                        (b"x-frame-options", b"SAMEORIGIN" if is_html else b"DENY"),
                    ]
                headers += [(k, v) for k, v in add if k not in present]
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, _send)
