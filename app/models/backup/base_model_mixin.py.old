from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional
import json

class BaseModelMixin:
    """
    Mixin class that adds JSON serialization capabilities to SQLAlchemy models.
    
    This class is designed to be used alongside SQLAlchemy models to provide
    standardized methods for converting models to dictionaries and JSON
    for API responses.
    """
    
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