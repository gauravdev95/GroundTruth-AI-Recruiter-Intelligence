"""Registers exception -> JSON response handlers on the FastAPI app.

Every error response — domain (`AppError` and its subclasses, including
`AuthError`), plain `HTTPException` (e.g. `get_current_user`/`require_role`
in `domains/auth/dependencies.py`, or FastAPI's own 404/405), request-
validation (Pydantic), and unexpected — renders through the same envelope:

    {"error": {"code": str, "message": str, "details": dict | null}}

`request_id` is always included in `details` so a user-reported error can be
traced back to the exact log lines for that request (see `core/request_id.py`).
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.core.exceptions import AppError
from src.core.request_id import get_request_id

logger = structlog.get_logger(__name__)

# Generic codes for plain HTTPExceptions that don't carry their own `code`
# (unlike AppError subclasses) — keyed by status code, falling back to
# `HTTP_<status>` for anything not explicitly listed.
_HTTP_STATUS_CODES = {
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    429: "RATE_LIMITED",
}


def _envelope(*, code: str, message: str, details: dict | None = None) -> dict:
    request_id = get_request_id()
    merged_details = dict(details) if details else {}
    if request_id is not None:
        merged_details["request_id"] = request_id
    return {"error": {"code": code, "message": message, "details": merged_details or None}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code=exc.code, message=exc.message, details=exc.details),
        )

    async def _handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_STATUS_CODES.get(exc.status_code, f"HTTP_{exc.status_code}")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code=code, message=message),
            headers=exc.headers,
        )

    # Registered under both: FastAPI's own `HTTPException` (what
    # `domains/auth/dependencies.py` raises) is a subclass of Starlette's
    # (what Starlette's router raises internally for 404/405) — Starlette's
    # dispatcher does exact-class lookup with MRO fallback, so both keys are
    # needed to cover every raise site with one handler function.
    app.add_exception_handler(HTTPException, _handle_http_exception)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                code="VALIDATION_FAILED",
                message="The request failed validation",
                details={"errors": jsonable_encoder(exc.errors())},
            ),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", path=str(request.url), error=str(exc))
        return JSONResponse(
            status_code=500,
            content=_envelope(code="INTERNAL_ERROR", message="An unexpected error occurred"),
        )
