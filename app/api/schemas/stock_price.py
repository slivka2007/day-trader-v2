"""
Stock Price model schemas.
"""

from datetime import date, datetime, timedelta

from marshmallow import (
    ValidationError,
    fields,
    post_load,
    validate,
    validates,
    validates_schema,
)
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from sqlalchemy import select

from app.api.schemas import Schema
from app.models import PriceSource, StockDailyPrice, StockIntradayPrice
from app.services.session_manager import SessionManager
from app.utils.current_datetime import get_current_date, get_current_datetime


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
            raise ValidationError("High price cannot be less than low price")

        if high is not None and open_price is not None and high < open_price:
            raise ValidationError("High price cannot be less than open price")

        if high is not None and close_price is not None and high < close_price:
            raise ValidationError("High price cannot be less than close price")

        if low is not None and open_price is not None and low > open_price:
            raise ValidationError("Low price cannot be greater than open price")

        if low is not None and close_price is not None and low > close_price:
            raise ValidationError("Low price cannot be greater than close price")


# Daily price schemas
class StockDailyPriceSchema(SQLAlchemyAutoSchema):
    """Schema for serializing/deserializing StockDailyPrice models."""

    class Meta:
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
            valid_sources: list[str] = [str(s.value) for s in PriceSource]
            raise ValidationError(
                f"Invalid price source. Must be one of: {', '.join(valid_sources)}"
            )


# Create instances for easy importing
daily_price_schema = StockDailyPriceSchema()
daily_prices_schema = StockDailyPriceSchema(many=True)


# Schema for creating/updating a daily price
class StockDailyPriceInputSchema(BasePriceSchema):
    """Schema for creating or updating a StockDailyPrice."""

    price_date: fields.Date = fields.Date(required=True)
    open_price: fields.Float = fields.Float(
        allow_none=True, validate=validate.Range(min=0)
    )
    high_price: fields.Float = fields.Float(
        allow_none=True, validate=validate.Range(min=0)
    )
    low_price: fields.Float = fields.Float(
        allow_none=True, validate=validate.Range(min=0)
    )
    close_price = fields.Float(allow_none=True, validate=validate.Range(min=0))
    adj_close = fields.Float(allow_none=True, validate=validate.Range(min=0))
    volume = fields.Integer(allow_none=True, validate=validate.Range(min=0))
    source = fields.String(
        validate=validate.OneOf([source.value for source in PriceSource]),
        default=PriceSource.HISTORICAL.value,
    )

    @validates("price_date")
    def validate_price_date(self, price_date: date) -> None:
        """Validate price date."""
        if price_date > get_current_date():
            raise ValidationError("Price date cannot be in the future")

    @post_load
    def make_daily_price(self, data: dict, **kwargs) -> StockDailyPrice:
        """Create a StockDailyPrice instance from validated data."""
        return StockDailyPrice.from_dict(data)


# Schema for deleting a daily price
class StockDailyPriceDeleteSchema(Schema):
    """Schema for confirming daily price deletion."""

    confirm: fields.Boolean = fields.Boolean(required=True)
    price_id: fields.Integer = fields.Integer(required=True)

    @validates_schema
    def validate_deletion(self, data: dict, **kwargs) -> None:
        """Validate deletion confirmation and check for dependencies."""
        if not data.get("confirm"):
            raise ValidationError("Must confirm deletion by setting 'confirm' to true")

        # Verify the price record exists and can be deleted
        with SessionManager() as session:
            price: StockDailyPrice | None = session.execute(
                select(StockDailyPrice).where(StockDailyPrice.id == data["price_id"])
            ).scalar_one_or_none()
            if not price:
                raise ValidationError("Daily price record not found")

            # Check if this is recent data (within last 30 days)
            # Recent data is often used for analysis and should be protected
            thirty_days_ago: date = get_current_date() - timedelta(days=30)
            price_date: date | None = price.__dict__.get("price_date")
            if price_date is not None and price_date >= thirty_days_ago:
                raise ValidationError(
                    "Cannot delete recent price data (less than 30 days old). "
                    "This data may be in use for active analyses."
                )


# Intraday price schemas
class StockIntradayPriceSchema(SQLAlchemyAutoSchema):
    """Schema for serializing/deserializing StockIntradayPrice models."""

    class Meta:
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
        if value not in [1, 5, 15, 30, 60]:
            raise ValidationError("Interval must be one of: 1, 5, 15, 30, 60")

    @validates("source")
    def validate_source(self, value: str) -> None:
        """Validate the source value."""
        if not PriceSource.is_valid(value):
            valid_sources: list[str] = [str(s.value) for s in PriceSource]
            raise ValidationError(
                f"Invalid price source. Must be one of: {', '.join(valid_sources)}"
            )


# Create instances for easy importing
intraday_price_schema = StockIntradayPriceSchema()
intraday_prices_schema = StockIntradayPriceSchema(many=True)


# Schema for creating/updating an intraday price
class StockIntradayPriceInputSchema(BasePriceSchema):
    """Schema for creating or updating a StockIntradayPrice."""

    timestamp: fields.DateTime = fields.DateTime(required=True)
    interval: fields.Integer = fields.Integer(
        validate=validate.OneOf([1, 5, 15, 30, 60]), default=1
    )
    open_price: fields.Float = fields.Float(
        allow_none=True, validate=validate.Range(min=0)
    )
    high_price: fields.Float = fields.Float(
        allow_none=True, validate=validate.Range(min=0)
    )
    low_price: fields.Float = fields.Float(
        allow_none=True, validate=validate.Range(min=0)
    )
    close_price: fields.Float = fields.Float(
        allow_none=True, validate=validate.Range(min=0)
    )
    volume: fields.Integer = fields.Integer(
        allow_none=True, validate=validate.Range(min=0)
    )
    source: fields.String = fields.String(
        validate=validate.OneOf([source.value for source in PriceSource]),
        default=PriceSource.DELAYED.value,
    )

    @validates("timestamp")
    def validate_timestamp(self, timestamp: datetime) -> None:
        """Validate timestamp."""
        if timestamp > get_current_datetime():
            raise ValidationError("Timestamp cannot be in the future")

    @post_load
    def make_intraday_price(self, data: dict) -> StockIntradayPrice:
        """Create a StockIntradayPrice instance from validated data."""
        return StockIntradayPrice.from_dict(data)


# Schema for deleting an intraday price
class StockIntradayPriceDeleteSchema(Schema):
    """Schema for confirming intraday price deletion."""

    confirm = fields.Boolean(required=True)
    price_id = fields.Integer(required=True)

    @validates_schema
    def validate_deletion(self, data: dict) -> None:
        """Validate deletion confirmation and check for dependencies."""
        if not data.get("confirm"):
            raise ValidationError("Must confirm deletion by setting 'confirm' to true")

        # Verify the price record exists and can be deleted
        with SessionManager() as session:
            price: StockIntradayPrice | None = session.execute(
                select(StockIntradayPrice).where(
                    StockIntradayPrice.id == data["price_id"]
                )
            ).scalar_one_or_none()
            if not price:
                raise ValidationError("Intraday price record not found")

            # Check if this is recent data (within last 7 days)
            # Recent data is often used for analysis and should be protected
            seven_days_ago: date = get_current_date() - timedelta(days=7)
            timestamp: datetime | None = price.timestamp
            if timestamp is not None and timestamp.date() >= seven_days_ago:
                raise ValidationError(
                    "Cannot delete recent price data (less than 7 days old). "
                    "This data may be in use for active analyses."
                )


# Create instances for easy importing
daily_price_input_schema = StockDailyPriceInputSchema()
daily_price_delete_schema = StockDailyPriceDeleteSchema()
intraday_price_input_schema = StockIntradayPriceInputSchema()
intraday_price_delete_schema = StockIntradayPriceDeleteSchema()
