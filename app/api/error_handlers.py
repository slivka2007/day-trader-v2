"""API error handlers for the Day Trader application.

This module contains error handlers for the API endpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Blueprint

from flask_restx import Api
from flask_restx.errors import ValidationError

from app.utils.constants import ApiConstants
from app.utils.errors import AuthorizationError, handle_validation_error


def flask_validation_error(error: ValidationError) -> tuple[dict[str, any], int]:
    """Handle Schema validation errors."""
    error_response: dict[str, any] = handle_validation_error(error)
    return error_response, ApiConstants.HTTP_BAD_REQUEST


def handle_authorization_error(error: AuthorizationError) -> tuple[dict[str, any], int]:
    """Handle authorization errors."""
    return {
        "error": True,
        "message": str(error),
        "status_code": ApiConstants.HTTP_UNAUTHORIZED,
    }, ApiConstants.HTTP_UNAUTHORIZED


def handle_not_found(error: any) -> tuple[dict[str, any], int]:
    """Handle 404 errors."""
    return {
        "error": True,
        "message": error.description,
        "status_code": ApiConstants.HTTP_NOT_FOUND,
    }, ApiConstants.HTTP_NOT_FOUND


def handle_unauthorized(error: any) -> tuple[dict[str, any], int]:
    """Handle 401 errors."""
    return {
        "error": True,
        "message": error.description,
        "status_code": ApiConstants.HTTP_UNAUTHORIZED,
    }, ApiConstants.HTTP_UNAUTHORIZED


def register_error_handlers(api: Api | Blueprint) -> None:
    """Register error handlers for the API or Blueprint.

    Args:
        api: The API or Blueprint to register error handlers for

    """
    if isinstance(api, Api):
        # Register error handlers for Flask-RESTx API
        api.errorhandler(ValidationError)(flask_validation_error)
        api.errorhandler(AuthorizationError)(handle_authorization_error)
        api.errorhandler(Exception)(handle_error)
    else:
        # Register error handlers for Flask Blueprint
        api.errorhandler(ValidationError)(flask_validation_error)
        api.errorhandler(AuthorizationError)(handle_authorization_error)
        api.errorhandler(404)(handle_not_found)
        api.errorhandler(401)(handle_unauthorized)


def handle_error(error: Exception) -> tuple[dict[str, any], int]:
    """Handle any unhandled exceptions."""
    if isinstance(error, AuthorizationError):
        return handle_authorization_error(error)
    if isinstance(error, ValidationError):
        return flask_validation_error(error)
    if hasattr(error, "code") and error.code == ApiConstants.HTTP_NOT_FOUND:
        return handle_not_found(error)
    if hasattr(error, "code") and error.code == ApiConstants.HTTP_UNAUTHORIZED:
        return handle_unauthorized(error)
    return {
        "error": True,
        "message": str(error),
        "status_code": ApiConstants.HTTP_INTERNAL_SERVER_ERROR,
    }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR
