"""Public error types for integration API / MCP (no DB details)."""
from __future__ import annotations


class IntegrationError(Exception):
    """Base integration error with a stable public code."""

    code: str = "error"
    http_status: int = 400

    def __init__(self, message: str = "Request could not be completed"):
        self.message = message
        super().__init__(message)


class UnauthorizedError(IntegrationError):
    code = "unauthorized"
    http_status = 401

    def __init__(self, message: str = "Not authenticated"):
        super().__init__(message)


class ForbiddenError(IntegrationError):
    code = "forbidden"
    http_status = 403

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message)


class NotFoundError(IntegrationError):
    code = "not_found"
    http_status = 404

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message)


class ValidationError(IntegrationError):
    code = "validation_error"
    http_status = 422

    def __init__(self, message: str = "Looks like we still need a few details before we can continue."):
        super().__init__(message)


class RateLimitedError(IntegrationError):
    code = "rate_limited"
    http_status = 429

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message)


class FeatureDisabledError(IntegrationError):
    code = "feature_disabled"
    http_status = 503

    def __init__(self, message: str = "Integration API is not enabled"):
        super().__init__(message)
