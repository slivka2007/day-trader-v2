"""
Base model classes and helpers for SQLAlchemy models.

This module defines the base classes and common functionality used by all models.
It provides foundation classes with standardized behavior for timestamps, serialization,
validation, and error handling.
"""

import json
import logging
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Type

from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, class_mapper, ColumnProperty

from app.utils.current_datetime import get_current_datetime

# Set up logging
logger = logging.getLogger(__name__)

# Create the base declarative class
DeclarativeBase = declarative_base()

class Base(DeclarativeBase):
    """
    Abstract base class for all database models.
    
    This class provides common columns and functionality that should be present
    in all models, such as timestamps for creation and updates, serialization
    methods for API responses, and validation utilities.
    
    Attributes:
        id: Primary key for all models
        created_at: Timestamp when the record was created
        updated_at: Timestamp when the record was last updated
    """
    __abstract__ = True
    
    # Primary key for all models
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Timestamps for record tracking
    created_at = Column(DateTime, default=get_current_datetime, nullable=False)
    updated_at = Column(DateTime, default=get_current_datetime, onupdate=get_current_datetime, nullable=False)
    
    def __repr__(self) -> str:
        """
        Default string representation of a model.
        
        Returns:
            String representation showing class name and ID
        """
        return f"<{self.__class__.__name__}(id={self.id})>"
    
    @classmethod
    def get_by_id(cls, session: Session, id: int) -> Optional["Base"]:
        """
        Get a record by its ID.
        
        Args:
            session: Database session
            id: Record ID
            
        Returns:
            Model instance if found, None otherwise
        """
        return session.query(cls).filter(cls.id == id).first()
    
    @classmethod
    def get_or_404(cls, session: Session, id: int) -> "Base":
        """
        Get a record by its ID or raise ResourceNotFoundError.
        
        Args:
            session: Database session
            id: Record ID
            
        Returns:
            Model instance
            
        Raises:
            ResourceNotFoundError: If record not found
        """
        from app.utils.errors import ResourceNotFoundError
        
        record = cls.get_by_id(session, id)
        if not record:
            raise ResourceNotFoundError(resource_type=cls.__name__, resource_id=id)
        return record
        
    def to_dict(self, include_relationships: bool = False, exclude: Optional[Set[str]] = None) -> Dict[str, Any]:
        """
        Convert the model instance to a dictionary.
        
        Args:
            include_relationships: Whether to include relationships in the output
            exclude: Set of attribute names to exclude from the result
            
        Returns:
            Dictionary representation of the model
        """
        if exclude is None:
            exclude = set()
            
        result = {}
        
        # Add all column attributes
        for column in self.__table__.columns:
            if column.name in exclude:
                continue
                
            value = getattr(self, column.name)
            result[column.name] = self._serialize_value(value)
        
        # Add relationships if requested
        if include_relationships:
            for relationship in self.__mapper__.relationships:
                # Skip if in exclude list
                if relationship.key in exclude:
                    continue
                    
                # Skip backrefs to avoid circular references
                if relationship.back_populates or relationship.backref:
                    continue
                    
                related_obj = getattr(self, relationship.key)
                
                if related_obj is None:
                    result[relationship.key] = None
                elif isinstance(related_obj, list):
                    result[relationship.key] = [
                        item.to_dict(include_relationships=False, exclude=exclude) 
                        for item in related_obj
                    ]
                else:
                    result[relationship.key] = related_obj.to_dict(
                        include_relationships=False, exclude=exclude
                    )
        
        return result
    
    def to_json(self, include_relationships: bool = False, exclude: Optional[Set[str]] = None) -> str:
        """
        Convert the model instance to a JSON string.
        
        Args:
            include_relationships: Whether to include relationships in the output
            exclude: Set of attribute names to exclude from the result
            
        Returns:
            JSON string representation of the model
        """
        try:
            return json.dumps(self.to_dict(
                include_relationships=include_relationships, 
                exclude=exclude
            ))
        except Exception as e:
            logger.error(f"Error serializing {self.__class__.__name__} to JSON: {str(e)}")
            return json.dumps({"error": "Serialization error", "id": self.id})
    
    @staticmethod
    def _serialize_value(value: Any) -> Any:
        """
        Serialize a value for JSON compatibility.
        
        Args:
            value: The value to serialize
            
        Returns:
            JSON-compatible representation of the value
        """
        if value is None:
            return None
        elif isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, Decimal):
            return float(value)
        elif isinstance(value, Enum):
            return value.value
        elif hasattr(value, 'to_dict') and callable(value.to_dict):
            return value.to_dict()
        return value
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], ignore_unknown: bool = True) -> Any:
        """
        Create a new instance from a dictionary.
        
        Args:
            data: Dictionary containing model data
            ignore_unknown: Whether to ignore keys that don't match model columns
            
        Returns:
            A new instance of the model
            
        Raises:
            ValueError: If required data is missing or invalid and ignore_unknown is False
        """
        # Get column names
        columns = {c.key for c in class_mapper(cls).columns}
        
        # Filter data to only include valid columns
        valid_data = {}
        for key, value in data.items():
            if key in columns:
                valid_data[key] = value
            elif not ignore_unknown:
                raise ValueError(f"Unknown column '{key}' for {cls.__name__}")
                
        try:
            return cls(**valid_data)
        except Exception as e:
            logger.error(f"Error creating {cls.__name__} from dict: {str(e)}")
            raise ValueError(f"Could not create {cls.__name__} from data: {str(e)}")
    
    @classmethod
    def get_columns(cls) -> List[str]:
        """
        Get a list of column names for this model.
        
        Returns:
            List of column names
        """
        return [prop.key for prop in class_mapper(cls).iterate_properties
                if isinstance(prop, ColumnProperty)]
    
    def update_from_dict(self, data: Dict[str, Any], 
                        allowed_fields: Optional[Set[str]] = None) -> bool:
        """
        Update model attributes from a dictionary.
        
        Args:
            data: Dictionary of attributes to update
            allowed_fields: Set of field names that are allowed to be updated,
                           if None, all fields can be updated except id, created_at
                           
        Returns:
            True if any fields were updated, False otherwise
            
        Raises:
            ValueError: If attempt to update a non-allowed field
        """
        # Default fields to exclude from updates
        default_exclude = {'id', 'created_at'}
        
        # Get column names
        columns = set(self.get_columns())
        
        # Determine allowed fields
        if allowed_fields is None:
            allowed_fields = columns - default_exclude
            
        # Track if anything was updated
        updated = False
        
        # Update fields
        for key, value in data.items():
            # Skip non-existent columns
            if key not in columns:
                continue
                
            # Check if field is allowed
            if key not in allowed_fields:
                raise ValueError(f"Cannot update field '{key}': not allowed")
                
            # Update if value is different
            current_value = getattr(self, key)
            if current_value != value:
                setattr(self, key, value)
                updated = True
                
        return updated


class EnumBase(str, Enum):
    """
    Base class for string enumerations to be used with SQLAlchemy.
    
    This allows enum values to be used directly in ORM queries
    and ensures consistent serialization to/from the database.
    
    The default implementation generates uppercase values from enum names.
    
    Example:
        class Status(EnumBase):
            ACTIVE = auto()
            INACTIVE = auto()
            
        # Results in Status.ACTIVE.value == "ACTIVE"
    """
    
    def _generate_next_value_(name, start, count, last_values):
        """Generate enum values as uppercase of the enum name."""
        return name.upper()
    
    def __str__(self) -> str:
        """String representation is just the value."""
        return self.value
        
    @classmethod
    def from_string(cls, value: str) -> 'EnumBase':
        """
        Convert a string to the corresponding enum value.
        
        Args:
            value: String value to convert
            
        Returns:
            Enum value
            
        Raises:
            ValueError: If value is not valid for this enum
        """
        try:
            # Case-insensitive search
            for member in cls:
                if member.value.upper() == value.upper():
                    return member
            # Not found
            raise ValueError(f"'{value}' is not a valid value for {cls.__name__}")
        except Exception as e:
            logger.error(f"Error converting string to {cls.__name__}: {str(e)}")
            raise ValueError(f"Invalid value '{value}' for {cls.__name__}")
    
    @classmethod
    def values(cls) -> List[str]:
        """
        Get a list of all valid values for this enum.
        
        Returns:
            List of valid enum values
        """
        return [member.value for member in cls]
    
    @classmethod
    def is_valid(cls, value: str) -> bool:
        """
        Check if a string is a valid value for this enum.
        
        Args:
            value: String value to check
            
        Returns:
            True if valid, False otherwise
        """
        try:
            cls.from_string(value)
            return True
        except ValueError:
            return False 