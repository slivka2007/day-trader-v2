"""
User service for managing User model operations.

This service encapsulates all database interactions for the User model,
providing a clean API for user management operations.
"""

import logging

from sqlalchemy import or_, select
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
    def find_by_username(session: Session, username: str) -> User | None:
        """
        Find a user by username.

        Args:
            session: Database session
            username: Username to search for

        Returns:
            User instance if found, None otherwise
        """
        stmt: select[tuple[User]] = select(User).where(User.username == username)
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def find_by_email(session: Session, email: str) -> User | None:
        """
        Find a user by email.

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
        """
        Find a user by username or email.

        Args:
            session: Database session
            identifier: Username or email to search for

        Returns:
            User instance if found, None otherwise
        """
        stmt: select[tuple[User]] = select(User).where(
            or_(User.username == identifier, User.email == identifier)
        )
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_by_id(session: Session, user_id: int) -> User | None:
        """
        Get a user by ID.

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
        """
        Get a user by ID or raise ResourceNotFoundError.

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
            raise ResourceNotFoundError(
                f"User with ID {user_id} not found", resource_id=user_id
            )
        return user

    @staticmethod
    def get_all(session: Session) -> list[User]:
        """
        Get all users.

        Args:
            session: Database session

        Returns:
            List of User instances
        """
        stmt: select[tuple[User]] = select(User)
        return list(session.execute(stmt).scalars().all())

    @staticmethod
    def create_user(session: Session, data: dict[str, any]) -> User:
        """
        Create a new user.

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
            # Validate data is a dictionary
            data_dict: dict[str, any] = data if isinstance(data, dict) else {}

            # Validate required fields
            required_fields: list[str] = ["username", "email", "password"]
            for field in required_fields:
                if field not in data_dict or not data_dict.get(field):
                    raise ValidationError(f"Field '{field}' is required")

            # Check for duplicate username or email
            stmt: select[tuple[User]] = select(User).where(
                or_(
                    User.username == data_dict.get("username"),
                    User.email == data_dict.get("email"),
                )
            )
            existing_user: User | None = session.execute(stmt).scalar_one_or_none()

            if existing_user:
                if existing_user.username == data_dict.get("username"):
                    raise ValidationError(
                        f"Username '{data_dict.get('username')}' already exists"
                    )
                else:
                    raise ValidationError(
                        f"Email '{data_dict.get('email')}' already exists"
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
                action="created", user_data=user_data_dict, user_id=user.id
            )

            return user
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            session.rollback()
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Could not create user: {str(e)}") from e

    @staticmethod
    def update_user(session: Session, user: User, data: dict[str, any]) -> User:
        """
        Update user attributes.

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
            # Validate data is a dictionary
            data_dict: dict[str, any] = data if isinstance(data, dict) else {}

            # Define which fields can be updated
            allowed_fields: set[str] = {"username", "email", "is_active", "is_admin"}

            # Check for username uniqueness if changing
            if "username" in data_dict and data_dict.get("username") != user.username:
                existing: User | None = UserService.find_by_username(
                    session, data_dict.get("username", "")
                )
                if existing:
                    raise ValidationError(
                        f"Username '{data_dict.get('username')}' already exists"
                    )

            # Check for email uniqueness if changing
            if "email" in data_dict and data_dict.get("email") != user.email:
                existing: User | None = UserService.find_by_email(
                    session, data_dict.get("email", "")
                )
                if existing:
                    raise ValidationError(
                        f"Email '{data_dict.get('email')}' already exists"
                    )

            # Update allowed fields
            updated = False
            for field in allowed_fields:
                if field in data_dict:
                    setattr(user, field, data_dict.get(field))
                    updated = True

            # Handle password update separately for security
            if "password" in data_dict and data_dict.get("password"):
                user.password = data_dict.get("password", "")
                updated = True

            # Only commit if something was updated
            if updated:
                user.updated_at = get_current_datetime()
                session.commit()

                # Prepare response data
                user_data: dict[str, any] = user_schema.dump(user)
                user_data_dict: dict[str, any] = (
                    user_data if isinstance(user_data, dict) else user_data[0]
                )

                # Emit WebSocket event
                EventService.emit_user_update(
                    action="updated", user_data=user_data_dict, user_id=user.id
                )

            return user
        except Exception as e:
            logger.error(f"Error updating user: {str(e)}")
            session.rollback()
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Could not update user: {str(e)}") from e

    @staticmethod
    def toggle_active(session: Session, user: User) -> User:
        """
        Toggle user active status.

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

            return user
        except Exception as e:
            logger.error(f"Error toggling user status: {str(e)}")
            session.rollback()
            raise ValidationError(f"Could not toggle user status: {str(e)}") from e

    @staticmethod
    def login(session: Session, user: User) -> User:
        """
        Update user's last login timestamp.

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
        """
        Grant admin privileges to a user.

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
                raise AuthorizationError("Only admins can grant admin privileges")

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
                action="admin_granted", user_data=user_data_dict, user_id=user.id
            )

            return user
        except Exception as e:
            logger.error(f"Error granting admin privileges: {str(e)}")
            session.rollback()
            if isinstance(e, (AuthorizationError, ResourceNotFoundError)):
                raise
            raise ValidationError(f"Could not grant admin privileges: {str(e)}") from e

    @staticmethod
    def delete_user(session: Session, user: User) -> bool:
        """
        Delete a user.

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
                action="deleted", user_data={"id": user.id}, user_id=user.id
            )

            return True
        except Exception as e:
            logger.error(f"Error deleting user: {str(e)}")
            session.rollback()
            raise ValidationError(f"Could not delete user: {str(e)}") from e

    @staticmethod
    def change_password(
        session: Session, user: User, current_password: str, new_password: str
    ) -> User:
        """
        Change user's password.

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
                raise ValidationError("Current password is incorrect")

            # Set new password (triggers validation)
            user.password = new_password
            user.updated_at = get_current_datetime()
            session.commit()

            return user
        except Exception as e:
            logger.error(f"Error changing password: {str(e)}")
            session.rollback()
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Could not change password: {str(e)}") from e

    @staticmethod
    def days_since_login(user: User) -> int | None:
        """
        Calculate days since last login.

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
        """
        Convert user to dictionary for API responses.

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
