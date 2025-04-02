"""Session manager module for handling database sessions.

This module provides session management utilities including a context manager
for automatic session handling and a decorator for wrapping functions that
require database access.
"""

from __future__ import annotations

import functools
import logging
from typing import TYPE_CHECKING, Callable, TypeVar

if TYPE_CHECKING:
    from types import TracebackType

    from sqlalchemy.orm import Session

from app.services.database import get_session

logger: logging.Logger = logging.getLogger(__name__)

T = TypeVar("T")


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

    def __init__(self) -> None:
        """Initialize a new SessionManager with no active session.

        The session will be created when entering the context manager.
        """
        self.session: Session | None = None

    def __enter__(self) -> Session:
        """Enter the context manager and create a new session.

        Returns:
            The newly created session.

        """
        self.session = get_session()
        return self.session

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context manager and handle session cleanup.

        Commits the session if no exceptions occurred, otherwise rolls back.
        Always closes the session at the end.

        Args:
            exc_type: Exception type if an exception was raised, None otherwise
            exc_val: Exception value if an exception was raised, None otherwise
            exc_tb: Exception traceback if an exception was raised, None otherwise

        """
        if exc_type is not None:
            logger.exception("Session rolled back due to exception: %s", exc_val)
            if self.session:
                self.session.rollback()
        else:
            try:
                if self.session:
                    self.session.commit()
            except Exception:
                logger.exception("Failed to commit session")
                if self.session:
                    self.session.rollback()
                raise
        if self.session:
            self.session.close()


def with_session(func: Callable[..., T]) -> Callable[..., T]:
    """Decorate a function to automatically manage database sessions.

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
    def wrapper(self: any, *args: any, **kwargs: any) -> T:
        with SessionManager() as session:
            return func(self, session, *args, **kwargs)

    return wrapper
