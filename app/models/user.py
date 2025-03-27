"""
User model.

This model represents user accounts for authentication and authorization.
"""
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, func
from sqlalchemy.orm import relationship, Mapped
from werkzeug.security import generate_password_hash, check_password_hash

from app.models.base import Base

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
    __tablename__ = 'users'
    
    # Basic information
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    services: Mapped[List["TradingService"]] = relationship("TradingService", back_populates="user", cascade="all, delete-orphan")
    
    # We're not exposing the password directly
    @property
    def password(self):
        """Password getter - raises error as password is write-only."""
        raise AttributeError('Password is not readable')
    
    @password.setter
    def password(self, password):
        """Password setter - hashes and stores the password."""
        self.password_hash = generate_password_hash(password)
    
    def verify_password(self, password):
        """Verify password against stored hash."""
        return check_password_hash(self.password_hash, password)
    
    def update_last_login(self):
        """Update the last login timestamp to now."""
        self.last_login = datetime.now(datetime.UTC)
    
    def __repr__(self) -> str:
        """String representation of the User object."""
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>" 