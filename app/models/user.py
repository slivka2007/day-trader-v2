"""User model.

This module defines the User model which represents user accounts for
authentication and authorization purposes, managing access to the application.
"""

import re
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import Mapped, relationship, validates
from werkzeug.security import check_password_hash, generate_password_hash

from app.models.base import Base
from app.utils.constants import UserConstants
from app.utils.current_datetime import get_current_datetime
from app.utils.errors import UserError
from app.utils.validators import validate_email, validate_max_length

if TYPE_CHECKING:
    from app.models.trading_service import TradingService


class User(Base):
    """Model representing a user account.

    Stores user authentication and authorization information.

    Attributes:
        id: Unique identifier for the user
        username: Unique username for login
        email: User's email address
        password_hash: Hashed password
        is_active: Whether the user account is active
        is_admin: Whether the user has admin privileges
        last_login: Timestamp of last login
        created_at: Timestamp when the user was created
        updated_at: Timestamp when the user was last updated
        services: Trading services owned by this user

    Properties:
        password: Property for setting the password (raises error when getting)
        has_active_services: Whether the user has any active trading services

    """

    #
    # SQLAlchemy configuration
    #
    __tablename__: str = "users"

    #
    # Constants
    #
    MIN_USERNAME_LENGTH: int = UserConstants.MIN_USERNAME_LENGTH
    MAX_USERNAME_LENGTH: int = UserConstants.MAX_USERNAME_LENGTH
    MIN_PASSWORD_LENGTH: int = UserConstants.MIN_PASSWORD_LENGTH

    #
    # Column definitions
    #

    # Identity
    id: Mapped[int] = Column(Integer, primary_key=True)

    # Authentication
    username: Mapped[str] = Column(
        String(MAX_USERNAME_LENGTH),
        unique=True,
        nullable=False,
    )
    email: Mapped[str] = Column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = Column(String(128), nullable=False)

    # Status
    is_active: Mapped[bool] = Column(Boolean, default=True)
    is_admin: Mapped[bool] = Column(Boolean, default=False)
    last_login: Mapped[datetime] = Column(DateTime, nullable=True)

    # Timestamps (overriding Base fields for clarity)
    created_at: Mapped[datetime] = Column(DateTime, default=get_current_datetime)
    updated_at: Mapped[datetime] = Column(
        DateTime,
        default=get_current_datetime,
        onupdate=get_current_datetime,
    )

    #
    # Relationships
    #
    services: Mapped[list["TradingService"]] = relationship(
        "TradingService",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    #
    # Magic methods
    #
    def __repr__(self) -> str:
        """Return string representation of the User object."""
        return (
            f"<User(id={self.id}, username='{self.username}', "
            f"active={self.is_active}, admin={self.is_admin})>"
        )

    #
    # Validation methods
    #
    @validates("username")
    def validate_username(self, key: str, username: str) -> str:
        """Validate username.

        Args:
            key: The attribute name being validated
            username: The username to validate

        Returns:
            The validated username

        Raises:
            UserError: If the username is invalid

        """
        if not username:
            raise UserError(
                UserError.USERNAME_REQUIRED.format(key=key, value=username),
            )

        # Validate length
        username = validate_max_length(
            value=username,
            max_length=self.MAX_USERNAME_LENGTH,
            error_class=UserError,
            key=key,
            error_attr="USERNAME_LENGTH",
        )

        # Also check minimum length
        if len(username) < self.MIN_USERNAME_LENGTH:
            raise UserError(
                UserError.USERNAME_LENGTH.format(
                    key=key,
                    value=username,
                ),
            )

        # Check username format
        if not re.match(r"^[a-zA-Z0-9_-]+$", username):
            raise UserError(
                UserError.USERNAME_FORMAT.format(key=key, value=username),
            )

        return username

    @validates("email")
    def validate_email(self, key: str, email: str) -> str:
        """Validate email.

        Args:
            key: The attribute name being validated
            email: The email to validate

        Returns:
            The validated email

        Raises:
            UserError: If the email is invalid

        """
        return validate_email(
            email=email,
            error_class=UserError,
            key=key,
            required=True,
        )

    #
    # Properties
    #
    @property
    def password(self) -> str:
        """Password getter.

        Raises:
            AttributeError: Password is not directly readable

        """
        raise AttributeError(UserError.PASSWORD_NOT_READABLE)

    @password.setter
    def password(self, password: str) -> None:
        """Password setter - hash the password.

        Args:
            password: The password to set

        Raises:
            UserError: If the password is invalid

        """
        if not password:
            raise UserError(UserError.PASSWORD_REQUIRED)

        if len(password) < self.MIN_PASSWORD_LENGTH:
            raise UserError(UserError.PASSWORD_LENGTH.format(self.MIN_PASSWORD_LENGTH))

        # More advanced password validation
        if not (
            any(c.isupper() for c in password)
            and any(c.islower() for c in password)
            and any(c.isdigit() for c in password)
        ):
            raise UserError(UserError.PASSWORD_COMPLEXITY)

        self.password_hash = generate_password_hash(password)

    @property
    def has_active_services(self) -> bool:
        """Check if user has any active trading services.

        Returns:
            True if the user has at least one active trading service

        """
        return any(service.is_active for service in self.services)

    #
    # Instance methods
    #
    def verify_password(self, password: str) -> bool:
        """Verify password.

        Args:
            password: The password to verify

        Returns:
            True if the password matches the hash, False otherwise

        """
        return check_password_hash(self.password_hash, password)

    def update_last_login(self) -> None:
        """Update the last login timestamp to current time."""
        self.last_login = get_current_datetime()
