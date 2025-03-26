"""
Marshmallow schemas for API serialization and validation.

This package contains schemas used to validate and serialize/deserialize
data between the API and the database models.
"""
from marshmallow import Schema, fields, validate, ValidationError
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

# Define a pagination schema for consistent pagination response
class PaginationSchema(Schema):
    """Schema for pagination metadata."""
    page = fields.Integer(required=True)
    page_size = fields.Integer(required=True)
    total_items = fields.Integer(required=True)
    total_pages = fields.Integer(required=True)
    has_next = fields.Boolean(required=True)
    has_prev = fields.Boolean(required=True)

# Define a paginated response schema
class PaginatedResponseSchema(Schema):
    """Schema for paginated response containing items and pagination metadata."""
    items = fields.List(fields.Raw(), required=True)
    pagination = fields.Nested(PaginationSchema, required=True)

__all__ = [
    'Schema', 
    'fields', 
    'validate', 
    'ValidationError',
    'SQLAlchemyAutoSchema',
    'auto_field',
    'PaginationSchema',
    'PaginatedResponseSchema',
] 