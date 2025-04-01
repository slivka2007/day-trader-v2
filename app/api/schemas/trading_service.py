"""
Trading Service model schemas.
"""

from typing import Literal

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
from app.models import (
    ServiceAction,
    ServiceState,
    TradingMode,
    TradingService,
)


class TradingServiceSchema(SQLAlchemyAutoSchema):
    """Schema for serializing/deserializing TradingService models."""

    class Meta:
        model = TradingService
        include_relationships = False
        load_instance = True
        exclude: tuple[Literal["created_at"], Literal["updated_at"]] = (
            "created_at",
            "updated_at",
        )

    # Add validation for trading service fields
    @validates("initial_balance")
    def validate_initial_balance(self, value: float) -> None:
        """Validate initial balance is positive."""
        if value <= 0:
            raise ValidationError("Initial balance must be greater than 0")

    @validates("stock_symbol")
    def validate_stock_symbol(self, value: str) -> None:
        """Validate stock symbol."""
        if not value or len(value) > 10:
            raise ValidationError("Stock symbol must be 1-10 characters")

        if not value.isalnum():
            raise ValidationError("Stock symbol must contain only letters and numbers")

    @validates("allocation_percent")
    def validate_allocation_percent(self, value: float) -> None:
        """Validate allocation percent."""
        if value < 0 or value > 100:
            raise ValidationError("Allocation percent must be between 0 and 100")

    @validates("buy_threshold")
    def validate_buy_threshold(self, value: float) -> None:
        """Validate buy threshold."""
        if value < 0:
            raise ValidationError("Buy threshold must be non-negative")

    @validates("sell_threshold")
    def validate_sell_threshold(self, value: float) -> None:
        """Validate sell threshold."""
        if value < 0:
            raise ValidationError("Sell threshold must be non-negative")


# Create an instance for easy importing
service_schema = TradingServiceSchema()
services_schema = TradingServiceSchema(many=True)


# Schema for creating a trading service
class TradingServiceCreateSchema(Schema):
    """Schema for creating a TradingService."""

    stock_symbol: fields.String = fields.String(
        required=True, validate=validate.Length(min=1, max=10)
    )
    name: fields.String = fields.String(
        required=True, validate=validate.Length(min=1, max=100)
    )
    description: fields.String = fields.String(allow_none=True)
    initial_balance: fields.Float = fields.Float(
        required=True, validate=validate.Range(min=1)
    )
    minimum_balance: fields.Float = fields.Float(
        default=0, validate=validate.Range(min=0)
    )
    allocation_percent: fields.Float = fields.Float(
        default=0.5, validate=validate.Range(min=0, max=100)
    )
    buy_threshold: fields.Float = fields.Float(
        default=3.0, validate=validate.Range(min=0)
    )
    sell_threshold: fields.Float = fields.Float(
        default=2.0, validate=validate.Range(min=0)
    )
    stop_loss_percent: fields.Float = fields.Float(
        default=5.0, validate=validate.Range(min=0)
    )
    take_profit_percent: fields.Float = fields.Float(
        default=10.0, validate=validate.Range(min=0)
    )
    is_active: fields.Boolean = fields.Boolean(default=True)

    @post_load
    def make_service(self, data: dict) -> TradingService:
        """Create a TradingService instance from validated data."""
        # Set current_balance to initial_balance when creating
        data["current_balance"] = data["initial_balance"]
        return TradingService.from_dict(data)


# Schema for updating a trading service
class TradingServiceUpdateSchema(Schema):
    """Schema for updating a TradingService."""

    name: fields.String = fields.String(validate=validate.Length(min=1, max=100))
    description: fields.String = fields.String(allow_none=True)
    stock_symbol: fields.String = fields.String(validate=validate.Length(min=1, max=10))
    is_active: fields.Boolean = fields.Boolean()
    minimum_balance: fields.Float = fields.Float(validate=validate.Range(min=0))
    allocation_percent: fields.Float = fields.Float(
        validate=validate.Range(min=0, max=100)
    )
    buy_threshold: fields.Float = fields.Float(validate=validate.Range(min=0))
    sell_threshold: fields.Float = fields.Float(validate=validate.Range(min=0))
    stop_loss_percent: fields.Float = fields.Float(validate=validate.Range(min=0))
    take_profit_percent: fields.Float = fields.Float(validate=validate.Range(min=0))
    state: fields.String = fields.String(
        validate=validate.OneOf([state.value for state in ServiceState])
    )
    mode: fields.String = fields.String(
        validate=validate.OneOf([mode.value for mode in TradingMode])
    )


# Schema for deleting a trading service
class TradingServiceDeleteSchema(Schema):
    """Schema for confirming trading service deletion."""

    confirm: fields.Boolean = fields.Boolean(required=True)
    service_id: fields.Integer = fields.Integer(required=True)

    @validates_schema
    def validate_deletion(self, data: dict) -> None:
        """Validate deletion confirmation and check for dependencies."""
        if not data.get("confirm"):
            raise ValidationError("Must confirm deletion by setting 'confirm' to true")

        # Check if service has associated transactions
        from app.models import TradingService, TradingTransaction
        from app.services.session_manager import SessionManager

        with SessionManager() as session:
            # Find the service
            service: TradingService | None = session.execute(
                select(TradingService).where(TradingService.id == data["service_id"])
            ).scalar_one_or_none()
            if not service:
                return  # Service doesn't exist, let the resource handle this error

            # Check if any transactions are associated with this service
            transactions_count: int = session.execute(
                select(TradingTransaction).where(
                    TradingTransaction.service_id == service.id
                )
            ).count()
            if transactions_count > 0:
                raise ValidationError(
                    f"Cannot delete service because it has {transactions_count} "
                    "associated transaction(s). Cancel or complete all transactions "
                    "first."
                )


# Schema for trading action (buy/sell decision)
class TradingServiceActionSchema(Schema):
    """Schema for service actions like buy/sell decisions."""

    action: fields.String = fields.String(
        required=True,
        validate=validate.OneOf([action.value for action in ServiceAction]),
    )
    stock_symbol: fields.String = fields.String(
        required=True, validate=validate.Length(min=1, max=10)
    )
    service_id: fields.Integer = fields.Integer(required=True)
    purchase_price: fields.Float = fields.Float(
        required=False
    )  # Only needed for sell checks

    @validates("stock_symbol")
    def validate_symbol(self, symbol: str) -> None:
        """Validate stock symbol."""
        if not symbol or len(symbol) > 10:
            raise ValidationError("Stock symbol must be 1-10 characters")

        if not symbol.isalnum():
            raise ValidationError("Stock symbol must contain only letters and numbers")


# Schema for trading decision response
class TradingDecisionResponseSchema(Schema):
    """Schema for trading decision responses."""

    should_proceed: fields.Boolean = fields.Boolean(required=True)
    reason: fields.String = fields.String(required=True)
    timestamp: fields.DateTime = fields.DateTime(required=True)
    details: fields.Dict = fields.Dict(required=False)
    next_action: fields.String = fields.String(required=False)


# Create instances for easy importing
service_create_schema = TradingServiceCreateSchema()
service_update_schema = TradingServiceUpdateSchema()
service_delete_schema = TradingServiceDeleteSchema()
service_action_schema = TradingServiceActionSchema()
decision_response_schema = TradingDecisionResponseSchema()
