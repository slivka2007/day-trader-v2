"""Authentication and authorization utilities.

This module provides utilities for authentication and authorization checks
that can be used across the application.
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import TYPE_CHECKING, Callable, TypeVar

from flask import abort
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from flask_jwt_extended.exceptions import JWTExtendedException
from sqlalchemy import select

from app.models import TradingService, TradingTransaction, User
from app.services.session_manager import SessionManager
from app.utils.errors import AuthorizationError, ResourceNotFoundError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger: logging.Logger = logging.getLogger(__name__)

# Define a type variable for return type of decorated functions
T = TypeVar("T")


def verify_resource_ownership(
    session: Session,
    resource_type: str,
    resource_id: str | int,
    user_id: int,
    *,
    raise_exception: bool = True,
) -> bool:
    """Verify that a user owns a resource.

    Args:
        session: Database session
        resource_type: Type of resource to check
        resource_id: ID of the resource
        user_id: ID of the user to check
        raise_exception: Whether to raise an exception if ownership verification fails

    Returns:
        Whether the user owns the resource

    Raises:
        ResourceNotFoundError: If the resource doesn't exist
        AuthorizationError: If the user doesn't own the resource and raise_exception is
        True

    """
    resource: TradingService | TradingTransaction | User | None = None
    ownership_verified: bool = False

    # Handle different resource types
    if resource_type == "service":
        resource: TradingService | None = session.execute(
            select(TradingService).where(TradingService.id == resource_id),
        ).scalar_one_or_none()
        if resource:
            ownership_verified = resource.user_id == user_id

    elif resource_type == "transaction":
        resource: TradingTransaction | None = session.execute(
            select(TradingTransaction).where(TradingTransaction.id == resource_id),
        ).scalar_one_or_none()
        if resource:
            # Get the service associated with the transaction
            service: TradingService | None = session.execute(
                select(TradingService).where(TradingService.id == resource.service_id),
            ).scalar_one_or_none()
            ownership_verified = bool(service.user_id == user_id) if service else False

    elif resource_type == "user":
        # Users can only access their own user data
        ownership_verified = str(resource_id) == str(user_id)
        resource = session.execute(
            select(User).where(User.id == resource_id),
        ).scalar_one_or_none()

    # Resource not found
    if not resource:
        if raise_exception:
            raise ResourceNotFoundError(resource_type, resource_id)
        return False

    # Check ownership
    if ownership_verified is not True and raise_exception:
        raise AuthorizationError
    return bool(ownership_verified)


def require_ownership(resource_type: str, id_parameter: str = "id") -> Callable[..., T]:
    """Verify user ownership of a resource.

    Args:
        resource_type: Type of resource to check
        id_parameter: Name of the parameter that contains the resource ID

    Returns:
        Decorated function

    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: any, **kwargs: any) -> T:
            # Get resource_id from kwargs
            resource_id: str | int | None = kwargs.get(id_parameter)
            if not resource_id:
                logger.error("ID parameter '%s' not found in request", id_parameter)
                raise AuthorizationError

            # Get user_id from JWT token
            try:
                verify_jwt_in_request()
                user_id: int | None = get_jwt_identity()
            except JWTExtendedException as e:
                logger.exception("JWT verification failed")
                raise AuthorizationError from e

            # Verify ownership
            with SessionManager() as session:
                verify_resource_ownership(
                    session=session,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    user_id=user_id,
                    raise_exception=True,
                )

            # Call the actual function if ownership is verified
            return func(*args, **kwargs)

        return wrapper

    return decorator


def admin_required(fn: Callable[..., T]) -> Callable[..., T]:
    """Check if the current user is an admin.

    Must be used with the jwt_required decorator.
    """

    @wraps(fn)
    def wrapper(*args: any, **kwargs: any) -> T:
        # Get user ID from token
        user_id: int | None = get_jwt_identity()

        # Check if user is admin
        with SessionManager() as session:
            user: User | None = session.execute(
                select(User).where(User.id == user_id),
            ).scalar_one_or_none()
            if not user or user.is_admin is not True:
                abort(403, "Admin privileges required")

        return fn(*args, **kwargs)

    return wrapper


def get_current_user(session: Session | None = None) -> User | None:
    """Get the current authenticated user.

    Args:
        session: Database session to use (optional)

    Returns:
        User object or None if no authenticated user

    """
    try:
        verify_jwt_in_request()
        user_id: int | None = get_jwt_identity()

        if session is None:
            with SessionManager() as new_session:
                return new_session.execute(
                    select(User).where(User.id == user_id),
                ).scalar_one_or_none()
        else:
            return session.execute(
                select(User).where(User.id == user_id),
            ).scalar_one_or_none()

    except JWTExtendedException:
        logger.exception("Failed to get current user")
        return None
