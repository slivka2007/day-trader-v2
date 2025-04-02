"""Standardized error handling for the Day Trader application.

This module provides consistent error handling across the application to ensure
uniform error responses and logging.
"""

from __future__ import annotations

import logging

from flask import Flask, Response, current_app, jsonify, make_response
from werkzeug.exceptions import HTTPException

logger: logging.Logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base class for API errors with status code and payload."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        payload: dict[str, any] | None = None,
    ) -> None:
        """Initialize API error with message, status code, and optional payload.

        Args:
            message: Error message
            status_code: HTTP status code
            payload: Additional error context

        """
        super().__init__(message)
        self.message: str = message
        self.status_code: int = status_code
        self.payload: dict[str, any] = payload or {}

    def to_dict(self) -> dict[str, any]:
        """Convert error to dictionary representation."""
        result: dict[str, any] = {
            "error": True,
            "message": self.message,
            "status_code": self.status_code,
        }

        if self.payload:
            result.update(self.payload)

        return result


class ValidationError(APIError):
    """Error raised when validation fails."""

    def __init__(
        self,
        message: str,
        errors: dict[str, any] | None = None,
        status_code: int = 400,
    ) -> None:
        """Initialize validation error with message and validation errors.

        Args:
            message: Error message
            errors: Dictionary of validation errors
            status_code: HTTP status code

        """
        super().__init__(message, status_code, {"validation_errors": errors or {}})


class AuthorizationError(APIError):
    """Error raised for authorization/permission issues."""

    def __init__(
        self,
        message: str = "Unauthorized access",
        status_code: int = 401,
        payload: dict[str, any] | None = None,
    ) -> None:
        """Initialize authorization error.

        Args:
            message: Error message
            status_code: HTTP status code
            payload: Additional error context

        """
        super().__init__(message, status_code, payload)


class ResourceNotFoundError(APIError):
    """Error raised when a requested resource is not found."""

    def __init__(
        self,
        resource_type: str,
        resource_id: str | int,
        status_code: int = 404,
        payload: dict[str, any] | None = None,
    ) -> None:
        """Initialize resource not found error.

        Args:
            resource_type: Type of resource that was not found
            resource_id: ID of the resource that was not found
            status_code: HTTP status code
            payload: Additional error context

        """
        message: str = f"{resource_type} with ID {resource_id} not found"
        payload_data: dict[str, any] = {
            "resource_type": resource_type,
            "resource_id": resource_id,
        }
        if payload:
            payload_data.update(payload)
        super().__init__(message, status_code, payload_data)


class BusinessLogicError(APIError):
    """Error raised for business logic violations."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        payload: dict[str, any] | None = None,
    ) -> None:
        """Initialize business logic error.

        Args:
            message: Error message
            status_code: HTTP status code
            payload: Additional error context

        """
        super().__init__(message, status_code, payload)


def api_error_handler(error: APIError | Exception) -> Response:
    """Global error handler for API errors.

    Args:
        error: The error that occurred

    Returns:
        Flask response with standardized error format

    """
    # Handle our custom API errors
    if isinstance(error, APIError):
        logger.warning("API Error: %s (%d)", error.message, error.status_code)
        return make_response(jsonify(error.to_dict()), error.status_code)

    # Handle standard HTTP exceptions
    if isinstance(error, HTTPException):
        logger.warning("HTTP Error: %s (%d)", error.description, error.code)
        return make_response(
            jsonify(
                {
                    "error": True,
                    "message": error.description,
                    "status_code": error.code,
                },
            ),
            error.code,
        )

    # Handle generic exceptions as 500 internal server errors
    logger.error("Unhandled Exception: %s", str(error), exc_info=True)

    # In production, don't expose error details
    if current_app.config.get("DEBUG", False):
        error_message = str(error)
    else:
        error_message = "An internal server error occurred"

    return make_response(
        jsonify({"error": True, "message": error_message, "status_code": 500}),
        500,
    )


def register_error_handlers(app: Flask) -> None:
    """Register error handlers with a Flask app.

    Args:
        app: Flask application instance

    """
    app.register_error_handler(APIError, api_error_handler)
    app.register_error_handler(Exception, api_error_handler)

    # Register specific HTTP error codes
    for error_code in [400, 401, 403, 404, 405, 500]:
        app.register_error_handler(error_code, api_error_handler)

    logger.info("Registered API error handlers")


def handle_validation_error(errors: dict[str, any]) -> tuple[dict[str, any], int]:
    """Handle validation errors from marshmallow schemas.

    Args:
        errors: Validation errors from marshmallow

    Returns:
        JSON response and status code

    """
    logger.warning("Validation error: %s", errors)
    return {
        "error": True,
        "message": "Validation error",
        "validation_errors": errors,
        "status_code": 400,
    }, 400
