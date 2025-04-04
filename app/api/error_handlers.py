"""API error handlers for the Day Trader application.

This module contains error handlers for the API endpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Blueprint

from flask_restx.errors import ValidationError

from app.utils.constants import ApiConstants
from app.utils.errors import handle_validation_error


def flask_validation_error(error: ValidationError) -> tuple[dict[str, any], int]:
    """Handle Schema validation errors."""
    error_response: dict[str, any] = handle_validation_error(error)
    return error_response, ApiConstants.HTTP_BAD_REQUEST


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


def register_error_handlers(api_bp: Blueprint) -> None:
    """Register error handlers for the API blueprint.

    Args:
        api_bp: The API Blueprint to register error handlers for

    """
    api_bp.errorhandler(ValidationError)(flask_validation_error)
    api_bp.errorhandler(404)(handle_not_found)
    api_bp.errorhandler(401)(handle_unauthorized)
