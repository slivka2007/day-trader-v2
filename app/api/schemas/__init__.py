"""Marshmallow schemas for API serialization and validation.

This package contains schemas used to validate and serialize/deserialize
data between the API and the database models.
"""

from marshmallow import Schema, ValidationError, fields, validate
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

# Import all schemas for easy access
from app.api.schemas.daily_price import (
    daily_price_bulk_schema,
    daily_price_delete_schema,
    daily_price_input_schema,
    daily_price_schema,
    daily_prices_schema,
)
from app.api.schemas.intraday_price import (
    intraday_price_bulk_schema,
    intraday_price_delete_schema,
    intraday_price_input_schema,
    intraday_price_schema,
    intraday_prices_schema,
)
from app.api.schemas.stock import (
    stock_delete_schema,
    stock_input_schema,
    stock_schema,
    stocks_schema,
)
from app.api.schemas.trading_service import (
    decision_response_schema,
    service_action_schema,
    service_create_schema,
    service_delete_schema,
    service_schema,
    service_update_schema,
    services_schema,
)
from app.api.schemas.trading_transaction import (
    transaction_cancel_schema,
    transaction_complete_schema,
    transaction_create_schema,
    transaction_delete_schema,
    transaction_schema,
    transactions_schema,
)
from app.api.schemas.user import (
    password_change_schema,
    user_create_schema,
    user_delete_schema,
    user_login_schema,
    user_schema,
    user_update_schema,
    users_schema,
)


# Define a pagination schema for consistent pagination response
class PaginationSchema(Schema):
    """Schema for pagination metadata."""

    page: fields.Integer = fields.Integer(required=True)
    page_size: fields.Integer = fields.Integer(required=True)
    total_items: fields.Integer = fields.Integer(required=True)
    total_pages: fields.Integer = fields.Integer(required=True)
    has_next: fields.Boolean = fields.Boolean(required=True)
    has_prev: fields.Boolean = fields.Boolean(required=True)


# Define a paginated response schema
class PaginatedResponseSchema(Schema):
    """Schema for paginated response containing items and pagination metadata."""

    items: fields.List = fields.List(fields.Raw(), required=True)
    pagination: fields.Nested = fields.Nested(
        PaginationSchema,
        required=True,
    )


__all__: list[str] = [
    "PaginatedResponseSchema",
    "PaginationSchema",
    "SQLAlchemyAutoSchema",
    "Schema",
    "ValidationError",
    "auto_field",
    "daily_price_bulk_schema",
    "daily_price_delete_schema",
    "daily_price_input_schema",
    "daily_price_schema",
    "daily_prices_schema",
    "decision_response_schema",
    "fields",
    "intraday_price_bulk_schema",
    "intraday_price_delete_schema",
    "intraday_price_input_schema",
    "intraday_price_schema",
    "intraday_prices_schema",
    "password_change_schema",
    "service_action_schema",
    "service_create_schema",
    "service_delete_schema",
    "service_schema",
    "service_update_schema",
    "services_schema",
    "stock_delete_schema",
    "stock_input_schema",
    "stock_schema",
    "stocks_schema",
    "transaction_cancel_schema",
    "transaction_complete_schema",
    "transaction_create_schema",
    "transaction_delete_schema",
    "transaction_schema",
    "transactions_schema",
    "user_create_schema",
    "user_delete_schema",
    "user_login_schema",
    "user_schema",
    "user_update_schema",
    "users_schema",
    "validate",
]
