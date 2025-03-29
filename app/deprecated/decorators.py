"""
API decorators for authentication and authorization.

DEPRECATED: This module is deprecated and will be removed in a future version.
Please use app.utils.auth for authentication and authorization utilities instead.
"""
from functools import wraps
from flask import g, abort
from flask_jwt_extended import get_jwt_identity, jwt_required
from app.utils.errors import AuthorizationError
from app.models import User
from app.services.database import get_db_session

# DEPRECATED: Use admin_required from app.utils.auth instead
def admin_required(fn):
    """
    Decorator to check if the current user is an admin.
    Must be used with the jwt_required decorator.
    
    DEPRECATED: Use admin_required from app.utils.auth instead.
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

# DEPRECATED: Use require_ownership from app.utils.auth instead
def require_ownership(model_class, id_param='id'):
    """
    Decorator to check if the current user owns the requested resource.
    Must be used with the jwt_required decorator.
    
    DEPRECATED: Use require_ownership from app.utils.auth instead.

    Args:
        model_class: The model class to check ownership against
        id_param: The URL parameter containing the resource ID
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Get user ID from token
            user_id = get_jwt_identity()
            
            # Get resource ID from URL parameters
            resource_id = kwargs.get(id_param)
            if not resource_id:
                abort(400, f"Missing required parameter: {id_param}")
            
            # Check ownership
            with get_db_session() as session:
                resource = session.query(model_class).filter_by(id=resource_id).first()
                if not resource:
                    abort(404, f"Resource not found")
                
                # Check if the resource has a user_id attribute
                if not hasattr(resource, 'user_id'):
                    abort(500, f"Model {model_class.__name__} does not support ownership checks")
                
                # Verify ownership
                if resource.user_id != user_id:
                    abort(403, "You do not have permission to access this resource")
            
            return fn(*args, **kwargs)
        
        return wrapper
    
    return decorator

# DEPRECATED: Use verify_resource_ownership from app.utils.auth instead
def verify_resource_ownership(session, resource, user_id):
    """
    Utility function to verify resource ownership.
    
    DEPRECATED: Use verify_resource_ownership from app.utils.auth instead.
    
    Args:
        session: Database session
        resource: The resource to check
        user_id: The ID of the user to check against
        
    Returns:
        bool: True if the user owns the resource, False otherwise
        
    Raises:
        AuthorizationError: If the user does not own the resource
    """
    if not hasattr(resource, 'user_id'):
        raise AuthorizationError(f"Resource does not support ownership checks")
    
    if resource.user_id != user_id:
        raise AuthorizationError("You do not have permission to access this resource")
    
    return True 