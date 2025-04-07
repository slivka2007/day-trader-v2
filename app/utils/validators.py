"""Validation utilities.

This module provides utility functions for validating different types of data
across the application. These functions help maintain consistency and DRY principles
by centralizing common validation logic.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from enum import Enum

from datetime import date, datetime
from typing import Callable, TypeVar

from app.utils.constants import StockConstants
from app.utils.current_datetime import get_current_date, get_current_datetime
from app.utils.errors import (
    CommonErrorMessages,
    StockError,
    TradingServiceError,
    TransactionError,
    UserError,
    ValidationError,
)

# Set up logging
logger: logging.Logger = logging.getLogger(__name__)

# Type variable for the error classes
ErrorType = TypeVar("ErrorType", bound=ValidationError)

# Common error attribute names used across validation functions
ERROR_ATTR_SYMBOL_REQUIRED = "SYMBOL_REQUIRED"
ERROR_ATTR_SYMBOL_LENGTH = "SYMBOL_LENGTH"
ERROR_ATTR_SYMBOL_FORMAT = "SYMBOL_FORMAT"
ERROR_ATTR_INVALID_SOURCE = "INVALID_SOURCE"
ERROR_ATTR_FUTURE_DATE = "FUTURE_DATE"
ERROR_ATTR_FUTURE_TIMESTAMP = "FUTURE_TIMESTAMP"
ERROR_ATTR_NEGATIVE_PRICE = "NEGATIVE_PRICE"
ERROR_ATTR_EMAIL_REQUIRED = "EMAIL_REQUIRED"
ERROR_ATTR_EMAIL_FORMAT = "EMAIL_FORMAT"
ERROR_ATTR_VALUE_POSITIVE = "PRICE_POSITIVE"
ERROR_ATTR_VALUE_NEGATIVE = "NEGATIVE_PRICE"

# Default error messages
DEFAULT_SYMBOL_REQUIRED = "Stock symbol is required"
DEFAULT_EMAIL_REQUIRED = "Email is required"


def _get_error_message(
    error_class: type[ErrorType],
    error_attr: str,
    default_message: str,
    **format_args: any,
) -> str:
    """Get an error message from the error class, with fallback to default message.

    Args:
        error_class: The error class to look for the error message
        error_attr: The attribute name of the error message
        default_message: Default message to use if error_attr not found
        **format_args: Format arguments to apply to the message

    Returns:
        Formatted error message string

    """
    if hasattr(error_class, error_attr):
        error_msg: any = getattr(error_class, error_attr)
        if format_args:
            try:
                return error_msg.format(**format_args)
            except (KeyError, IndexError):
                # If formatting fails, return unformatted message
                return error_msg
        return error_msg
    return default_message


def validate_stock_symbol(
    symbol: str,
    error_class: type[ErrorType],
    key: str = "symbol",
    max_length: int = StockConstants.MAX_SYMBOL_LENGTH,
) -> str:
    """Validate a stock symbol.

    This function centralizes the validation logic for stock symbols, ensuring
    that the same validation rules are applied consistently throughout the application.

    Args:
        symbol: The stock symbol to validate
        error_class: The error class to use for raising validation errors
        key: The attribute name being validated (for error messages)
        max_length: Maximum allowed length for the symbol

    Returns:
        The validated symbol (converted to uppercase)

    Raises:
        ValidationError: If the symbol is invalid (using the specified error_class)

    """
    # Check if symbol is empty
    if not symbol:
        error_msg = _get_error_message(
            error_class,
            ERROR_ATTR_SYMBOL_REQUIRED,
            CommonErrorMessages.SYMBOL_REQUIRED,
        )
        raise error_class(error_msg)

    # Convert to uppercase
    cleaned_symbol: str = symbol.strip().upper()

    # Check length
    if len(cleaned_symbol) > max_length:
        error_msg = _get_error_message(
            error_class,
            ERROR_ATTR_SYMBOL_LENGTH,
            CommonErrorMessages.SYMBOL_LENGTH.format(
                1,
                max_length,
                key=key,
                value=cleaned_symbol,
            ),
            key=key,
            value=cleaned_symbol,
        )
        raise error_class(error_msg)

    # Check format (only letters and numbers)
    if not re.match(r"^[A-Z0-9]+$", cleaned_symbol):
        error_msg = _get_error_message(
            error_class,
            ERROR_ATTR_SYMBOL_FORMAT,
            CommonErrorMessages.SYMBOL_FORMAT,
            key=key,
            value=cleaned_symbol,
        )
        raise error_class(error_msg)

    return cleaned_symbol


def validate_enum_value(
    value: str,
    enum_class: type[Enum],
    error_class: type[ErrorType],
    key: str,
    error_attr: str = "INVALID_VALUE",
) -> str:
    """Validate a value against an enumeration.

    Args:
        value: The value to validate
        enum_class: The enumeration class to validate against
        error_class: The error class to use for raising validation errors
        key: The attribute name being validated (for error messages)
        error_attr: The attribute name of the error message in the error class

    Returns:
        The validated value

    Raises:
        ValidationError: If the value is not valid for the enumeration

    """
    if value and not hasattr(enum_class, "is_valid"):
        # If enum doesn't have is_valid method, check values directly
        valid: bool = value in [e.value for e in enum_class]
    elif value:
        valid: bool = enum_class.is_valid(value)
    else:
        valid: bool = False

    if not valid:
        error_msg: str = _get_error_message(
            error_class,
            error_attr,
            ValidationError.FIELD_REQUIRED.format(key),
            key=key,
            value=value,
        )
        raise error_class(error_msg)

    return value


def _validate_numeric_value(  # noqa: PLR0913
    value: float,
    error_class: type[ErrorType],
    key: str,
    default_message: str,
    validator_func: Callable[[float], bool],
    *,
    error_attr: str = ERROR_ATTR_VALUE_POSITIVE,
) -> float:
    """Validate a numeric value according to provided criteria.

    This function centralizes the validation logic for numeric values, ensuring
    that the same validation rules are applied consistently throughout the application.

    Args:
        value: The numeric value to validate
        error_class: The error class to use for raising validation errors
        key: The attribute name being validated
        default_message: Default error message if specific one not found
        validator_func: Function that returns True if validation passes
        error_attr: The attribute name of the error message

    Returns:
        The validated value

    Raises:
        ValidationError: If the validation fails

    """
    if value is None or not validator_func(value):
        error_msg: str = _get_error_message(
            error_class,
            error_attr,
            default_message.format(key=key, value=value),
            key=key,
            value=value,
        )
        raise error_class(error_msg)

    return value


def validate_positive_value(
    value: float,
    error_class: type[ErrorType],
    key: str,
    error_attr: str = ERROR_ATTR_VALUE_POSITIVE,
) -> float:
    """Validate that a numeric value is positive (greater than zero).

    Args:
        value: The numeric value to validate
        error_class: The error class to use for raising validation errors
        key: The attribute name being validated (for error messages)
        error_attr: The attribute name of the error message in the error class

    Returns:
        The validated value

    Raises:
        ValidationError: If the value is not positive

    """
    return _validate_numeric_value(
        value,
        error_class,
        key,
        TransactionError.PRICE_POSITIVE.format(key, value),
        lambda x: x > 0,
        error_attr=error_attr,
    )


def validate_non_negative_value(
    value: float,
    error_class: type[ErrorType],
    key: str,
    error_attr: str = ERROR_ATTR_VALUE_NEGATIVE,
) -> float:
    """Validate that a numeric value is non-negative (greater than or equal to zero).

    Args:
        value: The numeric value to validate
        error_class: The error class to use for raising validation errors
        key: The attribute name being validated (for error messages)
        error_attr: The attribute name of the error message in the error class

    Returns:
        The validated value

    Raises:
        ValidationError: If the value is negative

    """
    return _validate_numeric_value(
        value,
        error_class,
        key,
        CommonErrorMessages.NEGATIVE_PRICE.format(key, value),
        lambda x: x >= 0,
        error_attr=error_attr,
    )


def validate_range(
    value: float,
    bounds: tuple[float, float],
    error_class: type[ErrorType],
    key: str,
    error_attr: str = "VALUE_RANGE",
) -> float:
    """Validate that a numeric value is within a specified range.

    Args:
        value: The numeric value to validate
        bounds: A tuple of (min_value, max_value) defining the allowed range
        error_class: The error class to use for raising validation errors
        key: The attribute name being validated (for error messages)
        error_attr: The attribute name of the error message in the error class

    Returns:
        The validated value

    Raises:
        ValidationError: If the value is outside the specified range

    """
    min_value: float
    max_value: float
    if bounds:
        min_value, max_value = bounds

    # Special case for allocation percent which has a specific error message
    if value is not None and (value < min_value or value > max_value):
        if error_class == TradingServiceError and error_attr == "ALLOCATION_PERCENT":
            error_msg = TradingServiceError.ALLOCATION_PERCENT.format(
                key=key,
                value=value,
            )
            raise error_class(error_msg)

        error_msg: str = _get_error_message(
            error_class,
            error_attr,
            TradingServiceError.ALLOCATION_PERCENT.format(key=key, value=value),
            key=key,
            value=value,
            min_value=min_value,
            max_value=max_value,
        )
        raise error_class(error_msg)

    return value


def _validate_not_future(  # noqa: PLR0913
    time_value: date | datetime,
    error_class: type[ErrorType],
    key: str,
    default_message: str,
    current_time_func: Callable[[], date | datetime],
    error_attr: str = "FUTURE_DATE",
) -> date | datetime:
    """Validate that a date or datetime is not in the future.

    Args:
        time_value: The date or datetime to validate
        error_class: The error class to use for raising validation errors
        key: The attribute name being validated
        default_message: Default error message format if specific one not found
        current_time_func: Function that returns current date/datetime
        error_attr: The attribute name of the error message

    Returns:
        The validated date/datetime value

    Raises:
        ValidationError: If the date/datetime is in the future

    """
    if not time_value:
        return time_value

    current_time = current_time_func()

    # Normalize timezone awareness for datetime comparison
    if isinstance(time_value, datetime) and isinstance(current_time, datetime):
        if time_value.tzinfo is not None and current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=time_value.tzinfo)
        elif time_value.tzinfo is None and current_time.tzinfo is not None:
            time_value = time_value.replace(tzinfo=current_time.tzinfo)

    if time_value > current_time:
        error_msg: str = _get_error_message(
            error_class,
            error_attr,
            default_message.format(key=key, value=time_value),
            key=key,
            value=time_value,
        )
        raise error_class(error_msg)

    return time_value


def validate_not_future_date(
    date_value: date,
    error_class: type[ErrorType],
    key: str,
    error_attr: str = ERROR_ATTR_FUTURE_DATE,
) -> date:
    """Validate that a date is not in the future.

    Args:
        date_value: The date to validate
        error_class: The error class to use for raising validation errors
        key: The attribute name being validated (for error messages)
        error_attr: The attribute name of the error message in the error class

    Returns:
        The validated date

    Raises:
        ValidationError: If the date is in the future

    """
    return _validate_not_future(
        date_value,
        error_class,
        key,
        CommonErrorMessages.FUTURE_DATE,
        get_current_date,
        error_attr,
    )


def validate_not_future_datetime(
    datetime_value: datetime,
    error_class: type[ErrorType],
    key: str,
    error_attr: str = ERROR_ATTR_FUTURE_TIMESTAMP,
) -> datetime:
    """Validate that a datetime is not in the future.

    Args:
        datetime_value: The datetime to validate
        error_class: The error class to use for raising validation errors
        key: The attribute name being validated (for error messages)
        error_attr: The attribute name of the error message in the error class

    Returns:
        The validated datetime

    Raises:
        ValidationError: If the datetime is in the future

    """
    return _validate_not_future(
        datetime_value,
        error_class,
        key,
        CommonErrorMessages.FUTURE_TIMESTAMP,
        get_current_datetime,
        error_attr=error_attr,
    )


def validate_max_length(
    value: str | None,
    max_length: int,
    error_class: type[ErrorType],
    key: str,
    error_attr: str = "MAX_LENGTH",
) -> str | None:
    """Validate that a string does not exceed a maximum length.

    Args:
        value: The string value to validate
        max_length: The maximum allowed length
        error_class: The error class to use for raising validation errors
        key: The attribute name being validated (for error messages)
        error_attr: The attribute name of the error message in the error class

    Returns:
        The validated string value

    Raises:
        ValidationError: If the string exceeds the maximum length

    """
    if not value:
        return value

    if len(value) > max_length:
        # Special handling for different model-specific attribute errors in StockError
        if error_class == StockError:
            stock_error_mapping: dict[str, str] = {
                "name": "NAME_LENGTH",
                "sector": "SECTOR_LENGTH",
                "description": "DESCRIPTION_LENGTH",
            }
            if key in stock_error_mapping:
                error_attr = stock_error_mapping[key]
                error_msg: str = _get_error_message(
                    StockError,
                    error_attr,
                    StockError.NAME_LENGTH.format(key=key, value=value),
                    key=key,
                    value=value,
                )
                raise StockError(error_msg)

        # Otherwise use standard error handling
        error_msg: str = _get_error_message(
            error_class,
            error_attr,
            StockError.NAME_LENGTH.format(key=key, value=value),
            key=key,
            value=value,
            max_length=max_length,
        )
        raise error_class(error_msg)

    return value


def validate_email(
    email: str,
    error_class: type[ErrorType],
    key: str = "email",
    *,
    required: bool = True,
) -> str | None:
    """Validate an email address.

    Args:
        email: The email address to validate
        error_class: The error class to use for raising validation errors
        key: The attribute name being validated (for error messages)
        required: Whether the email is required (cannot be empty)

    Returns:
        The validated email address

    Raises:
        ValidationError: If the email is invalid

    """
    # Check if email is required but empty
    if not email:
        if required:
            if error_class == UserError:
                error_msg: str = UserError.EMAIL_REQUIRED.format(key=key, value=email)
                raise UserError(error_msg)

            error_msg = _get_error_message(
                error_class,
                ERROR_ATTR_EMAIL_REQUIRED,
                CommonErrorMessages.EMAIL_REQUIRED.format(key=key, value=email),
                key=key,
                value=email,
            )
            raise error_class(error_msg)
        return email

    # Comprehensive email validation
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        if error_class == UserError:
            error_msg: str = UserError.EMAIL_FORMAT.format(key=key, value=email)
            raise UserError(error_msg)

        error_msg = _get_error_message(
            error_class,
            ERROR_ATTR_EMAIL_FORMAT,
            CommonErrorMessages.EMAIL_FORMAT.format(key=key, value=email),
            key=key,
            value=email,
        )
        raise error_class(error_msg)

    return email


def validate_required_field(
    value: any,
    error_class: type[ErrorType],
    field_name: str,
    error_attr: str = "FIELD_REQUIRED",
) -> any:
    """Validate that a required field is provided.

    Args:
        value: The value to validate
        error_class: The error class to use for raising validation errors
        field_name: The name of the required field
        error_attr: The attribute name of the error message in the error class

    Returns:
        The validated value

    Raises:
        ValidationError: If the value is None or empty string

    """
    if value is None or (isinstance(value, str) and not value.strip()):
        error_msg: str = _get_error_message(
            error_class,
            error_attr,
            ValidationError.FIELD_REQUIRED.format(field_name),
            field_name=field_name,
        )
        raise error_class(error_msg)

    return value
