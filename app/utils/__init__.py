"""
Utility package for the Day Trader application.

This package contains utility modules that provide helper functions,
decorators, and other utilities that are used across the application.
"""

from typing import List

from app.utils.auth import (
    admin_required,
    get_current_user,
    require_ownership,
    verify_resource_ownership,
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

__all__: List[str] = [
    # Error utilities
    "APIError",
    "ValidationError",
    "AuthorizationError",
    "ResourceNotFoundError",
    "BusinessLogicError",
    "api_error_handler",
    "register_error_handlers",
    "handle_validation_error",
    # Auth utilities
    "verify_resource_ownership",
    "require_ownership",
    "get_current_user",
    "admin_required",
    # Datetime utilities
    "get_current_datetime",
    "get_current_date",
    "get_current_time",
]
