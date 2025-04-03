"""User service for managing User model operations.

This service encapsulates all database interactions for the User model,
providing a clean API for user management operations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import or_, select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.api.schemas.user import user_schema
from app.models.user import User
from app.services.events import EventService
from app.utils.current_datetime import get_current_datetime
from app.utils.errors import AuthorizationError, ResourceNotFoundError, ValidationError

# Set up logging
logger: logging.Logger = logging.getLogger(__name__)


class UserService:
    """Service for User model operations."""

    @staticmethod
    def _raise_error(error_class: type[Exception], message: str, *args: any) -> None:
        """Raise an error with a formatted message.

        Args:
            error_class: The error class to raise
            message: The error message or message template
            *args: Format arguments for the message

        """
        error_msg: str = message.format(*args) if args else message
        raise error_class(error_msg)

    @staticmethod
    def find_by_username(session: Session, username: str) -> User | None:
        """Find a user by username.

        Args:
            session: Database session
            username: Username to search for

        Returns:
            User instance if found, None otherwise

        """
        return session.execute(
            select(User).where(User.username == username),
        ).scalar_one_or_none()

    @staticmethod
    def find_by_email(session: Session, email: str) -> User | None:
        """Find a user by email.

        Args:
            session: Database session
            email: Email to search for

        Returns:
            User instance if found, None otherwise

        """
        stmt: select[tuple[User]] = select(User).where(User.email == email)
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def find_by_username_or_email(session: Session, identifier: str) -> User | None:
        """Find a user by username or email.

        Args:
            session: Database session
            identifier: Username or email to search for

        Returns:
            User instance if found, None otherwise

        """
        stmt: select[tuple[User]] = select(User).where(
            or_(User.username == identifier, User.email == identifier),
        )
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_by_id(session: Session, user_id: int) -> User | None:
        """Get a user by ID.

        Args:
            session: Database session
            user_id: User ID to retrieve

        Returns:
            User instance if found, None otherwise

        """
        stmt: select[tuple[User]] = select(User).where(User.id == user_id)
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_or_404(session: Session, user_id: int) -> User:
        """Get a user by ID or raise ResourceNotFoundError.

        Args:
            session: Database session
            user_id: User ID to retrieve

        Returns:
            User instance

        Raises:
            ResourceNotFoundError: If user not found

        """
        user: User | None = UserService.get_by_id(session, user_id)
        if not user:
            UserService._raise_error(ResourceNotFoundError, "User", user_id)
        return user

    @staticmethod
    def get_all(session: Session) -> list[User]:
        """Get all users.

        Args:
            session: Database session

        Returns:
            List of User instances

        """
        stmt: select[tuple[User]] = select(User)
        return list(session.execute(stmt).scalars().all())

    @staticmethod
    def create_user(session: Session, data: dict[str, any]) -> User:
        """Create a new user.

        Args:
            session: Database session
            data: User data dictionary

        Returns:
            Created user instance

        Raises:
            ValidationError: If required fields are missing or invalid

        """
        from app.services.events import EventService

        try:
            data_dict: dict[str, any] = data if isinstance(data, dict) else {}

            # Validate required fields
            required_fields: list[str] = ["username", "email", "password"]
            for field in required_fields:
                if field not in data_dict or not data_dict.get(field):
                    UserService._raise_error(
                        ValidationError,
                        ValidationError.FIELD_REQUIRED,
                        field,
                    )

            # Check for duplicate username or email
            stmt: select[tuple[User]] = select(User).where(
                or_(
                    User.username == data_dict.get("username"),
                    User.email == data_dict.get("email"),
                ),
            )
            existing_user: User | None = session.execute(stmt).scalar_one_or_none()

            if existing_user:
                if existing_user.username == data_dict.get("username"):
                    UserService._raise_error(
                        ValidationError,
                        ValidationError.USERNAME_EXISTS,
                        data_dict.get("username"),
                    )
                UserService._raise_error(
                    ValidationError,
                    ValidationError.EMAIL_EXISTS,
                    data_dict.get("email"),
                )

            # Create password_hash from password
            password: str | None = data_dict.pop("password", None)

            # Create user from data
            user: User = User(**{k: v for k, v in data_dict.items() if k != "password"})

            # Set password (triggers validation and hashing)
            if password:
                user.password = password

            session.add(user)
            session.commit()

            # Prepare response data
            user_data: dict[str, any] = user_schema.dump(user)
            user_data_dict: dict[str, any] = (
                user_data if isinstance(user_data, dict) else user_data[0]
            )

            # Emit WebSocket event
            EventService.emit_user_update(
                action="created",
                user_data=user_data_dict,
                user_id=user.id,
            )

        except Exception as e:
            logger.exception("Error creating user")
            session.rollback()
            if isinstance(e, ValidationError):
                raise
            UserService._raise_error(
                ValidationError,
                ValidationError.CREATE_USER_ERROR,
                str(e),
            )
        return user

    @staticmethod
    def _validate_unique_fields(
        session: Session,
        user: User,
        data_dict: dict[str, any],
    ) -> None:
        """Validate username and email uniqueness.

        Args:
            session: Database session
            user: Current user instance
            data_dict: Dictionary of update data

        """
        if "username" in data_dict and data_dict.get("username") != user.username:
            existing: User | None = UserService.find_by_username(
                session,
                data_dict.get("username", ""),
            )
            if existing:
                UserService._raise_error(
                    ValidationError,
                    ValidationError.USERNAME_EXISTS,
                    data_dict.get("username"),
                )

        if "email" in data_dict and data_dict.get("email") != user.email:
            existing: User | None = UserService.find_by_email(
                session,
                data_dict.get("email", ""),
            )
            if existing:
                UserService._raise_error(
                    ValidationError,
                    ValidationError.EMAIL_EXISTS,
                    data_dict.get("email"),
                )

    @staticmethod
    def _update_user_fields(user: User, data_dict: dict[str, any]) -> bool:
        """Update allowed user fields.

        Args:
            user: User instance to update
            data_dict: Dictionary of update data

        Returns:
            True if any fields were updated

        """
        allowed_fields: set[str] = {"username", "email", "is_active", "is_admin"}
        updated = False

        for field in allowed_fields:
            if field in data_dict:
                setattr(user, field, data_dict.get(field))
                updated = True

        if "password" in data_dict and data_dict.get("password"):
            user.password = data_dict.get("password", "")
            updated = True

        return updated

    @staticmethod
    def update_user(session: Session, user: User, data: dict[str, any]) -> User:
        """Update user attributes.

        Args:
            session: Database session
            user: User instance to update
            data: Dictionary of attributes to update

        Returns:
            Updated user instance

        Raises:
            ValidationError: If invalid data is provided

        """
        from app.services.events import EventService

        try:
            data_dict: dict[str, any] = data if isinstance(data, dict) else {}

            UserService._validate_unique_fields(session, user, data_dict)

            if UserService._update_user_fields(user, data_dict):
                user.updated_at = get_current_datetime()
                session.commit()

                user_data: dict[str, any] = user_schema.dump(user)
                user_data_dict: dict[str, any] = (
                    user_data if isinstance(user_data, dict) else user_data[0]
                )

                EventService.emit_user_update(
                    action="updated",
                    user_data=user_data_dict,
                    user_id=user.id,
                )

        except Exception as e:
            logger.exception("Error updating user")
            session.rollback()
            if isinstance(e, ValidationError):
                raise
            UserService._raise_error(
                ValidationError,
                ValidationError.UPDATE_USER_ERROR,
                str(e),
            )
        return user

    @staticmethod
    def toggle_active(session: Session, user: User) -> User:
        """Toggle user active status.

        Args:
            session: Database session
            user: User instance

        Returns:
            Updated user instance

        """
        from app.services.events import EventService

        try:
            user.is_active = not user.is_active
            user.updated_at = get_current_datetime()
            session.commit()

            # Prepare response data
            user_data: dict[str, any] = user_schema.dump(user)
            user_data_dict: dict[str, any] = (
                user_data if isinstance(user_data, dict) else user_data[0]
            )

            # Emit WebSocket event
            EventService.emit_user_update(
                action="status_changed",
                user_data=user_data_dict,
                user_id=user.id,
            )

        except Exception as e:
            logger.exception("Error toggling user status")
            session.rollback()
            UserService._raise_error(
                ValidationError,
                ValidationError.TOGGLE_STATUS_ERROR,
                str(e),
            )
        return user

    @staticmethod
    def login(session: Session, user: User) -> User:
        """Update user's last login timestamp.

        Args:
            session: Database session
            user: User instance

        Returns:
            Updated user instance

        """
        user.last_login = get_current_datetime()
        session.commit()
        return user

    @staticmethod
    def grant_admin(session: Session, user: User, granting_user_id: int) -> User:
        """Grant admin privileges to a user.

        Args:
            session: Database session
            user: User instance
            granting_user_id: ID of user granting admin privileges

        Returns:
            Updated user instance

        Raises:
            AuthorizationError: If granting user is not an admin

        """
        try:
            # Check if granting user is an admin
            stmt: select[tuple[User]] = select(User).where(User.id == granting_user_id)
            granting_user: User | None = session.execute(stmt).scalar_one_or_none()
            if not granting_user or not granting_user.is_admin:
                UserService._raise_error(
                    AuthorizationError,
                    AuthorizationError.ADMIN_ONLY,
                )

            # Set admin flag
            user.is_admin = True
            user.updated_at = get_current_datetime()
            session.commit()

            # Prepare response data
            user_data: dict[str, any] = user_schema.dump(user)
            user_data_dict: dict[str, any] = (
                user_data if isinstance(user_data, dict) else user_data[0]
            )

            # Emit WebSocket event
            EventService.emit_user_update(
                action="admin_granted",
                user_data=user_data_dict,
                user_id=user.id,
            )

        except Exception as e:
            logger.exception("Error granting admin privileges")
            session.rollback()
            if isinstance(e, (AuthorizationError, ResourceNotFoundError)):
                raise
            UserService._raise_error(
                ValidationError,
                ValidationError.GRANT_ADMIN_ERROR,
                str(e),
            )
        return user

    @staticmethod
    def delete_user(session: Session, user: User) -> bool:
        """Delete a user.

        Args:
            session: Database session
            user: User instance

        Returns:
            True if user was deleted, False otherwise

        """
        try:
            # Delete user
            session.delete(user)
            session.commit()

            # Emit WebSocket event
            EventService.emit_user_update(
                action="deleted",
                user_data={"id": user.id},
                user_id=user.id,
            )

        except Exception as e:
            logger.exception("Error deleting user")
            session.rollback()
            UserService._raise_error(
                ValidationError,
                ValidationError.DELETE_USER_ERROR,
                str(e),
            )
        return True

    @staticmethod
    def change_password(
        session: Session,
        user: User,
        current_password: str,
        new_password: str,
    ) -> User:
        """Change user's password.

        Args:
            session: Database session
            user: User instance
            current_password: Current password for verification
            new_password: New password to set

        Returns:
            Updated user instance

        Raises:
            ValidationError: If current password is incorrect or new password is invalid

        """
        try:
            # Verify current password
            if not user.verify_password(current_password):
                UserService._raise_error(
                    ValidationError,
                    ValidationError.INVALID_PASSWORD,
                )

            # Set new password (triggers validation)
            user.password = new_password
            user.updated_at = get_current_datetime()
            session.commit()

        except Exception as e:
            logger.exception("Error changing password")
            session.rollback()
            if isinstance(e, ValidationError):
                raise
            UserService._raise_error(
                ValidationError,
                ValidationError.CHANGE_PASSWORD_ERROR,
                str(e),
            )
        return user

    @staticmethod
    def days_since_login(user: User) -> int | None:
        """Calculate days since last login.

        Args:
            user: User instance

        Returns:
            Number of days since last login, or None if never logged in

        """
        if user.last_login is None:
            return None
        return (get_current_datetime() - user.last_login).days

    @staticmethod
    def user_to_dict(user: User) -> dict[str, any]:
        """Convert user to dictionary for API responses.

        Args:
            user: User instance

        Returns:
            Dictionary with user data

        """
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "last_login": (
                user.last_login.isoformat() if user.last_login is not None else None
            ),
            "created_at": (
                user.created_at.isoformat() if user.created_at is not None else None
            ),
            "updated_at": (
                user.updated_at.isoformat() if user.updated_at is not None else None
            ),
        }
