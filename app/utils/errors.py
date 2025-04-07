"""Standardized error handling for the Day Trader application.

This module provides consistent error handling across the application to ensure
uniform error responses and logging.
"""

from __future__ import annotations

import logging

from flask import Flask, Response, current_app, jsonify, make_response
from werkzeug.exceptions import HTTPException

from app.utils.constants import (
    ApiConstants,
    PriceAnalysisConstants,
    StockConstants,
    TradingServiceConstants,
    UserConstants,
)

logger: logging.Logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base class for API errors with status code and payload."""

    # Data provider error messages
    FETCH_STOCK_INFO_ERROR: str = "Failed to fetch stock info"
    FETCH_INTRADAY_DATA_ERROR: str = "Failed to fetch intraday data"
    FETCH_DAILY_DATA_ERROR: str = "Failed to fetch daily data"
    PROCESS_STOCK_DATA_ERROR: str = "Failed to process stock data"
    PROCESS_INTRADAY_DATA_ERROR: str = "Failed to process intraday data"
    PROCESS_DAILY_DATA_ERROR: str = "Failed to process daily data"
    NO_PRICE_DATA_ERROR: str = "No price data available"
    NO_DAILY_PRICE_DATA_ERROR: str = "No daily price data available"
    LATEST_PRICE_ERROR: str = "Failed to get latest price"
    LATEST_DAILY_PRICE_ERROR: str = "Failed to get latest daily price"

    def __init__(
        self,
        message: str,
        status_code: int = ApiConstants.HTTP_BAD_REQUEST,
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


# Common validation error messages that can be shared across different error types
class CommonErrorMessages:
    """Common error messages that can be shared across validation error types."""

    # Common field validation
    FIELD_REQUIRED: str = "Field '{}' is required"

    # Symbol validation
    SYMBOL_REQUIRED: str = "Stock symbol is required"
    SYMBOL_LENGTH: str = (
        "Stock symbol must be between {} and {} characters: key={}, value={}"
    )
    SYMBOL_FORMAT: str = "Stock symbol must contain only letters and numbers"

    # Price validation
    NEGATIVE_PRICE: str = "Price cannot be negative: key={}, value={}"
    PRICE_POSITIVE: str = "Price must be greater than zero: key={}, value={}"

    # Date/time validation
    FUTURE_DATE: str = "Date cannot be in the future: key={}, value={}"
    FUTURE_TIMESTAMP: str = "Timestamp cannot be in the future: key={}, value={}"
    INVALID_DATE_FORMAT: str = "Invalid date format. Use YYYY-MM-DD"
    INVALID_DATETIME_FORMAT: str = "Invalid datetime format. Use YYYY-MM-DD HH:MM:SS"

    # Email validation
    EMAIL_REQUIRED: str = "Email is required: key={}, value={}"
    EMAIL_FORMAT: str = "Invalid email format: key={}, value={}"

    # Deletion confirmation
    CONFIRM_DELETION: str = "Must confirm deletion by setting 'confirm' to true"


class ValidationError(APIError):
    """Error raised when validation fails."""

    # Core validation messages - using common messages where possible
    FIELD_REQUIRED: str = CommonErrorMessages.FIELD_REQUIRED
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

    # Date and price validation - using common messages
    MISSING_PRICE_DATE: str = "Missing or invalid price_date"
    MISSING_PRICE_TIMESTAMP: str = "Missing or invalid price_timestamp"
    MISSING_PRICE_INTERVAL: str = "Missing or invalid price_interval"
    INVALID_DATE_FORMAT: str = CommonErrorMessages.INVALID_DATE_FORMAT
    INVALID_DATETIME_FORMAT: str = CommonErrorMessages.INVALID_DATETIME_FORMAT

    # Transaction validation specific messages
    SHARES_POSITIVE: str = "Shares must be greater than zero: key={}, value={}"
    PRICE_POSITIVE: str = CommonErrorMessages.PRICE_POSITIVE
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
    INVALID_STATE: str = "Invalid transaction state: key={}, value={}"
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
        status_code: int = ApiConstants.HTTP_BAD_REQUEST,
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

    # User model validation errors - using common messages where possible
    USERNAME_REQUIRED: str = "Username is required: key={}, value={}"
    USERNAME_LENGTH: str = (
        f"Username must be between {UserConstants.MIN_USERNAME_LENGTH} "
        f"and {UserConstants.MAX_USERNAME_LENGTH} characters: "
        "key={key}, value={value}"
    )
    USERNAME_FORMAT: str = (
        "Username can only contain letters, numbers, underscores, and hyphens: "
        "key={key}, value={value}"
    )
    USERNAME_REQUIREMENTS: str = (
        f"Username ({UserConstants.MIN_USERNAME_LENGTH}-"
        f"{UserConstants.MAX_USERNAME_LENGTH} characters, "
        "letters, numbers, underscores, hyphens): "
        "key={key}, value={value}"
    )
    EMAIL_REQUIRED: str = CommonErrorMessages.EMAIL_REQUIRED
    EMAIL_FORMAT: str = CommonErrorMessages.EMAIL_FORMAT
    PASSWORD_REQUIRED: str = "Password is required:"  # noqa: S105
    PASSWORD_LENGTH: str = (
        f"Password must be at least {UserConstants.MIN_PASSWORD_LENGTH} characters"
    )
    PASSWORD_REQUIREMENTS: str = (
        f"Password (min {UserConstants.MIN_PASSWORD_LENGTH} chars, "
        "uppercase, lowercase, number required)"
    )
    PASSWORD_COMPLEXITY: str = (
        "Password must contain at least one uppercase letter, "  # noqa: S105
        "one lowercase letter, and one digit"
    )
    PASSWORD_NOT_READABLE: str = "Password is not a readable attribute"  # noqa: S105


class StockError(ValidationError):
    """Errors specific to stock model and operations."""

    # Stock model validation errors - using common messages where possible
    SYMBOL_EXISTS: str = "Stock with symbol already exists: key={}, value={}"
    SYMBOL_REQUIRED: str = CommonErrorMessages.SYMBOL_REQUIRED
    SYMBOL_LENGTH: str = (
        f"Stock symbol must be {StockConstants.MAX_SYMBOL_LENGTH} "
        "characters or less: key={{key}}, value={{value}}"
    )
    SYMBOL_FORMAT: str = CommonErrorMessages.SYMBOL_FORMAT
    NAME_LENGTH: str = (
        f"Stock name must be {StockConstants.MAX_NAME_LENGTH} "
        "characters or less: key={{key}}, value={{value}}"
    )
    SECTOR_LENGTH: str = (
        f"Stock sector must be {StockConstants.MAX_SECTOR_LENGTH} "
        "characters or less: key={{key}}, value={{value}}"
    )
    DESCRIPTION_LENGTH: str = (
        f"Stock description must be {StockConstants.MAX_DESCRIPTION_LENGTH} "
        "characters or less: key={{key}}, value={{value}}"
    )
    CONFIRM_DELETION: str = CommonErrorMessages.CONFIRM_DELETION
    HAS_SERVICES: str = (
        "Cannot delete stock '{}' because it is used by {} trading service(s): "
        "key={}, value={}"
    )
    HAS_TRANSACTIONS: str = (
        "Cannot delete stock '{}' because it has {} associated transaction(s): "
        "key={}, value={}"
    )


class StockPriceError(ValidationError):
    """Errors specific to stock price models and operations."""

    # Stock price validation errors - using common messages where possible
    INVALID_SOURCE: str = "Invalid price source: key={}, value={}"
    FUTURE_TIMESTAMP: str = CommonErrorMessages.FUTURE_TIMESTAMP
    FUTURE_DATE: str = CommonErrorMessages.FUTURE_DATE
    INVALID_INTERVAL: str = (
        "Invalid interval key={}, value={}. Must be one of: 1, 5, 15, 30, 60"
    )
    NEGATIVE_PRICE: str = CommonErrorMessages.NEGATIVE_PRICE
    HIGH_LOW_PRICE: str = "High price cannot be less than low price: key={}, value={}"
    LOW_HIGH_PRICE: str = (
        "Low price cannot be greater than high price: key={}, value={}"
    )
    HIGH_OPEN_PRICE: str = "High price cannot be less than open price: key={}, value={}"
    HIGH_CLOSE_PRICE: str = (
        "High price cannot be less than close price: key={}, value={}"
    )
    LOW_OPEN_PRICE: str = (
        "Low price cannot be greater than open price: key={}, value={}"
    )
    LOW_CLOSE_PRICE: str = (
        "Low price cannot be greater than close price: key={}, value={}"
    )

    # Technical analysis errors
    INSUFFICIENT_DATA_POINTS: str = (
        f"Not enough data points for analysis. Minimum "
        f"required: {PriceAnalysisConstants.MIN_DATA_POINTS}"
    )
    MA_PERIOD_TOO_LONG: str = (
        f"Moving average period too long. Maximum allowed: "
        f"{PriceAnalysisConstants.MAX_MA_PERIOD}"
    )
    RSI_PERIOD_TOO_SHORT: str = (
        f"RSI period too short. Minimum required: "
        f"{PriceAnalysisConstants.RSI_MIN_PERIODS}"
    )

    # Deletion validation - using common messages
    CONFIRM_DELETION: str = CommonErrorMessages.CONFIRM_DELETION
    DAILY_PRICE_NOT_FOUND: str = "Daily price record not found"
    INTRADAY_PRICE_NOT_FOUND: str = "Intraday price record not found"

    # Recent data protection
    RECENT_DAILY_DATA: str = (
        "Cannot delete recent price data (less than 30 days old). "
        "This data may be in use for active analyses."
    )
    RECENT_INTRADAY_DATA: str = (
        "Cannot delete recent price data (less than 7 days old). "
        "This data may be in use for active analyses."
    )


class TransactionError(ValidationError):
    """Errors specific to trading transaction model and operations."""

    # Transaction model validation errors - using common messages
    SYMBOL_REQUIRED: str = CommonErrorMessages.SYMBOL_REQUIRED
    INVALID_STATE: str = "Invalid transaction state: {}"
    SHARES_POSITIVE: str = "Shares must be greater than zero"
    CONFIRM_DELETION: str = CommonErrorMessages.CONFIRM_DELETION


class TradingServiceError(ValidationError):
    """Errors specific to the trading service module."""

    # Trading service validation error messages - using common messages where possible
    INITIAL_BALANCE: str = "Initial balance must be greater than zero: key={}, value={}"
    CURRENT_BALANCE: str = "Current balance must be greater than zero: key={}, value={}"
    MINIMUM_BALANCE: str = "Minimum balance must be non-negative: key={}, value={}"
    REQUIRED_FIELD: str = CommonErrorMessages.FIELD_REQUIRED
    INSUFFICIENT_PRICE_DATA: str = "Not enough price data for stock {} to backtest"
    CREATE_SERVICE: str = "Could not create trading service: {}"
    UPDATE_SERVICE: str = "Could not update trading service: {}"
    BACKTEST_FAILED: str = "Backtest failed: {}"
    NO_SELL_NO_SHARES: str = "Cannot set mode to SELL when no shares are held"
    NO_BUY_MIN_BALANCE: str = (
        "Cannot set mode to BUY when balance is at or below minimum"
    )
    DELETE_WITH_TRANSACTIONS: str = (
        "Cannot delete trading service with active transactions. Cancel or complete "
        "them first."
    )
    SYMBOL_REQUIRED: str = CommonErrorMessages.SYMBOL_REQUIRED
    SYMBOL_LENGTH: str = (
        f"Stock symbol must be between {StockConstants.MIN_SYMBOL_LENGTH} "
        f"and {StockConstants.MAX_SYMBOL_LENGTH} characters: "
        "key={key}, value={value}"
    )
    SYMBOL_FORMAT: str = CommonErrorMessages.SYMBOL_FORMAT
    INVALID_STATE: str = "Invalid service state: key={}, value={}"
    INVALID_MODE: str = "Invalid trading mode: key={}, value={}"
    ALLOCATION_PERCENT: str = (
        f"Allocation percent must be between "
        f"{TradingServiceConstants.MIN_ALLOCATION_PERCENT} "
        f"and {TradingServiceConstants.MAX_ALLOCATION_PERCENT}: "
        "key={key}, value={value}"
    )
    BUY_THRESHOLD_NEGATIVE: str = (
        f"Buy threshold must be non-negative (minimum: "
        f"{TradingServiceConstants.MIN_BUY_THRESHOLD})"
    )
    SELL_THRESHOLD_NEGATIVE: str = (
        f"Sell threshold must be non-negative (minimum: "
        f"{TradingServiceConstants.MIN_SELL_THRESHOLD})"
    )
    CONFIRM_DELETION: str = CommonErrorMessages.CONFIRM_DELETION


class AuthorizationError(APIError):
    """Error raised for authorization/permission issues."""

    # Common authorization error messages
    ADMIN_ONLY: str = "Only admins can grant admin privileges"
    NOT_AUTHORIZED: str = "Not authorized to access this resource"
    ACCOUNT_INACTIVE: str = "Account is inactive"

    def __init__(
        self,
        message: str = NOT_AUTHORIZED,
        status_code: int = ApiConstants.HTTP_UNAUTHORIZED,
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
        status_code: int = ApiConstants.HTTP_NOT_FOUND,
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
        status_code: int = ApiConstants.HTTP_BAD_REQUEST,
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
        "status_code": ApiConstants.HTTP_BAD_REQUEST,
    }, ApiConstants.HTTP_BAD_REQUEST
