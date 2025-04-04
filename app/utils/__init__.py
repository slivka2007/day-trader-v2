"""Utility package for the Day Trader application.

This package contains utility modules that provide helper functions,
decorators, and other utilities that are used across the application.
"""

from app.utils.auth import (
    admin_required,
    get_current_user,
    require_ownership,
    verify_resource_ownership,
)
from app.utils.constants import (
    ApiConstants,
    PaginationConstants,
    PriceAnalysisConstants,
    StockConstants,
    TimeConstants,
    TradingServiceConstants,
    UserConstants,
)
from app.utils.current_datetime import (
    get_current_date,
    get_current_datetime,
    get_current_time,
)
from app.utils.errors import (
    APIError,
    AuthorizationError,
    BusinessLogicError,
    ResourceNotFoundError,
    ValidationError,
    api_error_handler,
    handle_validation_error,
    register_error_handlers,
)
from app.utils.query_utils import (
    apply_filters,
    apply_pagination,
)

__all__: list[str] = [
    "APIError",
    # Constants
    "ApiConstants",
    # Errors
    "AuthorizationError",
    "BusinessLogicError",
    "PaginationConstants",
    "PriceAnalysisConstants",
    "ResourceNotFoundError",
    "StockConstants",
    "TimeConstants",
    "TradingServiceConstants",
    "UserConstants",
    "ValidationError",
    # Query utils
    "apply_filters",
    "apply_pagination",
    # Decorators
    "admin_required",
    "api_error_handler",
    "get_current_date",
    "get_current_datetime",
    "get_current_time",
    "get_current_user",
    "handle_validation_error",
    "register_error_handlers",
    "require_ownership",
    "verify_resource_ownership",
]
