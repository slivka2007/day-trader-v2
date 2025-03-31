"""
Custom exceptions for the Day Trader application.

This module defines application-specific exceptions that provide
clear error messages and appropriate hierarchy for error handling.
"""


class DayTraderError(Exception):
    """Base exception for all Day Trader application errors."""

    pass


class ConfigurationError(DayTraderError):
    """Exception raised for errors in the application configuration."""

    pass


class DatabaseError(DayTraderError):
    """Exception raised for database-related errors."""

    pass


class ServiceError(DayTraderError):
    """Exception raised for errors in service operation."""

    pass


class InvalidStateError(ServiceError):
    """Exception raised when an operation is attempted in an invalid state."""

    pass


class APIError(DayTraderError):
    """Exception raised for errors in API operations."""

    pass


class InvalidSymbolError(APIError):
    """Exception raised when an invalid stock symbol is used."""

    pass


class RateLimitError(APIError):
    """Exception raised when API rate limit is exceeded."""

    pass


class StockPurchaseError(APIError):
    """Exception raised when stock purchase fails."""

    pass


class StockSaleError(APIError):
    """Exception raised when stock sale fails."""

    pass


class DataFetchError(APIError):
    """Exception raised when fetching data from external sources fails."""

    pass
