"""App factory. Run: uvicorn app.main:app --port 8000 (from apps/ai-api)."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app import __version__
from app.api.v1 import api_router
from app.config import PRODUCT_NAME, Settings, get_settings
from app.db.session import get_engine
from app.errors import install_error_handlers
from app.logging import RequestContextMiddleware, configure_logging
from app.schemas.meta import HealthResponse, ReadyCheck, ReadyResponse
from app.security.bodylimit import BodyLimitMiddleware
from app.security.headers import SecurityHeadersMiddleware
from app.security.ratelimit import RateLimitMiddleware

log = logging.getLogger("app")

DESCRIPTION = """
**Independent portfolio / concept demo on synthetic data. Not an official system of any company.**

Conventions: `/api/v1`, snake_case JSON, error envelope `{"error": {"code", "message", "details"}}`,
demo clock `as_of` + `scenario_id` query params, `X-Demo-Session` (uuid) and `X-Demo-Role` headers,
`provenance` on every numeric payload. Operation extensions `x-owner`, `x-status`, `x-permission`, `x-roles`
describe ownership and simulated RBAC.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=f"{PRODUCT_NAME} API",
        version=__version__,
        description=DESCRIPTION,
        openapi_tags=[{"name": "meta"}, {"name": "demo"}],
    )
    app.state.settings = settings
    app.dependency_overrides[get_settings] = lambda: settings
    install_error_handlers(app)

    # Middleware order: last added = outermost. Request context wraps everything (so 429s are logged too).
    app.add_middleware(  # innermost: reject oversized bodies (QA-03); the CV upload route may carry a file
        BodyLimitMiddleware,
        max_bytes=settings.max_body_bytes,
        path_limits={"/api/v1/cv/ffb-assessment": settings.upload_max_bytes + 1024 * 1024},
    )
    app.add_middleware(
        RateLimitMiddleware,
        enabled=settings.rate_limit_enabled,
        per_ip_per_minute=settings.rate_limit_per_ip_per_minute,
        per_session_per_minute=settings.rate_limit_per_session_per_minute,
        burst=settings.rate_limit_burst,
        trust_proxy=settings.trust_proxy_headers,
        trusted_proxy_hops=settings.trusted_proxy_hops,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Demo-Session", "X-Demo-Role", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)  # outermost: also covers 413/429/4xx produced further in

    @app.get("/health", response_model=HealthResponse, tags=["meta"], summary="Liveness (no DB access)")
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__)

    @app.get("/ready", response_model=ReadyResponse, tags=["meta"], summary="Readiness: DB reachable, schema present, data seeded",
             responses={503: {"model": ReadyResponse}})
    def ready():
        from fastapi.responses import JSONResponse  # noqa: PLC0415

        checks: list[ReadyCheck] = []
        try:
            engine = get_engine(settings.database_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                checks.append(ReadyCheck(name="database", ok=True, detail=engine.dialect.name))
                tables = set(inspect(conn).get_table_names())
                schema_ok = {"facilities", "process_hourly", "audit_logs"} <= tables
                checks.append(ReadyCheck(name="schema", ok=schema_ok, detail=f"{len(tables)} tables"))
                seeded = False
                if schema_ok:
                    seeded = (conn.execute(text("SELECT COUNT(*) FROM facilities")).scalar() or 0) > 0
                checks.append(ReadyCheck(name="seeded", ok=seeded, detail=None if seeded else "run `make seed`"))
        except Exception as exc:  # noqa: BLE001 - readiness must report, not raise
            checks.append(ReadyCheck(name="database", ok=False, detail=type(exc).__name__))
        ok = all(c.ok for c in checks)
        body = ReadyResponse(status="ready" if ok else "not_ready", checks=checks)
        return JSONResponse(status_code=200 if ok else 503, content=body.model_dump())

    app.include_router(api_router)
    log.info("app_started", extra={"env": settings.app_env, "db": settings.database_url.split(":")[0]})
    return app


app = create_app()
