"""Daily Price model schemas.

This module contains the schemas for the StockDailyPrice model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date

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
from app.models import PriceSource, StockDailyPrice
from app.utils.current_datetime import get_current_date
from app.utils.errors import StockPriceError


# Base price schema with common validations
class BaseDailyPriceSchema(Schema):
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


# Daily price schema for serialization
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
    trading_range: fields.Float = fields.Float(dump_only=True)
    trading_range_percent: fields.Float = fields.Float(dump_only=True)
    is_real_data: fields.Boolean = fields.Boolean(dump_only=True)

    # Add stock symbol to make API responses more informative
    stock_symbol: fields.Method = fields.Method("get_stock_symbol", dump_only=True)

    def get_stock_symbol(self, obj: StockDailyPrice) -> str | None:
        """Get the stock symbol from the related stock."""
        return obj.stock.symbol if obj.stock else None

    @validates("source")
    def validate_source(self, value: str) -> None:
        """Validate the source value."""
        if not PriceSource.is_valid(value):
            raise ValidationError(StockPriceError.INVALID_SOURCE.format(value=value))


# Schema for creating/updating a daily price
class DailyPriceInputSchema(BaseDailyPriceSchema):
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
        dump_default=PriceSource.HISTORICAL.value,
    )

    @validates("price_date")
    def validate_price_date(self, price_date: date) -> None:
        """Validate price date."""
        if price_date > get_current_date():
            raise ValidationError(StockPriceError.FUTURE_DATE.format(value=price_date))

    @post_load
    def make_daily_price(self, data: dict) -> StockDailyPrice:
        """Create a StockDailyPrice instance from validated data."""
        return StockDailyPrice.from_dict(data)


# Schema for deleting a daily price
class DailyPriceDeleteSchema(Schema):
    """Schema for confirming daily price deletion."""

    confirm: fields.Boolean = fields.Boolean(required=True)
    price_id: fields.Integer = fields.Integer(required=True)

    @validates_schema
    def validate_deletion(self, data: dict) -> None:
        """Validate deletion confirmation."""
        if not data.get("confirm"):
            raise ValidationError(StockPriceError.CONFIRM_DELETION)


# Schema for bulk operations
class DailyPriceBulkSchema(Schema):
    """Schema for bulk price operations."""

    stock_id: fields.Integer = fields.Integer(required=True)
    period: fields.String = fields.String(
        validate=validate.OneOf(
            [
                "1mo",
                "3mo",
                "6mo",
                "1y",
                "2y",
                "5y",
                "10y",
                "ytd",
                "max",
            ],
        ),
        dump_default="1y",
    )


# Create instances for easy importing
daily_price_schema = StockDailyPriceSchema()
daily_prices_schema = StockDailyPriceSchema(many=True)
daily_price_input_schema = DailyPriceInputSchema()
daily_price_delete_schema = DailyPriceDeleteSchema()
daily_price_bulk_schema = DailyPriceBulkSchema()
