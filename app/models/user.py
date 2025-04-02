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
from app.utils.current_datetime import get_current_datetime

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
    MIN_USERNAME_LENGTH: int = 3
    MAX_USERNAME_LENGTH: int = 50
    MIN_PASSWORD_LENGTH: int = 8

    # Error messages
    ERR_USERNAME_REQUIRED: str = "Username is required"
    ERR_USERNAME_LENGTH: str = (
        f"Username must be between {MIN_USERNAME_LENGTH} and "
        f"{MAX_USERNAME_LENGTH} characters"
    )
    ERR_USERNAME_FORMAT: str = (
        "Username can only contain letters, numbers, underscores, and hyphens"
    )
    ERR_EMAIL_REQUIRED: str = "Email is required"
    ERR_EMAIL_FORMAT: str = "Invalid email format"
    ERR_PASSWORD_REQUIRED: str = "Password is required"  # noqa: S105
    ERR_PASSWORD_LENGTH: str = (
        f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
    )
    ERR_PASSWORD_COMPLEXITY: str = (
        "Password must contain at least one uppercase letter, "  # noqa: S105
        "one lowercase letter, and one digit"
    )
    ERR_PASSWORD_NOT_READABLE: str = "Password is not a readable attribute"  # noqa: S105

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
            raise ValueError(self.ERR_USERNAME_REQUIRED)
        if (
            len(username) < self.MIN_USERNAME_LENGTH
            or len(username) > self.MAX_USERNAME_LENGTH
        ):
            raise ValueError(self.ERR_USERNAME_LENGTH)
        # Check username format
        if not re.match(r"^[a-zA-Z0-9_-]+$", username):
            raise ValueError(self.ERR_USERNAME_FORMAT)
        return username

    @validates("email")
    def validate_email(self, email: str) -> str:
        """Validate email."""
        if not email:
            raise ValueError(self.ERR_EMAIL_REQUIRED)
        # More comprehensive email validation
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
            raise ValueError(self.ERR_EMAIL_FORMAT)
        return email

    @property
    def password(self) -> str:
        """Password getter."""
        raise AttributeError(self.ERR_PASSWORD_NOT_READABLE)

    @password.setter
    def password(self, password: str) -> None:
        """Password setter - hash the password."""
        if not password:
            raise ValueError(self.ERR_PASSWORD_REQUIRED)
        if len(password) < self.MIN_PASSWORD_LENGTH:
            raise ValueError(self.ERR_PASSWORD_LENGTH)
        # More advanced password validation
        if not (
            any(c.isupper() for c in password)
            and any(c.islower() for c in password)
            and any(c.isdigit() for c in password)
        ):
            raise ValueError(self.ERR_PASSWORD_COMPLEXITY)
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password: str) -> bool:
        """Verify password."""
        return check_password_hash(self.password_hash, password)

    @property
    def has_active_services(self) -> bool:
        """Check if user has any active trading services."""
        return any(service.is_active for service in self.services)

    def __repr__(self) -> str:
        """Return string representation of the User object."""
        return f"<User {self.username}>"
