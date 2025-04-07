"""Authentication and authorization utilities.

This module provides utilities for authentication and authorization checks
that can be used across the application.
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import TYPE_CHECKING, Callable, TypeVar

from flask import g
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from flask_jwt_extended.exceptions import JWTExtendedException
from sqlalchemy import Select, select

from app.models import TradingService, TradingTransaction, User
from app.services.session_manager import SessionManager
from app.utils.errors import AuthorizationError, ResourceNotFoundError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger: logging.Logger = logging.getLogger(__name__)

# Define a type variable for return type of decorated functions
T = TypeVar("T")


def load_user_from_request() -> None:
    """Load current user from JWT and set in Flask g object.

    This function is meant to be registered as a before_request handler.
    """
    try:
        # Skip if no Authorization header is present
        if not verify_jwt_in_request(optional=True):
            g.user = None
            return

        user_id = get_jwt_identity()
        if user_id is not None:
            # Convert user_id to integer if it's a string
            if isinstance(user_id, str):
                user_id = int(user_id)

            with SessionManager() as session:
                # Retrieve user and make a detached copy with all attributes loaded
                stmt: Select = select(User).where(User.id == user_id)
                user: User | None = session.execute(stmt).scalar_one_or_none()

                if user:
                    # Make a complete copy of all attribute values
                    # This ensures the user object remains usable after the session is
                    # closed
                    user_dict = {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "password_hash": user.password_hash,
                        "is_active": user.is_active,
                        "is_admin": user.is_admin,
                        "created_at": user.created_at,
                        "updated_at": user.updated_at,
                        "last_login": user.last_login,
                    }

                    # Expire the instance to detach it with all attributes loaded
                    session.expunge(user)

                    # Manually set all attributes on the detached instance
                    for key, value in user_dict.items():
                        setattr(user, key, value)

                g.user = user
        else:
            g.user = None
    except JWTExtendedException:
        logger.exception("Failed to get user from token")
        g.user = None


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
                user_id: int | str | None = get_jwt_identity()

                # Convert user_id to integer if it's a string
                if isinstance(user_id, str):
                    user_id = int(user_id)

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
        user_id: int | str | None = get_jwt_identity()

        # Convert user_id to integer if it's a string
        if isinstance(user_id, str):
            user_id = int(user_id)

        # Check if user is admin
        with SessionManager() as session:
            user: User | None = session.execute(
                select(User).where(User.id == user_id),
            ).scalar_one_or_none()
            if not user or user.is_admin is not True:
                raise AuthorizationError(AuthorizationError.NOT_AUTHORIZED)

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
        user_id: int | str | None = get_jwt_identity()

        # Convert user_id to integer if it's a string
        if isinstance(user_id, str):
            user_id = int(user_id)

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
