"""Application-wide constants.

This module contains constants used throughout the application.
These constants are grouped by their functional areas for easier management.
"""

from __future__ import annotations

import logging

# Set up logging
logger: logging.Logger = logging.getLogger(__name__)


# Common validation constants shared across modules
class ValidationConstants:
    """Validation constants used across different modules."""

    # Common minimum/maximum values
    MIN_NAME_LENGTH: int = 1
    MAX_NAME_LENGTH: int = 100

    # Common percentage bounds
    MIN_PERCENT: float = 0.0
    MAX_PERCENT: float = 100.0

    # Default values
    DEFAULT_THRESHOLD: float = 0.0


# User related constants
class UserConstants:
    """User-related constants."""

    MIN_USERNAME_LENGTH: int = 3
    MAX_USERNAME_LENGTH: int = 50
    MIN_PASSWORD_LENGTH: int = 8


# Stock related constants
class StockConstants:
    """Stock-related constants."""

    MIN_SYMBOL_LENGTH: int = 1
    MAX_SYMBOL_LENGTH: int = 10
    MAX_NAME_LENGTH: int = 200
    MAX_SECTOR_LENGTH: int = 100
    MAX_DESCRIPTION_LENGTH: int = 1000


# Trading service constants
class TradingServiceConstants:
    """Trading service related constants."""

    # Resource types
    RESOURCE_TRADING_SERVICE: str = "TradingService"
    RESOURCE_STOCK: str = "Stock"

    # Constants
    MIN_DAYS_FOR_SMA: int = 20  # Minimum days required for SMA calculation
    MIN_NAME_LENGTH: int = ValidationConstants.MIN_NAME_LENGTH
    MAX_NAME_LENGTH: int = ValidationConstants.MAX_NAME_LENGTH
    DEFAULT_ALLOCATION_PERCENT: float = ValidationConstants.MAX_PERCENT
    DEFAULT_BUY_THRESHOLD: float = ValidationConstants.DEFAULT_THRESHOLD
    DEFAULT_SELL_THRESHOLD: float = ValidationConstants.DEFAULT_THRESHOLD
    DEFAULT_STOP_LOSS_PERCENT: float = ValidationConstants.DEFAULT_THRESHOLD
    DEFAULT_TAKE_PROFIT_PERCENT: float = ValidationConstants.DEFAULT_THRESHOLD
    MAX_ALLOCATION_PERCENT: float = ValidationConstants.MAX_PERCENT
    MIN_ALLOCATION_PERCENT: float = ValidationConstants.MIN_PERCENT
    MIN_MINIMUM_BALANCE: float = ValidationConstants.MIN_PERCENT
    MIN_BUY_THRESHOLD: float = ValidationConstants.DEFAULT_THRESHOLD
    MIN_SELL_THRESHOLD: float = ValidationConstants.DEFAULT_THRESHOLD
    MIN_STOP_LOSS_PERCENT: float = ValidationConstants.DEFAULT_THRESHOLD
    MIN_TAKE_PROFIT_PERCENT: float = ValidationConstants.DEFAULT_THRESHOLD


# Price analysis constants
class PriceAnalysisConstants:
    """Price analysis related constants."""

    # Constants for technical analysis
    MIN_DATA_POINTS: int = 5
    SHORT_MA_PERIOD: int = 5
    MEDIUM_MA_PERIOD: int = 10
    LONG_MA_PERIOD: int = 20
    EXTENDED_MA_PERIOD: int = 50
    MAX_MA_PERIOD: int = 200

    # RSI constants
    RSI_OVERSOLD: int = 30
    RSI_OVERBOUGHT: int = 70
    RSI_MIN_PERIODS: int = 15

    # Constants for default periods
    DEFAULT_MA_PERIOD: int = 20
    DEFAULT_BB_PERIOD: int = 20


# Time constants
class TimeConstants:
    """Time related constants."""

    # Trading day constants
    TRADING_HOURS_START: str = "09:30"
    TRADING_HOURS_END: str = "16:00"
    MARKET_TIMEZONE: str = "America/New_York"

    # Time periods in seconds
    SECOND: int = 1
    MINUTE: int = 60
    HOUR: int = 3600
    DAY: int = 86400
    WEEK: int = 604800


# API related constants
class ApiConstants:
    """API related constants."""

    # API response status values
    STATUS_SUCCESS: str = "success"
    STATUS_ERROR: str = "error"

    # Common HTTP status codes
    HTTP_OK: int = 200
    HTTP_CREATED: int = 201
    HTTP_BAD_REQUEST: int = 400
    HTTP_UNAUTHORIZED: int = 401
    HTTP_FORBIDDEN: int = 403
    HTTP_NOT_FOUND: int = 404
    HTTP_CONFLICT: int = 409
    HTTP_INTERNAL_SERVER_ERROR: int = 500


# Pagination constants
class PaginationConstants:
    """Pagination related constants."""

    DEFAULT_PAGE: int = 1
    DEFAULT_PER_PAGE: int = 20
    MAX_PER_PAGE: int = 100
