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

    # Common validation error messages
    FIELD_REQUIRED: str = "Field '{}' is required"
    USERNAME_EXISTS: str = "Username '{}' already exists"
    EMAIL_EXISTS: str = "Email '{}' already exists"
    INVALID_PASSWORD: str = "Current password is incorrect"  # noqa: S105
    CREATE_USER_ERROR: str = "Could not create user: {}"
    UPDATE_USER_ERROR: str = "Could not update user: {}"
    TOGGLE_STATUS_ERROR: str = "Could not toggle user status: {}"
    GRANT_ADMIN_ERROR: str = "Could not grant admin privileges: {}"
    DELETE_USER_ERROR: str = "Could not delete user: {}"
    CHANGE_PASSWORD_ERROR: str = "Could not change password: {}"  # noqa: S105

    # User validation specific messages
    INVALID_USERNAME: str = "Invalid username format"
    PASSWORD_NUMBER: str = "Password requires a number"  # noqa: S105
    PASSWORD_UPPER: str = "Password requires uppercase"  # noqa: S105
    PASSWORD_LOWER: str = "Password requires lowercase"  # noqa: S105
    PASSWORD_SPECIAL: str = "Password requires special char"  # noqa: S105
    PASSWORDS_MISMATCH: str = "Passwords do not match"
    MUST_CONFIRM: str = "Must confirm deletion"
    USER_NOT_FOUND: str = "User not found"
    ACTIVE_SERVICES: str = "Cannot delete: active services"
    INVALID_CREDENTIALS: str = "Invalid username or password"

    # Transaction validation specific messages
    SHARES_POSITIVE: str = "Shares must be greater than zero"
    PRICE_POSITIVE: str = "Purchase price must be greater than zero"
    INSUFFICIENT_FUNDS: str = (
        "Insufficient funds. Required: ${:.2f}, Available: ${:.2f}"
    )
    SERVICE_NOT_BUYING: str = (
        "Service is not in a state that allows buying (current state: {}, mode: {})"
    )
    SERVICE_NOT_FOUND: str = "Trading service with ID {} not found"
    TRANSACTION_NOT_FOUND: str = "Transaction with ID {} not found"
    TRANSACTION_NOT_OPEN: str = (
        "Transaction cannot be completed because it is not open (current state: {})"
    )
    CANNOT_DELETE_OPEN: str = "Cannot delete an open transaction. Cancel it first."
    TRANSACTION_NOT_CANCELLABLE: str = (
        "Transaction cannot be cancelled because it is in state: {}"
    )
    INVALID_STATE: str = "Invalid transaction state: {}"
    USER_NOT_OWNER: str = "User {} does not own the service for transaction {}"
    CREATE_BUY_ERROR: str = "Could not create buy transaction: {}"
    COMPLETE_ERROR: str = "Could not complete transaction: {}"
    CANCEL_ERROR: str = "Could not cancel transaction: {}"
    DELETE_ERROR: str = "Could not delete transaction: {}"
    UPDATE_NOTES_ERROR: str = "Could not update transaction notes: {}"

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


class UserError(ValidationError):
    """Errors specific to user model and operations."""

    # User model validation errors
    USERNAME_REQUIRED: str = "Username is required"
    USERNAME_LENGTH: str = "Username must be between {} and {} characters"
    USERNAME_FORMAT: str = (
        "Username can only contain letters, numbers, underscores, and hyphens"
    )
    EMAIL_REQUIRED: str = "Email is required"
    EMAIL_FORMAT: str = "Invalid email format"
    PASSWORD_REQUIRED: str = "Password is required"  # noqa: S105
    PASSWORD_LENGTH: str = "Password must be at least {} characters"
    PASSWORD_COMPLEXITY: str = (
        "Password must contain at least one uppercase letter, "  # noqa: S105
        "one lowercase letter, and one digit"
    )
    PASSWORD_NOT_READABLE: str = "Password is not a readable attribute"  # noqa: S105


class StockError(ValidationError):
    """Errors specific to stock model and operations."""

    # Stock model validation errors
    SYMBOL_REQUIRED: str = "Stock symbol is required"
    SYMBOL_LENGTH: str = "Stock symbol must be {} characters or less"


class StockPriceError(ValidationError):
    """Errors specific to stock price models and operations."""

    # Stock price validation errors (common)
    INVALID_SOURCE: str = "Invalid price source: {}"

    # Intraday price validation errors
    FUTURE_TIMESTAMP: str = "Timestamp cannot be in the future: {}"
    INVALID_INTERVAL: str = "Invalid interval {}. Must be one of: 1, 5, 15, 30, 60"

    # Daily price validation errors
    FUTURE_DATE: str = "Price date cannot be in the future: {}"
    NEGATIVE_PRICE: str = "{} cannot be negative"
    HIGH_LOW_PRICE: str = "High price cannot be less than low price"
    LOW_HIGH_PRICE: str = "Low price cannot be greater than high price"


class TransactionError(ValidationError):
    """Errors specific to trading transaction model and operations."""

    # Transaction model validation errors
    SYMBOL_REQUIRED: str = "Stock symbol is required"
    INVALID_STATE: str = "Invalid transaction state: {}"
    SHARES_POSITIVE: str = "Shares must be greater than zero"


class TradingServiceError(ValidationError):
    """Errors specific to the trading service module."""

    # Trading service validation error messages
    INITIAL_BALANCE: str = "Initial balance must be greater than zero"
    REQUIRED_FIELD: str = "Field '{}' is required"
    INSUFFICIENT_PRICE_DATA: str = "Not enough price data for stock {} to backtest"
    CREATE_SERVICE: str = "Could not create trading service: {}"
    UPDATE_SERVICE: str = "Could not update trading service: {}"
    BACKTEST_FAILED: str = "Backtest failed: {}"
    NO_SELL_NO_SHARES: str = "Cannot set mode to SELL when no shares are held"
    NO_BUY_MIN_BALANCE: str = (
        "Cannot set mode to BUY when balance is at or below minimum"
    )
    DELETE_WITH_TRANSACTIONS: str = (
        "Cannot delete trading service with active transactions. Cancel or complete them "
        "first."
    )
    # Additional trading service validation errors
    SYMBOL_REQUIRED: str = "Stock symbol is required"
    INVALID_STATE: str = "Invalid service state: {}"
    INVALID_MODE: str = "Invalid trading mode: {}"
    ALLOCATION_PERCENT: str = "Allocation percent must be between 0 and {}"


class AuthorizationError(APIError):
    """Error raised for authorization/permission issues."""

    # Common authorization error messages
    ADMIN_ONLY = "Only admins can grant admin privileges"

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

    # Error message template
    NOT_FOUND = "{} with ID {} not found"

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
        message: str = self.NOT_FOUND.format(resource_type, resource_id)
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
