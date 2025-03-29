"""
Utility package for the Day Trader application.

This package contains utility modules that provide helper functions,
decorators, and other utilities that are used across the application.
"""

from app.utils.errors import (
    APIError,
    ValidationError,
    AuthorizationError,
    ResourceNotFoundError,
    BusinessLogicError,
    api_error_handler,
    register_error_handlers,
    handle_validation_error
)

from app.utils.auth import (
    verify_resource_ownership,
    require_ownership,
    get_current_user,
    admin_required
)

from app.utils.current_datetime import (
    get_current_datetime,
    get_current_date,
    get_current_time
)

__all__ = [
    # Error utilities
    'APIError',
    'ValidationError',
    'AuthorizationError',
    'ResourceNotFoundError',
    'BusinessLogicError',
    'api_error_handler',
    'register_error_handlers',
    'handle_validation_error',
    
    # Auth utilities
    'verify_resource_ownership',
    'require_ownership',
    'get_current_user',
    'admin_required',
    
    # Datetime utilities
    'get_current_datetime',
    'get_current_date',
    'get_current_time'
] 