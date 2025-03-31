"""
User model.

This model represents user accounts for authentication and authorization.
"""

import re
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import Mapped, relationship, validates
from werkzeug.security import check_password_hash, generate_password_hash

from app.models.base import Base
from app.utils.current_datetime import get_current_datetime

if TYPE_CHECKING:
    from app.models.trading_service import TradingService


class User(Base):
    """
    Model representing a user account.

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

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=get_current_datetime)
    updated_at = Column(
        DateTime, default=get_current_datetime, onupdate=get_current_datetime
    )

    # Relationships
    services: Mapped[List["TradingService"]] = relationship(
        "TradingService", back_populates="user", cascade="all, delete-orphan"
    )

    @validates("username")
    def validate_username(self, _key, username) -> str:
        """Validate username."""
        if not username:
            raise ValueError("Username is required")
        if len(username) < 3 or len(username) > 50:
            raise ValueError("Username must be between 3 and 50 characters")
        # Check username format
        if not re.match(r"^[a-zA-Z0-9_-]+$", username):
            raise ValueError(
                "Username can only contain letters, numbers, underscores, and hyphens"
            )
        return username

    @validates("email")
    def validate_email(self, _key, email) -> str:
        """Validate email."""
        if not email:
            raise ValueError("Email is required")
        # More comprehensive email validation
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
            raise ValueError("Invalid email format")
        return email

    @property
    def password(self) -> str:
        """Password getter."""
        raise AttributeError("Password is not a readable attribute")

    @password.setter
    def password(self, password: str) -> None:
        """Password setter - hash the password."""
        if not password:
            raise ValueError("Password is required")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        # More advanced password validation
        if not (
            any(c.isupper() for c in password)
            and any(c.islower() for c in password)
            and any(c.isdigit() for c in password)
        ):
            raise ValueError(
                "Password must contain at least one uppercase letter, "
                "one lowercase letter, and one digit"
            )
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password: str) -> bool:
        """Verify password."""
        if not password:
            return False
        return check_password_hash(str(self.password_hash), password)

    @property
    def has_active_services(self) -> bool:
        """Check if user has any active trading services."""
        services = getattr(self, "services", [])
        return bool(
            any(service.__dict__.get("is_active", False) for service in services)
        )

    def __repr__(self) -> str:
        """String representation."""
        return f"<User {self.username}>"
