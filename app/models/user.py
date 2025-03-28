"""
User model.

This model represents user accounts for authentication and authorization.
"""
import logging
import re
from typing import Optional, List, TYPE_CHECKING, Dict, Any, Union, Set
from datetime import datetime, timedelta

from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, event, or_
from sqlalchemy.orm import relationship, Mapped, Session, validates
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app

from app.models.base import Base
from app.utils.current_datetime import get_current_datetime
from app.utils.errors import AuthorizationError, ValidationError, ResourceNotFoundError
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
    
    def update(self, session: Session, data: Dict[str, Any]) -> "User":
        """
        Update user attributes.
        
        Args:
            session: Database session
            data: Dictionary of attributes to update
            
        Returns:
            Updated user instance
            
        Raises:
            ValueError: If invalid data is provided
        """
        from app.api.schemas.user import user_schema
        from app.services.events import EventService
        
        try:
            # Define which fields can be updated
            allowed_fields = {
                'username', 'email', 'is_active', 'is_admin'
            }
            
            # Check for username uniqueness if changing
            if 'username' in data and data['username'] != self.username:
                existing = self.find_by_username(session, data['username'])
                if existing:
                    raise ValueError(f"Username '{data['username']}' already exists")
                    
            # Check for email uniqueness if changing
            if 'email' in data and data['email'] != self.email:
                existing = self.find_by_email(session, data['email'])
                if existing:
                    raise ValueError(f"Email '{data['email']}' already exists")
            
            # Update allowed fields
            updated = self.update_from_dict(data, allowed_fields)
            
            # Handle password update separately for security
            if 'password' in data and data['password']:
                self.password = data['password']
                updated = True
            
            # Only commit if something was updated
            if updated:
                self.updated_at = get_current_datetime()
                session.commit()
                
                # Prepare response data
                user_data = user_schema.dump(self)
                
                # Emit WebSocket event
                EventService.emit_user_update(
                    action='updated',
                    user_data=user_data,
                    user_id=self.id
                )
            
            return self
        except Exception as e:
            logger.error(f"Error updating user: {str(e)}")
            session.rollback()
            raise ValueError(f"Could not update user: {str(e)}")
    
    def toggle_active(self, session: Session) -> "User":
        """
        Toggle user active status.
        
        Args:
            session: Database session
            
        Returns:
            Updated user instance
        """
        from app.api.schemas.user import user_schema
        from app.services.events import EventService
        
        try:
            # Toggle status
            self.is_active = not self.is_active
            self.updated_at = get_current_datetime()
            
            session.commit()
            
            # Prepare response data
            user_data = user_schema.dump(self)
            action = 'activated' if self.is_active else 'deactivated'
            
            # Emit WebSocket event
            EventService.emit_user_update(
                action=action,
                user_data=user_data,
                user_id=self.id
            )
            
            return self
        except Exception as e:
            logger.error(f"Error toggling user active status: {str(e)}")
            session.rollback()
            raise ValueError(f"Could not toggle user active status: {str(e)}")
    
    def login(self, session: Session) -> "User":
        """
        Record user login.
        
        Args:
            session: Database session
            
        Returns:
            Updated user instance
        """
        self.last_login = get_current_datetime()
        session.commit()
        return self
    
    @classmethod
    def create_user(cls, session: Session, data: Dict[str, Any]) -> "User":
        """
        Create a new user.
        
        Args:
            session: Database session
            data: User data dictionary
            
        Returns:
            Created user instance
            
        Raises:
            ValueError: If required fields are missing
        """
        from app.api.schemas.user import user_schema
        from app.services.events import EventService
        
        try:
            # Validate required fields
            required_fields = ['username', 'email', 'password']
            for field in required_fields:
                if field not in data or not data[field]:
                    raise ValueError(f"Field '{field}' is required")
                    
            # Check for duplicate username or email
            existing_user = session.query(cls).filter(
                or_(cls.username == data['username'], cls.email == data['email'])
            ).first()
            
            if existing_user:
                if existing_user.username == data['username']:
                    raise ValueError(f"Username '{data['username']}' already exists")
                else:
                    raise ValueError(f"Email '{data['email']}' already exists")
            
            # Create password_hash from password
            password = data.pop('password', None)
            
            # Create user from data
            user = cls.from_dict(data)
            
            # Set password (triggers validation and hashing)
            if password:
                user.password = password
            
            session.add(user)
            session.commit()
            
            # Prepare response data
            user_data = user_schema.dump(user)
            
            # Emit WebSocket event
            EventService.emit_user_update(
                action='created',
                user_data=user_data,
                user_id=user.id
            )
            
            return user
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            session.rollback()
            raise ValueError(f"Could not create user: {str(e)}")
    
    def grant_admin(self, session: Session, granting_user_id: int) -> "User":
        """
        Grant admin privileges to a user.
        
        Args:
            session: Database session
            granting_user_id: ID of the user granting admin privileges
            
        Returns:
            Updated user instance
            
        Raises:
            AuthorizationError: If the granting user is not an admin
        """
        from app.api.schemas.user import user_schema
        from app.services.events import EventService
        
        try:
            # Verify that granting user is an admin
            granting_user = User.get_or_404(session, granting_user_id)
            if not granting_user.is_admin:
                raise AuthorizationError("Only administrators can grant admin privileges")
            
            # Grant admin privileges if not already an admin
            if not self.is_admin:
                self.is_admin = True
                self.updated_at = get_current_datetime()
                session.commit()
                
                # Prepare response data
                user_data = user_schema.dump(self)
                
                # Emit WebSocket event
                EventService.emit_user_update(
                    action='admin_granted',
                    user_data=user_data,
                    user_id=self.id,
                    additional_data={'granted_by': granting_user_id}
                )
            
            return self
        except Exception as e:
            logger.error(f"Error granting admin privileges: {str(e)}")
            session.rollback()
            if isinstance(e, AuthorizationError):
                raise
            raise ValueError(f"Could not grant admin privileges: {str(e)}")
    
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