"""
Authentication and authorization utilities.

This module provides utilities for authentication and authorization checks
that can be used across the application.
"""
import logging
from typing import Dict, Any, Optional, Callable, TypeVar, Union
from functools import wraps
from sqlalchemy.orm import Session
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request, jwt_required
from flask import abort

from app.models import User, TradingService, TradingTransaction
from app.services.database import get_db_session
from app.utils.errors import AuthorizationError, ResourceNotFoundError

logger = logging.getLogger(__name__)

# Define a type variable for return type of decorated functions
T = TypeVar('T')

def verify_resource_ownership(session: Session, resource_type: str, 
                             resource_id: Union[str, int], user_id: int,
                             raise_exception: bool = True) -> bool:
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
    resource = None
    ownership_verified = False
    
    # Handle different resource types
    if resource_type == 'service':
        resource = session.query(TradingService).filter_by(id=resource_id).first()
        if resource:
            ownership_verified = resource.user_id == user_id
            
    elif resource_type == 'transaction':
        resource = session.query(TradingTransaction).filter_by(id=resource_id).first()
        if resource:
            # Get the service associated with the transaction
            service = session.query(TradingService).filter_by(id=resource.service_id).first()
            ownership_verified = service and service.user_id == user_id
            
    elif resource_type == 'user':
        # Users can only access their own user data
        ownership_verified = str(resource_id) == str(user_id)
        resource = session.query(User).filter_by(id=resource_id).first()
            
    # Resource not found
    if not resource:
        if raise_exception:
            raise ResourceNotFoundError(resource_type, resource_id)
        return False
    
    # Check ownership
    if not ownership_verified and raise_exception:
        raise AuthorizationError(f"User does not have access to this {resource_type}")
        
    return ownership_verified

def require_ownership(resource_type: str, id_parameter: str = 'id'):
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
        def wrapper(*args, **kwargs):
            # Get resource_id from kwargs
            resource_id = kwargs.get(id_parameter)
            if not resource_id:
                logger.error(f"ID parameter '{id_parameter}' not found in request")
                raise AuthorizationError(f"Resource ID not provided")
            
            # Get user_id from JWT token
            try:
                verify_jwt_in_request()
                user_id = get_jwt_identity()
            except Exception as e:
                logger.error(f"JWT verification failed: {str(e)}")
                raise AuthorizationError("Authentication required")
            
            # Verify ownership
            with get_db_session() as session:
                verify_resource_ownership(
                    session=session,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    user_id=user_id,
                    raise_exception=True
                )
            
            # Call the actual function if ownership is verified
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator

def admin_required(fn):
    """
    Decorator to check if the current user is an admin.
    Must be used with the jwt_required decorator.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Get user ID from token
        user_id = get_jwt_identity()
        
        # Check if user is admin
        with get_db_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user or not user.is_admin:
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
        user_id = get_jwt_identity()
        
        # Use provided session or create a new one
        close_session = False
        if not session:
            session = get_db_session()
            close_session = True
            
        user = session.query(User).filter_by(id=user_id).first()
        
        if close_session:
            session.close()
            
        return user
    except Exception as e:
        logger.debug(f"Failed to get current user: {str(e)}")
        return None 