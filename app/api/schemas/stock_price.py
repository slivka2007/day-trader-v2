"""Stock Price model schemas.

This module contains the schemas for the StockPrice model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date, datetime

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
from app.models import (
    IntradayInterval,
    PriceSource,
    StockDailyPrice,
    StockIntradayPrice,
)
from app.utils.current_datetime import get_current_date, get_current_datetime
from app.utils.errors import StockPriceError


# Base price schema with common validations
class BasePriceSchema(Schema):
    """Base schema with common price validations."""

    @validates_schema
    def validate_price_data(self, data: dict) -> None:
        """Validate that price data is consistent."""
        high: float | None = data.get("high_price")
        low: float | None = data.get("low_price")
        open_price: float | None = data.get("open_price")
        close_price: float | None = data.get("close_price")

        if high is not None and low is not None and high < low:
            raise ValidationError(StockPriceError.HIGH_LOW_PRICE)

        if high is not None and open_price is not None and high < open_price:
            raise ValidationError(StockPriceError.HIGH_OPEN_PRICE)

        if high is not None and close_price is not None and high < close_price:
            raise ValidationError(StockPriceError.HIGH_CLOSE_PRICE)

        if low is not None and open_price is not None and low > open_price:
            raise ValidationError(StockPriceError.LOW_OPEN_PRICE)

        if low is not None and close_price is not None and low > close_price:
            raise ValidationError(StockPriceError.LOW_CLOSE_PRICE)


# Daily price schemas
class StockDailyPriceSchema(SQLAlchemyAutoSchema):
    """Schema for serializing/deserializing StockDailyPrice models."""

    class Meta:
        """Metadata options for the schema."""

        model = StockDailyPrice
        include_relationships: bool = False
        load_instance: bool = True
        exclude: tuple[str, ...] = ("created_at", "updated_at")

    # Add computed properties
    change: fields.Float = fields.Float(dump_only=True)
    change_percent: fields.Float = fields.Float(dump_only=True)

    # Add stock symbol to make API responses more informative
    stock_symbol: fields.Method = fields.Method("get_stock_symbol", dump_only=True)

    def get_stock_symbol(self, obj: StockDailyPrice) -> str | None:
        """Get the stock symbol from the related stock."""
        return obj.stock.symbol if obj.stock else None

    @validates("source")
    def validate_source(self, value: str) -> None:
        """Validate the source value."""
        if not PriceSource.is_valid(value):
            raise ValidationError(StockPriceError.INVALID_SOURCE.format(value))


# Create instances for easy importing
daily_price_schema = StockDailyPriceSchema()
daily_prices_schema = StockDailyPriceSchema(many=True)


# Schema for creating/updating a daily price
class StockDailyPriceInputSchema(BasePriceSchema):
    """Schema for creating or updating a StockDailyPrice."""

    price_date: fields.Date = fields.Date(required=True)
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
    adj_close: fields.Float = fields.Float(
        allow_none=True,
        validate=validate.Range(min=0),
    )
    volume: fields.Integer = fields.Integer(
        allow_none=True,
        validate=validate.Range(min=0),
    )
    source: fields.String = fields.String(
        validate=validate.OneOf([source.value for source in PriceSource]),
        default=PriceSource.HISTORICAL.value,
    )

    @validates("price_date")
    def validate_price_date(self, price_date: date) -> None:
        """Validate price date."""
        if price_date > get_current_date():
            raise ValidationError(StockPriceError.FUTURE_DATE.format(price_date))

    @post_load
    def make_daily_price(self, data: dict) -> StockDailyPrice:
        """Create a StockDailyPrice instance from validated data."""
        return StockDailyPrice.from_dict(data)


# Schema for deleting a daily price
class StockDailyPriceDeleteSchema(Schema):
    """Schema for confirming daily price deletion."""

    confirm: fields.Boolean = fields.Boolean(required=True)
    price_id: fields.Integer = fields.Integer(required=True)

    @validates_schema
    def validate_deletion(self, data: dict) -> None:
        """Validate deletion confirmation and check for dependencies."""
        if not data.get("confirm"):
            raise ValidationError(StockPriceError.CONFIRM_DELETION)


# Intraday price schemas
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

    # Add stock symbol to make API responses more informative
    stock_symbol: fields.Method = fields.Method("get_stock_symbol", dump_only=True)

    def get_stock_symbol(self, obj: StockIntradayPrice) -> str | None:
        """Get the stock symbol from the related stock."""
        return obj.stock.symbol if obj.stock else None

    @validates("interval")
    def validate_interval(self, value: int) -> None:
        """Validate the interval value."""
        if value not in IntradayInterval.valid_values():
            raise ValidationError(StockPriceError.INVALID_INTERVAL.format(value))

    @validates("source")
    def validate_source(self, value: str) -> None:
        """Validate the source value."""
        if not PriceSource.is_valid(value):
            raise ValidationError(StockPriceError.INVALID_SOURCE.format(value))


# Create instances for easy importing
intraday_price_schema = StockIntradayPriceSchema()
intraday_prices_schema = StockIntradayPriceSchema(many=True)


# Schema for creating/updating an intraday price
class StockIntradayPriceInputSchema(BasePriceSchema):
    """Schema for creating or updating a StockIntradayPrice."""

    timestamp: fields.DateTime = fields.DateTime(required=True)
    interval: fields.Integer = fields.Integer(
        validate=validate.OneOf(IntradayInterval.valid_values()),
        default=IntradayInterval.ONE_MINUTE.value,
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
        default=PriceSource.DELAYED.value,
    )

    @validates("timestamp")
    def validate_timestamp(self, timestamp: datetime) -> None:
        """Validate timestamp."""
        if timestamp > get_current_datetime():
            raise ValidationError(StockPriceError.FUTURE_TIMESTAMP.format(timestamp))

    @post_load
    def make_intraday_price(self, data: dict) -> StockIntradayPrice:
        """Create a StockIntradayPrice instance from validated data."""
        return StockIntradayPrice.from_dict(data)


# Schema for deleting an intraday price
class StockIntradayPriceDeleteSchema(Schema):
    """Schema for confirming intraday price deletion."""

    confirm: fields.Boolean = fields.Boolean(required=True)
    price_id: fields.Integer = fields.Integer(required=True)

    @validates_schema
    def validate_deletion(self, data: dict) -> None:
        """Validate deletion confirmation and check for dependencies."""
        if not data.get("confirm"):
            raise ValidationError(StockPriceError.CONFIRM_DELETION)


# Create instances for easy importing
daily_price_input_schema = StockDailyPriceInputSchema()
daily_price_delete_schema = StockDailyPriceDeleteSchema()
intraday_price_input_schema = StockIntradayPriceInputSchema()
intraday_price_delete_schema = StockIntradayPriceDeleteSchema()
