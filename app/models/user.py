"""
User model.

This model represents user accounts for authentication and authorization.
"""
import logging
import re
from typing import Optional, List, TYPE_CHECKING, Dict, Any
from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime, or_
from sqlalchemy.orm import relationship, Mapped, validates, Session
from werkzeug.security import generate_password_hash, check_password_hash

from app.models.base import Base
from app.utils.current_datetime import get_current_datetime
if TYPE_CHECKING:
    from app.models.trading_service import TradingService

# Set up logging
logger = logging.getLogger(__name__)

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
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=get_current_datetime)
    updated_at = Column(DateTime, default=get_current_datetime, onupdate=get_current_datetime)
    
    # Relationships
    services: Mapped[List["TradingService"]] = relationship("TradingService", back_populates="user", cascade="all, delete-orphan")
    
    @validates('username')
    def validate_username(self, key, username):
        """Validate username."""
        if not username:
            raise ValueError("Username is required")
        if len(username) < 3 or len(username) > 50:
            raise ValueError("Username must be between 3 and 50 characters")
        # Check username format
        if not re.match(r'^[a-zA-Z0-9_-]+$', username):
            raise ValueError("Username can only contain letters, numbers, underscores, and hyphens")
        return username
    
    @validates('email')
    def validate_email(self, key, email):
        """Validate email."""
        if not email:
            raise ValueError("Email is required")
        # More comprehensive email validation
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            raise ValueError("Invalid email format")
        return email
    
    @property
    def password(self):
        """Password getter."""
        raise AttributeError('Password is not a readable attribute')
    
    @password.setter
    def password(self, password):
        """Password setter - hash the password."""
        if not password:
            raise ValueError("Password is required")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        # More advanced password validation
        if not (any(c.isupper() for c in password) and 
                any(c.islower() for c in password) and
                any(c.isdigit() for c in password)):
            raise ValueError("Password must contain at least one uppercase letter, one lowercase letter, and one digit")
        self.password_hash = generate_password_hash(password)
    
    def verify_password(self, password):
        """Verify password."""
        if not password:
            return False
        return check_password_hash(self.password_hash, password)
    
    @property
    def has_active_services(self) -> bool:
        """Check if user has any active trading services."""
        return any(service.is_active for service in self.services)
    
    @property
    def days_since_login(self) -> Optional[int]:
        """Get days since last login."""
        if not self.last_login:
            return None
        return (get_current_datetime() - self.last_login).days
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary for API responses."""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
    def __repr__(self) -> str:
        """String representation."""
        return f'<User {self.username}>'
    
    # Class methods for database queries
    @classmethod
    def get_by_id(cls, session: Session, user_id: int) -> Optional["User"]:
        """
        Get a user by ID.
        
        Args:
            session: Database session
            user_id: User ID to retrieve
            
        Returns:
            User instance if found, None otherwise
        """
        return session.query(cls).get(user_id)
    
    @classmethod
    def find_by_username(cls, session: Session, username: str) -> Optional["User"]:
        """
        Find a user by username.
        
        Args:
            session: Database session
            username: Username to search for
            
        Returns:
            User instance if found, None otherwise
        """
        return session.query(cls).filter(cls.username == username).first()
    
    @classmethod
    def find_by_email(cls, session: Session, email: str) -> Optional["User"]:
        """
        Find a user by email.
        
        Args:
            session: Database session
            email: Email to search for
            
        Returns:
            User instance if found, None otherwise
        """
        return session.query(cls).filter(cls.email == email).first()
    
    @classmethod
    def find_by_username_or_email(cls, session: Session, identifier: str) -> Optional["User"]:
        """
        Find a user by username or email.
        
        Args:
            session: Database session
            identifier: Username or email to search for
            
        Returns:
            User instance if found, None otherwise
        """
        return session.query(cls).filter(
            or_(cls.username == identifier, cls.email == identifier)
        ).first()
    
    @classmethod
    def get_all(cls, session: Session) -> List["User"]:
        """
        Get all users.
        
        Args:
            session: Database session
            
        Returns:
            List of User instances
        """
        return session.query(cls).all() 