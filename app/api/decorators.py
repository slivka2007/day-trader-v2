"""
API decorators for authentication and authorization.
"""
from functools import wraps
from flask import g
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from app.utils.errors import AuthorizationError
from app.models import User
from app.services.database import get_db_session

def admin_required(fn):
    """
    Decorator to check if the current user is an admin.
    Must be used with the jwt_required decorator.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Get the current user from g
        if not hasattr(g, 'user') or not g.user:
            # Get the user from database if not already set
            user_id = get_jwt_identity()
            with get_db_session() as session:
                g.user = session.query(User).get(user_id)
        
        # Check if user is admin
        if not g.user or not g.user.is_admin:
            raise AuthorizationError("Admin privileges required")
        
        return fn(*args, **kwargs)
    return wrapper 