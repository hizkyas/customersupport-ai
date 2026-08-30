"""
Custom exception hierarchy for the AI Customer Support platform.

All application exceptions extend AppException, which carries a structured
error payload (code, message, details) and a status code.  Global handlers
in main.py convert these into a consistent JSON envelope.
"""

from typing import Any, Dict, Optional


class AppException(Exception):
    """Base application exception with structured error payload."""

    def __init__(
        self,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        message: str = "An unexpected error occurred",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(AppException):
    """Resource not found (404)."""

    def __init__(self, resource: str = "Resource", resource_id: Any = None):
        details = {}
        if resource_id is not None:
            details["resource_id"] = str(resource_id)
        super().__init__(
            status_code=404,
            error_code="NOT_FOUND",
            message=f"{resource} not found",
            details=details,
        )


class ForbiddenError(AppException):
    """Access denied (403)."""

    def __init__(self, message: str = "You do not have permission to perform this action"):
        super().__init__(
            status_code=403,
            error_code="FORBIDDEN",
            message=message,
        )


class ConflictError(AppException):
    """Conflicting state or duplicate resource (409)."""

    def __init__(self, message: str = "Resource conflict"):
        super().__init__(
            status_code=409,
            error_code="CONFLICT",
            message=message,
        )


class ValidationError(AppException):
    """Business-logic validation failure (422)."""

    def __init__(self, message: str = "Validation error", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=422,
            error_code="VALIDATION_ERROR",
            message=message,
            details=details or {},
        )


class RateLimitExceededError(AppException):
    """Too many requests (429)."""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            message="Too many requests. Please try again later.",
            details={"retry_after_seconds": retry_after},
        )
