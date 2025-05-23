"""Base model classes and helpers for SQLAlchemy models.

This module defines the base classes and common functionality used by all models.
It provides foundation classes with standardized behavior for timestamps, serialization,
validation, and error handling.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.orm import ColumnProperty, class_mapper, declarative_base

from app.utils.current_datetime import get_current_datetime
from app.utils.errors import BaseModelError, ValidationError

# Set up logging
logger: logging.Logger = logging.getLogger(__name__)

# Create the base declarative class
DeclarativeBase: any = declarative_base()


class Base(DeclarativeBase):
    """Abstract base class for all database models.

    This class provides common columns and functionality that should be present
    in all models, such as timestamps for creation and updates, serialization
    methods for API responses, and validation utilities.

    Attributes:
        id: Primary key for all models
        created_at: Timestamp when the record was created
        updated_at: Timestamp when the record was last updated

    """

    #
    # SQLAlchemy configuration
    #

    __abstract__ = True

    # Primary key for all models
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Timestamps for record tracking
    created_at = Column(DateTime, default=get_current_datetime, nullable=False)
    updated_at = Column(
        DateTime,
        default=get_current_datetime,
        onupdate=get_current_datetime,
        nullable=False,
    )

    #
    # Magic methods
    #

    def __repr__(self) -> str:
        """Return string representation of a model.

        Returns:
            String representation showing class name and ID

        """
        return (
            f"<{self.__class__.__name__}(id={self.id}, "
            f"created_at={self.created_at}, updated_at={self.updated_at})>"
        )

    def __str__(self) -> str:
        """Return a user-friendly string representation of a model.

        Returns:
            Human-readable string representation focusing on the model's identity

        """
        return f"{self.__class__.__name__} #{self.id}"

    #
    # Serialization methods
    #

    def to_dict(
        self,
        *,
        include_relationships: bool = False,
        exclude: set[str] | None = None,
    ) -> dict[str, any]:
        """Convert the model instance to a dictionary.

        Args:
            include_relationships: Whether to include relationships in the output
            exclude: Set of attribute names to exclude from the result

        Returns:
            Dictionary representation of the model

        """
        if exclude is None:
            exclude = set()

        result: dict[str, any] = {}

        # Add all column attributes
        for column in self.__table__.columns:
            if column.name in exclude:
                continue
            result[column.name] = self._serialize_value(getattr(self, column.name))

        # Add relationships if requested
        if include_relationships:
            for relationship in self.__mapper__.relationships:
                # Skip if in exclude list
                if relationship.key in exclude:
                    continue

                # Skip backrefs to avoid circular references
                if relationship.back_populates or relationship.backref:
                    continue

                related_obj: any = getattr(self, relationship.key)

                if related_obj is None:
                    result[relationship.key] = None
                elif isinstance(related_obj, list):
                    result[relationship.key] = [
                        item.to_dict(include_relationships=False, exclude=exclude)
                        for item in related_obj
                    ]
                else:
                    result[relationship.key] = related_obj.to_dict(
                        include_relationships=False,
                        exclude=exclude,
                    )

        return result

    def to_json(
        self,
        *,
        include_relationships: bool = False,
        exclude: set[str] | None = None,
    ) -> str:
        """Convert the model instance to a JSON string.

        Args:
            include_relationships: Whether to include relationships in the output
            exclude: Set of attribute names to exclude from the result

        Returns:
            JSON string representation of the model

        """
        try:
            return json.dumps(
                self.to_dict(
                    include_relationships=include_relationships,
                    exclude=exclude,
                ),
            )
        except (TypeError, ValueError, OverflowError):
            logger.exception(
                BaseModelError.SERIALIZATION_ERROR,
                self.__class__.__name__,
            )
            return json.dumps({"error": "Serialization error", "id": self.id})

    @staticmethod
    def _serialize_value(value: any) -> any:
        """Serialize a value for JSON compatibility.

        Args:
            value: The value to serialize

        Returns:
            JSON-compatible representation of the value

        """
        if value is None:
            return None

        if isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, (Decimal, float)):
            return float(value)

        if isinstance(value, Enum):
            return value.value

        if hasattr(value, "to_dict") and callable(value.to_dict):
            return value.to_dict()

        return value

    #
    # Instance methods
    #

    def update_from_dict(
        self,
        data: dict[str, any],
        allowed_fields: set[str] | None = None,
    ) -> bool:
        """Update model attributes from a dictionary.

        Args:
            data: Dictionary of attributes to update
            allowed_fields: Set of field names that are allowed to be updated,
                           if None, all fields can be updated except id, created_at

        Returns:
            True if any fields were updated, False otherwise

        Raises:
            ValidationError: If attempt to update a non-allowed field

        """
        # Default fields to exclude from updates
        default_exclude: set[str] = {"id", "created_at"}

        # Get column names
        columns: set[str] = set(self.get_columns())

        # Determine allowed fields
        if allowed_fields is None:
            allowed_fields = columns - default_exclude

        # Track if anything was updated
        updated: bool = False

        # Track validation errors
        validation_errors: dict[str, str] = {}

        # Update fields
        for key, value in data.items():
            # Skip non-existent columns
            if key not in columns:
                continue

            # Check if field is allowed
            if key not in allowed_fields:
                error_msg: str = BaseModelError.UPDATE_FIELD_ERROR.format(key)
                validation_errors[key] = error_msg
                continue

            # Update if value is different
            current_value: any = getattr(self, key)
            if current_value != value:
                setattr(self, key, value)
                updated = True

        # Raise exception if there were validation errors
        if validation_errors:
            raise ValidationError(
                BaseModelError.MULTIPLE_FIELDS_ERROR,
                errors=validation_errors,
            )

        return updated

    #
    # Class methods
    #

    @classmethod
    def from_dict(cls, data: dict[str, any], *, ignore_unknown: bool = True) -> any:
        """Create a new instance from a dictionary.

        Args:
            data: Dictionary containing model data
            ignore_unknown: Whether to ignore keys that don't match model columns

        Returns:
            A new instance of the model

        Raises:
            ValidationError: If required data is missing or invalid and ignore_unknown
            is False

        """
        # Get column names
        columns: set[str] = {c.key for c in class_mapper(cls).columns}

        # Filter data to only include valid columns
        valid_data: dict[str, any] = {}
        for key, value in data.items():
            if key in columns:
                valid_data[key] = value
            elif not ignore_unknown:
                error_msg: str = BaseModelError.UNKNOWN_COLUMN_ERROR.format(
                    key,
                    cls.__name__,
                )
                errors: dict[str, str] = {key: error_msg}
                raise ValidationError(error_msg, errors=errors)

        try:
            return cls(**valid_data)
        except Exception as e:
            logger.exception("Error creating %s from dict", cls.__name__)
            error_msg = BaseModelError.CREATE_FROM_DICT_ERROR.format(
                cls.__name__,
                str(e),
            )
            errors: dict[str, str] = {"data": error_msg}
            raise ValidationError(error_msg, errors=errors) from e

    @classmethod
    def get_columns(cls) -> list[str]:
        """Get a list of column names for this model.

        Returns:
            List of column names

        """
        return [
            prop.key
            for prop in class_mapper(cls).iterate_properties
            if isinstance(prop, ColumnProperty)
        ]
