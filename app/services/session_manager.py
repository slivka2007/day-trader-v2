"""
Session manager module for handling database sessions.

This module provides session management utilities including a context manager 
for automatic session handling and a decorator for wrapping functions that 
require database access.
"""
import logging
import functools
from typing import Callable, TypeVar

from app.services.database import get_session

logger = logging.getLogger(__name__)

T = TypeVar('T')


class SessionManager:
    """Context manager for handling database sessions.
    
    This class provides automatic session creation, commit on success, 
    and rollback on exceptions. Use with the 'with' statement to ensure 
    proper cleanup of session resources.
    
    Example:
        with SessionManager() as session:
            user = session.query(User).filter_by(username='johndoe').first()
            user.last_login = datetime.now()
    """
    
    def __init__(self):
        self.session = None
        
    def __enter__(self):
        self.session = get_session()
        return self.session
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            logger.error(f"Session rolled back due to exception: {exc_val}")
            self.session.rollback()
        else:
            try:
                self.session.commit()
            except Exception as e:
                logger.error(f"Failed to commit session: {e}")
                self.session.rollback()
                raise
        self.session.close()


def with_session(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator for automatically managing database sessions.
    
    This decorator wraps a function with session handling logic, providing
    the function with a session object as its first argument after self.
    
    Args:
        func: The function to wrap with session management
        
    Returns:
        A wrapped function that handles session management automatically
        
    Example:
        @with_session
        def get_user(self, session, user_id):
            return session.query(User).get(user_id)
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        with SessionManager() as session:
            return func(self, session, *args, **kwargs)
    return wrapper 