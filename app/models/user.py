"""User model.

This model represents user accounts for authentication and authorization.
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
        services: Trading services owned by this user

    """

    __tablename__: str = "users"

    # Constants
    MIN_USERNAME_LENGTH: int = UserConstants.MIN_USERNAME_LENGTH
    MAX_USERNAME_LENGTH: int = UserConstants.MAX_USERNAME_LENGTH
    MIN_PASSWORD_LENGTH: int = UserConstants.MIN_PASSWORD_LENGTH

    id: Mapped[int] = Column(Integer, primary_key=True)
    username: Mapped[str] = Column(
        String(MAX_USERNAME_LENGTH),
        unique=True,
        nullable=False,
    )
    email: Mapped[str] = Column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = Column(String(128), nullable=False)
    is_active: Mapped[bool] = Column(Boolean, default=True)
    is_admin: Mapped[bool] = Column(Boolean, default=False)
    last_login: Mapped[datetime] = Column(DateTime)
    created_at: Mapped[datetime] = Column(DateTime, default=get_current_datetime)
    updated_at: Mapped[datetime] = Column(
        DateTime,
        default=get_current_datetime,
        onupdate=get_current_datetime,
    )

    # Relationships
    services: Mapped[list["TradingService"]] = relationship(
        "TradingService",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @validates("username")
    def validate_username(self, username: str) -> str:
        """Validate username."""
        if not username:
            raise ValueError(UserError.USERNAME_REQUIRED)
        if (
            len(username) < self.MIN_USERNAME_LENGTH
            or len(username) > self.MAX_USERNAME_LENGTH
        ):
            raise ValueError(
                UserError.USERNAME_LENGTH.format(
                    self.MIN_USERNAME_LENGTH,
                    self.MAX_USERNAME_LENGTH,
                ),
            )
        # Check username format
        if not re.match(r"^[a-zA-Z0-9_-]+$", username):
            raise ValueError(UserError.USERNAME_FORMAT)
        return username

    @validates("email")
    def validate_email(self, email: str) -> str:
        """Validate email."""
        if not email:
            raise ValueError(UserError.EMAIL_REQUIRED)
        # More comprehensive email validation
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
            raise ValueError(UserError.EMAIL_FORMAT)
        return email

    @property
    def password(self) -> str:
        """Password getter."""
        raise AttributeError(UserError.PASSWORD_NOT_READABLE)

    @password.setter
    def password(self, password: str) -> None:
        """Password setter - hash the password."""
        if not password:
            raise ValueError(UserError.PASSWORD_REQUIRED)
        if len(password) < self.MIN_PASSWORD_LENGTH:
            raise ValueError(UserError.PASSWORD_LENGTH.format(self.MIN_PASSWORD_LENGTH))
        # More advanced password validation
        if not (
            any(c.isupper() for c in password)
            and any(c.islower() for c in password)
            and any(c.isdigit() for c in password)
        ):
            raise ValueError(UserError.PASSWORD_COMPLEXITY)
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password: str) -> bool:
        """Verify password."""
        return check_password_hash(self.password_hash, password)

    def update_last_login(self) -> None:
        """Update the last login timestamp to current time."""
        self.last_login = get_current_datetime()

    @property
    def has_active_services(self) -> bool:
        """Check if user has any active trading services."""
        return any(service.is_active for service in self.services)

    def __repr__(self) -> str:
        """Return string representation of the User object."""
        return f"<User {self.username}>"
