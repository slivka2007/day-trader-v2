"""Trading Transaction model schemas.

This module contains the schemas for the TradingTransaction model.
"""

from typing import Literal

from marshmallow import ValidationError, fields, validate, validates, validates_schema
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from app.api.schemas import Schema
from app.models import TradingTransaction, TransactionState
from app.utils.constants import StockConstants
from app.utils.errors import StockError, TransactionError


class TradingTransactionSchema(SQLAlchemyAutoSchema):
    """Schema for serializing/deserializing TradingTransaction models.

    This schema is used to serialize and deserialize TradingTransaction models.
    """

    class Meta:
        """Metadata options for the TradingTransaction schema."""

        model = TradingTransaction
        include_relationships = False
        load_instance = True
        exclude: tuple[Literal["created_at"], Literal["updated_at"]] = (
            "created_at",
            "updated_at",
        )

    # Add custom fields and validation
    is_complete: fields.Boolean = fields.Boolean(dump_only=True)
    is_profitable: fields.Boolean = fields.Boolean(dump_only=True)

    # Add calculated fields that may be useful in the UI
    total_cost: fields.Method = fields.Method("calculate_total_cost", dump_only=True)
    total_revenue: fields.Method = fields.Method(
        "calculate_total_revenue",
        dump_only=True,
    )
    profit_loss_pct: fields.Method = fields.Method(
        "calculate_profit_loss_pct",
        dump_only=True,
    )

    def calculate_total_cost(self, obj: TradingTransaction) -> float:
        """Calculate the total cost of the purchase."""
        if obj.purchase_price and obj.shares:
            return float(obj.purchase_price * obj.shares)
        return 0.0

    def calculate_total_revenue(self, obj: TradingTransaction) -> float:
        """Calculate the total revenue from the sale."""
        if obj.sale_price and obj.shares:
            return float(obj.sale_price * obj.shares)
        return 0.0

    def calculate_profit_loss_pct(self, obj: TradingTransaction) -> float:
        """Calculate the profit/loss as a percentage."""
        if obj.purchase_price and obj.sale_price and obj.purchase_price > 0:
            return float(
                ((obj.sale_price - obj.purchase_price) / obj.purchase_price) * 100,
            )
        return 0.0

    @validates("purchase_price")
    def validate_purchase_price(self, value: float) -> None:
        """Validate purchase price is positive."""
        if value <= 0:
            raise ValidationError(TransactionError.PRICE_POSITIVE)

    @validates("shares")
    def validate_shares(self, value: float) -> None:
        """Validate shares is positive."""
        if value <= 0:
            raise ValidationError(TransactionError.SHARES_POSITIVE)

    @validates("sale_price")
    def validate_sale_price(self, value: float) -> None:
        """Validate sale price is positive."""
        if value is not None and value <= 0:
            raise ValidationError(TransactionError.PRICE_POSITIVE)

    @validates("stock_symbol")
    def validate_stock_symbol(self, value: str) -> None:
        """Validate stock symbol."""
        if not value or len(value) > StockConstants.MAX_SYMBOL_LENGTH:
            raise ValidationError(StockError.SYMBOL_LENGTH)

        if not value.isalnum():
            raise ValidationError(StockError.SYMBOL_FORMAT)

    @validates("state")
    def validate_state(self, value: str) -> None:
        """Validate transaction state."""
        if value and not TransactionState.is_valid(value):
            raise ValidationError(TransactionError.INVALID_STATE.format(value))


# Create instances for easy importing
transaction_schema = TradingTransactionSchema()
transactions_schema = TradingTransactionSchema(many=True)


# Schema for completing a transaction (selling shares)
class TransactionCompleteSchema(Schema):
    """Schema for completing (selling) a transaction."""

    sale_price: fields.Float = fields.Float(
        required=True,
        validate=validate.Range(min=0.01),
    )

    @validates("sale_price")
    def validate_sale_price(self, value: float) -> None:
        """Validate sale price is valid."""
        if value <= 0:
            raise ValidationError(TransactionError.PRICE_POSITIVE)

    @validates_schema
    def validate_transaction_state(self) -> None:
        """Validate the transaction is in a state where it can be completed."""
        # This validation could be performed if the transaction_id was passed
        # Since it's handled in the resource, we don't need additional validation here


# Schema for creating a new buy transaction
class TransactionCreateSchema(Schema):
    """Schema for creating a new buy transaction."""

    service_id: fields.Integer = fields.Integer(required=True)
    stock_symbol: fields.String = fields.String(
        required=True,
        validate=validate.Length(min=1, max=10),
    )
    shares: fields.Float = fields.Float(
        required=True,
        validate=validate.Range(min=0.01),
    )
    purchase_price: fields.Float = fields.Float(
        required=True,
        validate=validate.Range(min=0.01),
    )

    @validates("stock_symbol")
    def validate_stock_symbol(self, value: str) -> None:
        """Validate stock symbol."""
        if not value or len(value) > StockConstants.MAX_SYMBOL_LENGTH:
            raise ValidationError(StockError.SYMBOL_LENGTH)

        if not value.isalnum():
            raise ValidationError(StockError.SYMBOL_FORMAT)


# Schema for cancelling a transaction
class TransactionCancelSchema(Schema):
    """Schema for cancelling a transaction."""

    reason: fields.String = fields.String(
        required=False,
        validate=validate.Length(max=500),
    )

    @validates_schema
    def validate_cancellation(self) -> None:
        """Validate the cancellation is possible."""
        # This validation is handled in the model's cancel_transaction method
        # The transaction_id is part of the resource URL path, so we don't need to
        # validate it here


# Schema for deleting a transaction
class TransactionDeleteSchema(Schema):
    """Schema for confirming transaction deletion."""

    confirm: fields.Boolean = fields.Boolean(required=True)
    transaction_id: fields.Integer = fields.Integer(required=True)

    @validates_schema
    def validate_deletion(self, data: dict) -> None:
        """Validate deletion confirmation."""
        if not data.get("confirm"):
            raise ValidationError(TransactionError.CONFIRM_DELETION)


# Create instances for easy importing
transaction_complete_schema = TransactionCompleteSchema()
transaction_create_schema = TransactionCreateSchema()
transaction_cancel_schema = TransactionCancelSchema()
transaction_delete_schema = TransactionDeleteSchema()
