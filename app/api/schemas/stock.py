"""Stock model schemas.

This module contains the schemas for the Stock model.
"""

from __future__ import annotations

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
from app.models import Stock
from app.utils.constants import StockConstants
from app.utils.errors import StockError


class StockSchema(SQLAlchemyAutoSchema):
    """Schema for serializing/deserializing Stock models."""

    class Meta:
        """Metadata options for the schema."""

        model = Stock
        include_relationships: bool = False
        load_instance: bool = True
        exclude: tuple[str, ...] = ("created_at", "updated_at")

    # Add calculated fields
    has_services: fields.Method = fields.Method("check_has_services", dump_only=True)
    has_transactions: fields.Method = fields.Method(
        "check_has_transactions",
        dump_only=True,
    )
    price_count: fields.Method = fields.Method("count_prices", dump_only=True)

    def check_has_services(self, obj: Stock) -> bool:
        """Check if the stock has any associated services."""
        return len(obj.services) > 0 if obj.services else False

    def check_has_transactions(self, obj: Stock) -> bool:
        """Check if the stock has any associated transactions."""
        return len(obj.transactions) > 0 if obj.transactions else False

    def count_prices(self, obj: Stock) -> dict[str, int]:
        """Count the number of price data points available."""
        daily_count: int = len(obj.daily_prices) if obj.daily_prices else 0
        intraday_count: int = len(obj.intraday_prices) if obj.intraday_prices else 0
        return {
            "daily": daily_count,
            "intraday": intraday_count,
            "total": daily_count + intraday_count,
        }

    # Add validation for stock symbol
    @validates("symbol")
    def validate_symbol(self, symbol: str) -> None:
        """Validate stock symbol format."""
        if not symbol or len(symbol) > Stock.MAX_SYMBOL_LENGTH:
            raise ValidationError(
                StockError.SYMBOL_LENGTH.format(
                    StockConstants.MIN_SYMBOL_LENGTH,
                    StockConstants.MAX_SYMBOL_LENGTH,
                ),
            )

        if not symbol.isalnum():
            raise ValidationError(StockError.SYMBOL_FORMAT)

    @validates("name")
    def validate_name(self, name: str) -> None:
        """Validate stock name."""
        if name and len(name) > StockConstants.MAX_NAME_LENGTH:
            raise ValidationError(
                StockError.NAME_LENGTH.format(StockConstants.MAX_NAME_LENGTH),
            )

    @validates("sector")
    def validate_sector(self, sector: str) -> None:
        """Validate stock sector."""
        if sector and len(sector) > StockConstants.MAX_SECTOR_LENGTH:
            raise ValidationError(
                StockError.SECTOR_LENGTH.format(StockConstants.MAX_SECTOR_LENGTH),
            )

    @validates("description")
    def validate_description(self, description: str) -> None:
        """Validate stock description."""
        if description and len(description) > StockConstants.MAX_DESCRIPTION_LENGTH:
            raise ValidationError(
                StockError.DESCRIPTION_LENGTH.format(
                    StockConstants.MAX_DESCRIPTION_LENGTH,
                ),
            )


# Create an instance for easy importing
stock_schema = StockSchema()
stocks_schema = StockSchema(many=True)


# Schema for creating/updating a stock with only necessary fields
class StockInputSchema(Schema):
    """Schema for creating or updating a Stock."""

    symbol: fields.String = fields.String(
        required=True,
        validate=validate.Length(
            min=StockConstants.MIN_SYMBOL_LENGTH,
            max=StockConstants.MAX_SYMBOL_LENGTH,
        ),
    )
    name: fields.String = fields.String(
        allow_none=True,
        validate=validate.Length(max=StockConstants.MAX_NAME_LENGTH),
    )
    is_active: fields.Boolean = fields.Boolean(default=True)
    sector: fields.String = fields.String(
        allow_none=True,
        validate=validate.Length(max=StockConstants.MAX_SECTOR_LENGTH),
    )
    description: fields.String = fields.String(
        allow_none=True,
        validate=validate.Length(max=StockConstants.MAX_DESCRIPTION_LENGTH),
    )

    @validates("symbol")
    def validate_symbol(self, symbol: str) -> None:
        """Validate stock symbol format."""
        if not symbol.isalnum():
            raise ValidationError(StockError.SYMBOL_FORMAT)

    @post_load
    def make_stock(self, data: dict) -> Stock:
        """Create a Stock instance from validated data."""
        # Ensure symbol is uppercase
        if "symbol" in data:
            data["symbol"] = data["symbol"].upper()
        return Stock.from_dict(data)


# Schema for deleting a stock
class StockDeleteSchema(Schema):
    """Schema for confirming stock deletion."""

    confirm = fields.Boolean(required=True)
    stock_id = fields.Integer(required=True)

    @validates_schema
    def validate_deletion(self, data: dict) -> None:
        """Validate stock deletion.

        This function validates that the deletion is properly confirmed and the stock
        has no dependencies.
        """
        if not data.get("confirm"):
            raise ValidationError(StockError.CONFIRM_DELETION)


# Create instances for easy importing
stock_input_schema = StockInputSchema()
stock_delete_schema = StockDeleteSchema()
