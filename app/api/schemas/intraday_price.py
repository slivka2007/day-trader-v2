"""Intraday price model schemas.

This module contains schemas for the StockIntradayPrice model, providing
serialization, deserialization, and validation functionality for API operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

from marshmallow import (
    ValidationError,
    fields,
    post_load,
    validate,
    validates,
    validates_schema,
)
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from app.api.schemas import Schema
from app.models import IntradayInterval, PriceSource, StockIntradayPrice
from app.utils.current_datetime import get_current_datetime
from app.utils.errors import StockPriceError

# Constants for intraday price validation
DEFAULT_INTRADAY_INTERVAL: str = "1m"
DEFAULT_INTRADAY_PERIOD: str = "1d"
VALID_INTRADAY_INTERVALS: list[str] = [
    "1m",
    "2m",
    "5m",
    "15m",
    "30m",
    "60m",
    "90m",
    "1h",
]
VALID_INTRADAY_PERIODS: list[str] = ["1d", "5d", "1mo", "3mo"]


# Base price schema with common price validations
class BasePriceSchema(Schema):
    """Base schema with common price validations."""

    @validates("high_price")
    def validate_high_price(self, value: float) -> float:
        """Validate high price value is non-negative."""
        if value is not None and value < 0:
            raise ValidationError(StockPriceError.NEGATIVE_PRICE)
        return value

    @validates("low_price")
    def validate_low_price(self, value: float) -> float:
        """Validate low price value is non-negative."""
        if value is not None and value < 0:
            raise ValidationError(StockPriceError.NEGATIVE_PRICE)
        return value

    @validates("open_price")
    def validate_open_price(self, value: float) -> float:
        """Validate open price value is non-negative."""
        if value is not None and value < 0:
            raise ValidationError(StockPriceError.NEGATIVE_PRICE)
        return value

    @validates("close_price")
    def validate_close_price(self, value: float) -> float:
        """Validate close price value is non-negative."""
        if value is not None and value < 0:
            raise ValidationError(StockPriceError.NEGATIVE_PRICE)
        return value


# Schema for serializing StockIntradayPrice models
class StockIntradayPriceSchema(SQLAlchemyAutoSchema):
    """Schema for serializing/deserializing StockIntradayPrice models."""

    class Meta:
        """Metadata options for the schema."""

        model = StockIntradayPrice
        include_relationships: bool = False
        load_instance: bool = True
        exclude: tuple[str, ...] = ("created_at", "updated_at")

    # Add computed properties
    change: fields.Float = fields.Float(dump_only=True)
    change_percent: fields.Float = fields.Float(dump_only=True)
    is_real_data: fields.Boolean = fields.Boolean(dump_only=True)
    is_delayed: fields.Boolean = fields.Boolean(dump_only=True)
    is_real_time: fields.Boolean = fields.Boolean(dump_only=True)

    # Add stock symbol to make API responses more informative
    stock_symbol: fields.Method = fields.Method("get_stock_symbol", dump_only=True)
    # Ensure stock_id is always included
    stock_id: fields.Integer = fields.Integer(dump_only=True)

    def get_stock_symbol(self, obj: StockIntradayPrice) -> str | None:
        """Get the stock symbol from the related stock."""
        return obj.stock.symbol if obj.stock else None

    @validates("interval")
    def validate_interval(self, value: int) -> None:
        """Validate the interval value."""
        if not IntradayInterval.is_valid_interval(value):
            raise ValidationError(
                StockPriceError.INVALID_INTERVAL.format(key="interval", value=value),
            )

    @validates("source")
    def validate_source(self, value: str) -> None:
        """Validate the source value."""
        if not PriceSource.is_valid(value):
            raise ValidationError(
                StockPriceError.INVALID_SOURCE.format(key="source", value=value),
            )


# Schema for creating/updating intraday price data
class StockIntradayPriceInputSchema(BasePriceSchema):
    """Schema for creating or updating a StockIntradayPrice."""

    timestamp: fields.DateTime = fields.DateTime(required=True)
    stock_id: fields.Integer = fields.Integer(required=True)
    interval: fields.Integer = fields.Integer(
        validate=validate.OneOf(IntradayInterval.valid_values()),
        dump_default=IntradayInterval.ONE_MINUTE.value,
    )
    open_price: fields.Float = fields.Float(
        allow_none=True,
        validate=validate.Range(min=0),
    )
    high_price: fields.Float = fields.Float(
        allow_none=True,
        validate=validate.Range(min=0),
    )
    low_price: fields.Float = fields.Float(
        allow_none=True,
        validate=validate.Range(min=0),
    )
    close_price: fields.Float = fields.Float(
        allow_none=True,
        validate=validate.Range(min=0),
    )
    volume: fields.Integer = fields.Integer(
        allow_none=True,
        validate=validate.Range(min=0),
    )
    source: fields.String = fields.String(
        validate=validate.OneOf([source.value for source in PriceSource]),
        dump_default=PriceSource.DELAYED.value,
    )

    @validates("timestamp")
    def validate_timestamp(self, timestamp: datetime) -> None:
        """Validate timestamp."""
        current_time = get_current_datetime()

        # Normalize timezone awareness for comparison
        if timestamp.tzinfo is not None and current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timestamp.tzinfo)
        elif timestamp.tzinfo is None and current_time.tzinfo is not None:
            timestamp = timestamp.replace(tzinfo=current_time.tzinfo)

        if timestamp > current_time:
            raise ValidationError(
                StockPriceError.FUTURE_TIMESTAMP.format(
                    key="timestamp",
                    value=timestamp,
                ),
            )

    @post_load
    def make_intraday_price(
        self,
        data: dict,
        **_kwargs: object,
    ) -> StockIntradayPrice:
        """Create a StockIntradayPrice instance from validated data."""
        return StockIntradayPrice.from_dict(data)


# Schema for confirming deletion of an intraday price
class StockIntradayPriceDeleteSchema(Schema):
    """Schema for confirming deletion of a StockIntradayPrice."""

    confirm: fields.Boolean = fields.Boolean(required=True)
    price_id: fields.Integer = fields.Integer(required=True)

    @validates_schema
    def validate_deletion(self, data: dict, **_kwargs: object) -> None:
        """Validate deletion confirmation and check for dependencies."""
        if not data.get("confirm"):
            raise ValidationError(StockPriceError.CONFIRM_DELETION)


# Schema for bulk importing intraday prices
class StockIntradayPriceBulkSchema(Schema):
    """Schema for bulk importing intraday prices."""

    stock_id: fields.Integer = fields.Integer(required=True)
    interval: fields.String = fields.String(
        validate=validate.OneOf(VALID_INTRADAY_INTERVALS),
        dump_default=DEFAULT_INTRADAY_INTERVAL,
    )
    period: fields.String = fields.String(
        validate=validate.OneOf(VALID_INTRADAY_PERIODS),
        dump_default=DEFAULT_INTRADAY_PERIOD,
    )


# Create instances for easy importing
intraday_price_schema = StockIntradayPriceSchema()
intraday_prices_schema = StockIntradayPriceSchema(many=True)
intraday_price_input_schema = StockIntradayPriceInputSchema()
intraday_price_delete_schema = StockIntradayPriceDeleteSchema()
intraday_price_bulk_schema = StockIntradayPriceBulkSchema()
