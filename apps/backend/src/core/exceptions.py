"""Platform-wide typed exceptions.

Every domain exception (including `domains/auth/exceptions.AuthError`)
subclasses `AppError` so `core/error_handlers.py` can render all of them
through a single response envelope. `code` is the stable, machine-readable
identifier the frontend branches on — see `docs/ERROR_CODES.md`.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    status_code: int = 400
    code: str = "APP_ERROR"

    def __init__(self, message: str | None = None, *, details: dict[str, Any] | None = None) -> None:
        self.message = message or self.__class__.__doc__ or "An error occurred"
        self.details = details
        super().__init__(self.message)


class NotFound(AppError):
    """The requested resource was not found."""

    status_code = 404
    code = "NOT_FOUND"


class Forbidden(AppError):
    """You do not have permission to access this resource."""

    status_code = 403
    code = "FORBIDDEN"


class Conflict(AppError):
    """The request conflicts with the resource's current state."""

    status_code = 409
    code = "CONFLICT"


class ValidationFailed(AppError):
    """The request failed validation."""

    status_code = 422
    code = "VALIDATION_FAILED"


class ExternalServiceError(AppError):
    """An upstream service failed or is unavailable."""

    status_code = 502
    code = "EXTERNAL_SERVICE_ERROR"
