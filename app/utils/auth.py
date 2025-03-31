"""
Authentication and authorization utilities.

This module provides utilities for authentication and authorization checks
that can be used across the application.
"""

import logging
from functools import wraps
from typing import Callable, Optional, TypeVar, Union

from flask import abort
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from sqlalchemy.orm import Session

from app.models import TradingService, TradingTransaction, User
from app.services.session_manager import SessionManager
from app.utils.errors import AuthorizationError, ResourceNotFoundError

logger: logging.Logger = logging.getLogger(__name__)

# Define a type variable for return type of decorated functions
T = TypeVar("T")


def verify_resource_ownership(
    session: Session,
    resource_type: str,
    resource_id: Union[str, int],
    user_id: int,
    raise_exception: bool = True,
) -> bool:
    """
    Verify that a user owns a resource.

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
        AuthorizationError: If the user doesn't own the resource and raise_exception is True
    """
    resource: Optional[Union[TradingService, TradingTransaction, User]] = None
    ownership_verified: bool = False

    # Handle different resource types
    if resource_type == "service":
        resource: Optional[TradingService] = (
            session.query(TradingService).filter_by(id=resource_id).first()
        )
        if resource:
            ownership_verified = resource.user_id == user_id

    elif resource_type == "transaction":
        resource: Optional[TradingTransaction] = (
            session.query(TradingTransaction).filter_by(id=resource_id).first()
        )
        if resource:
            # Get the service associated with the transaction
            service: Optional[TradingService] = (
                session.query(TradingService).filter_by(id=resource.service_id).first()
            )
            if service:
                ownership_verified = bool(service.user_id == user_id)
            else:
                ownership_verified = False

    elif resource_type == "user":
        # Users can only access their own user data
        ownership_verified = str(resource_id) == str(user_id)
        resource = session.query(User).filter_by(id=resource_id).first()

    # Resource not found
    if not resource:
        if raise_exception:
            raise ResourceNotFoundError(resource_type, resource_id)
        return False

    # Check ownership
    if ownership_verified is not True and raise_exception:
        raise AuthorizationError(f"User does not have access to this {resource_type}")

    return bool(ownership_verified)


def require_ownership(resource_type: str, id_parameter: str = "id") -> Callable[..., T]:
    """
    Decorator to verify that a user owns a resource.

    Args:
        resource_type: Type of resource to check
        id_parameter: Name of the parameter that contains the resource ID

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Get resource_id from kwargs
            resource_id: Optional[Union[str, int]] = kwargs.get(id_parameter)
            if not resource_id:
                logger.error(f"ID parameter '{id_parameter}' not found in request")
                raise AuthorizationError("Resource ID not provided")

            # Get user_id from JWT token
            try:
                verify_jwt_in_request()
                user_id: Optional[int] = get_jwt_identity()
            except Exception as e:
                logger.error(f"JWT verification failed: {str(e)}")
                raise AuthorizationError("Authentication required")

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
    """
    Decorator to check if the current user is an admin.
    Must be used with the jwt_required decorator.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs) -> T:
        # Get user ID from token
        user_id: Optional[int] = get_jwt_identity()

        # Check if user is admin
        with SessionManager() as session:
            user: Optional[User] = session.query(User).filter_by(id=user_id).first()
            if not user or user.is_admin is not True:
                abort(403, "Admin privileges required")

        return fn(*args, **kwargs)

    return wrapper


def get_current_user(session: Optional[Session] = None) -> Optional[User]:
    """
    Get the current authenticated user.

    Args:
        session: Database session to use (optional)

    Returns:
        User object or None if no authenticated user
    """
    try:
        verify_jwt_in_request()
        user_id: Optional[int] = get_jwt_identity()

        # Use provided session or create a new one
        session_manager = None
        if session is None:
            session_manager = SessionManager()
            session = session_manager.session

        if session is None:
            logger.error("Failed to create database session")
            return None

        user: Optional[User] = session.query(User).filter_by(id=user_id).first()

        if session_manager is not None and session_manager.session is not None:
            session_manager.session.close()

        return user
    except Exception as e:
        logger.debug(f"Failed to get current user: {str(e)}")
        return None
