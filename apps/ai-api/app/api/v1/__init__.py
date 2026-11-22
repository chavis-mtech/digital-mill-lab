"""Aggregate /api/v1 router (architect-owned). Module routers are owned per the build plan section 4."""

from fastapi import APIRouter

from app.api.v1 import (
    ai,
    alerts,
    copilot,
    cv,
    demo,
    energy,
    executive,
    kb,
    logistics,
    maintenance,
    meta,
    process,
    production,
    reports,
    roi,
    scenarios,
    traceability,
    workorders,
)

API_PREFIX = "/api/v1"

MODULES = (
    meta,
    demo,
    executive,
    alerts,
    production,
    process,
    ai,
    maintenance,
    workorders,
    logistics,
    energy,
    traceability,
    scenarios,
    roi,
    copilot,
    kb,
    cv,
    reports,
)

api_router = APIRouter(prefix=API_PREFIX)
for _module in MODULES:
    api_router.include_router(_module.router)


def iter_contract_routes():
    """Yield (full_path, APIRoute) for every /api/v1 operation.

    Walks the module routers directly (FastAPI >= 0.16x nests included routers lazily, so app.routes
    no longer lists APIRoute objects for included routers).
    """
    from fastapi.routing import APIRoute  # noqa: PLC0415

    for module in MODULES:
        for route in module.router.routes:
            if isinstance(route, APIRoute):
                yield API_PREFIX + route.path, route
