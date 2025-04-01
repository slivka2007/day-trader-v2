"""
Stock model schemas.
"""

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
from app.models import Stock


class StockSchema(SQLAlchemyAutoSchema):
    """Schema for serializing/deserializing Stock models."""

    class Meta:
        model = Stock
        include_relationships: bool = False
        load_instance: bool = True
        exclude: tuple[str, ...] = ("created_at", "updated_at")

    # Add calculated fields
    has_services: fields.Method = fields.Method("check_has_services", dump_only=True)
    has_transactions: fields.Method = fields.Method(
        "check_has_transactions", dump_only=True
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
        if not symbol or len(symbol) > 10:
            raise ValidationError("Stock symbol must be 1-10 characters")

        if not symbol.isalnum():
            raise ValidationError("Stock symbol must contain only letters and numbers")

    @validates("name")
    def validate_name(self, name: str) -> None:
        """Validate stock name."""
        if name and len(name) > 200:
            raise ValidationError("Stock name must be 200 characters or less")

    @validates("sector")
    def validate_sector(self, sector: str) -> None:
        """Validate stock sector."""
        if sector and len(sector) > 100:
            raise ValidationError("Stock sector must be 100 characters or less")

    @validates("description")
    def validate_description(self, description: str) -> None:
        """Validate stock description."""
        if description and len(description) > 1000:
            raise ValidationError("Stock description must be 1000 characters or less")


# Create an instance for easy importing
stock_schema = StockSchema()
stocks_schema = StockSchema(many=True)


# Schema for creating/updating a stock with only necessary fields
class StockInputSchema(Schema):
    """Schema for creating or updating a Stock."""

    symbol: fields.String = fields.String(
        required=True, validate=validate.Length(min=1, max=10)
    )
    name: fields.String = fields.String(
        allow_none=True, validate=validate.Length(max=200)
    )
    is_active: fields.Boolean = fields.Boolean(default=True)
    sector: fields.String = fields.String(
        allow_none=True, validate=validate.Length(max=100)
    )
    description: fields.String = fields.String(
        allow_none=True, validate=validate.Length(max=1000)
    )

    @validates("symbol")
    def validate_symbol(self, symbol: str) -> None:
        """Validate stock symbol format."""
        if not symbol.isalnum():
            raise ValidationError("Stock symbol must contain only letters and numbers")

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
        """
        Validate that deletion is properly confirmed and stock has no dependencies.
        """
        if not data.get("confirm"):
            raise ValidationError("Must confirm deletion by setting 'confirm' to true")

        # Check if stock has associated services or transactions
        from app.models import Stock, TradingService, TradingTransaction
        from app.services.session_manager import SessionManager

        with SessionManager() as session:
            # Find the stock by ID
            stock: Stock | None = session.execute(
                select(Stock).where(Stock.id == data["stock_id"])
            ).scalar_one_or_none()
            if not stock:
                return  # Stock doesn't exist, let the resource handle this error

            # Check if any trading services use this stock
            services_count: int = session.execute(
                select(TradingService).where(TradingService.stock_id == stock.id)
            ).count()
            if services_count > 0:
                raise ValidationError(
                    f"Cannot delete stock '{stock.symbol}' because it is used by "
                    f"{services_count} trading service(s)"
                )

            # Check if any transactions are associated with this stock
            transactions_count: int = session.execute(
                select(TradingTransaction).where(
                    TradingTransaction.stock_id == stock.id
                )
            ).count()
            if transactions_count > 0:
                raise ValidationError(
                    f"Cannot delete stock '{stock.symbol}' because it has "
                    f"{transactions_count} associated transaction(s)"
                )


# Create instances for easy importing
stock_input_schema = StockInputSchema()
stock_delete_schema = StockDeleteSchema()
