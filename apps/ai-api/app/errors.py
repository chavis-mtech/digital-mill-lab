"""Uniform error envelope: {"error": {"code", "message", "details"}} for every non-2xx response."""

from __future__ import annotations

import logging
from typing import Any, NoReturn

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("app.errors")


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: Any = None, headers: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


def envelope(code: str, message: str, details: Any = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


def error_response(status_code: int, code: str, message: str, details: Any = None, headers: dict | None = None):
    return JSONResponse(status_code=status_code, content=envelope(code, message, details), headers=headers)


def not_implemented(owner: str, task: str | None = None, note: str | None = None) -> NoReturn:
    """Contract stub: the endpoint exists in OpenAPI, its owner agent has not implemented it yet."""
    raise ApiError(
        501,
        "not_implemented",
        "This endpoint is part of the API contract but is not implemented yet (status: planned).",
        {"owner": owner, "task": task, "status": "planned", "note": note},
    )


def not_found(entity: str, ident: Any) -> NoReturn:
    raise ApiError(404, "not_found", f"{entity} not found", {"entity": entity, "id": ident})


def forbidden(message: str, details: Any = None) -> NoReturn:
    raise ApiError(403, "forbidden", message, details)


def bad_request(code: str, message: str, details: Any = None) -> NoReturn:
    raise ApiError(422, code, message, details)


_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limited",
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return error_response(exc.status_code, exc.code, exc.message, exc.details, exc.headers)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        code = _STATUS_CODES.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else code.replace("_", " ")
        return error_response(exc.status_code, code, message, None, getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        details = [
            {"loc": list(e.get("loc", [])), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()
        ]
        return error_response(422, "validation_error", "Request validation failed", details)

    @app.exception_handler(OverflowError)
    async def _overflow(request: Request, exc: OverflowError):
        # QA-04: an integer id / number beyond the database or float range is a client error, not a server fault
        log.warning("value_out_of_range", extra={"path": request.url.path})
        return error_response(422, "value_out_of_range", "A numeric value is outside the supported range.", None)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("unhandled_error", extra={"path": request.url.path})
        return error_response(500, "internal_error", "An unexpected error occurred.", None)
