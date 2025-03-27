"""
Base model classes and helpers for SQLAlchemy models.

This module defines the base classes and common functionality used by all models.
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, TypeVar
import json

from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base

# Create the base declarative class
DeclarativeBase = declarative_base()

# Type variable for models
ModelType = TypeVar('ModelType', bound='Base')

class Base(DeclarativeBase):
    """
    Abstract base class for all database models.
    
    This class provides common columns and functionality that should be present
    in all models, such as timestamps for creation and updates, as well as
    serialization methods for API responses.
    """
    __abstract__ = True
    
    # Primary key for all models
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Timestamps for record tracking
    created_at = Column(DateTime, default=datetime.now(datetime.UTC), nullable=False)
    updated_at = Column(DateTime, default=datetime.now(datetime.UTC), onupdate=datetime.now(datetime.UTC), nullable=False)
    
    def __repr__(self) -> str:
        """
        Default string representation of a model.
        
        Returns:
            String representation showing class name and ID
        """
        return f"<{self.__class__.__name__}(id={self.id})>"
        
    def to_dict(self, include_relationships: bool = False) -> Dict[str, Any]:
        """
        Convert the model instance to a dictionary.
        
        Args:
            include_relationships: Whether to include relationships in the output
            
        Returns:
            Dictionary representation of the model
        """
        result = {}
        
        # Add all column attributes
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            result[column.name] = self._serialize_value(value)
        
        # Add relationships if requested
        if include_relationships:
            for relationship in self.__mapper__.relationships:
                # Skip backrefs to avoid circular references
                if relationship.back_populates or relationship.backref:
                    continue
                    
                related_obj = getattr(self, relationship.key)
                
                if related_obj is None:
                    result[relationship.key] = None
                elif isinstance(related_obj, list):
                    result[relationship.key] = [
                        item.to_dict(include_relationships=False) 
                        for item in related_obj
                    ]
                else:
                    result[relationship.key] = related_obj.to_dict(include_relationships=False)
        
        return result
    
    def to_json(self, include_relationships: bool = False) -> str:
        """
        Convert the model instance to a JSON string.
        
        Args:
            include_relationships: Whether to include relationships in the output
            
        Returns:
            JSON string representation of the model
        """
        return json.dumps(self.to_dict(include_relationships=include_relationships))
    
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
        elif hasattr(value, 'to_dict') and callable(value.to_dict):
            return value.to_dict()
        return value
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Any:
        """
        Create a new instance from a dictionary.
        
        Args:
            data: Dictionary containing model data
            
        Returns:
            A new instance of the model
        """
        # Filter out keys that don't correspond to model columns
        valid_data = {
            k: v for k, v in data.items() 
            if k in cls.__table__.columns.keys()
        }
        
        return cls(**valid_data)


class EnumBase(str, Enum):
    """
    Base class for string enumerations to be used with SQLAlchemy.
    
    This allows enum values to be used directly in ORM queries
    and ensures consistent serialization to/from the database.
    """
    
    def _generate_next_value_(name, start, count, last_values):
        """Generate enum values as uppercase of the enum name."""
        return name.upper()
    
    def __str__(self) -> str:
        """String representation is just the value."""
        return self.value 