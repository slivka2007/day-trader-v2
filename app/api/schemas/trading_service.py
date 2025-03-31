"""
Trading Service model schemas.
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

from app.api.schemas import Schema
from app.models import ServiceState, TradingMode, TradingService


class TradingServiceSchema(SQLAlchemyAutoSchema):
    """Schema for serializing/deserializing TradingService models."""

    class Meta:
        model = TradingService
        include_relationships = False
        load_instance = True
        exclude = ("created_at", "updated_at")

    # Add validation for trading service fields
    @validates("initial_balance")
    def validate_initial_balance(self, value):
        """Validate initial balance is positive."""
        if value <= 0:
            raise ValidationError("Initial balance must be greater than 0")

    @validates("stock_symbol")
    def validate_stock_symbol(self, value):
        """Validate stock symbol."""
        if not value or len(value) > 10:
            raise ValidationError("Stock symbol must be 1-10 characters")

        if not value.isalnum():
            raise ValidationError("Stock symbol must contain only letters and numbers")

    @validates("allocation_percent")
    def validate_allocation_percent(self, value):
        """Validate allocation percent."""
        if value < 0 or value > 100:
            raise ValidationError("Allocation percent must be between 0 and 100")

    @validates("buy_threshold")
    def validate_buy_threshold(self, value):
        """Validate buy threshold."""
        if value < 0:
            raise ValidationError("Buy threshold must be non-negative")

    @validates("sell_threshold")
    def validate_sell_threshold(self, value):
        """Validate sell threshold."""
        if value < 0:
            raise ValidationError("Sell threshold must be non-negative")


# Create an instance for easy importing
service_schema = TradingServiceSchema()
services_schema = TradingServiceSchema(many=True)


# Schema for creating a trading service
class TradingServiceCreateSchema(Schema):
    """Schema for creating a TradingService."""

    stock_symbol = fields.String(required=True, validate=validate.Length(min=1, max=10))
    name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    description = fields.String(allow_none=True)
    initial_balance = fields.Decimal(required=True, validate=validate.Range(min=1))
    minimum_balance = fields.Decimal(default=0, validate=validate.Range(min=0))
    allocation_percent = fields.Decimal(
        default=0.5, validate=validate.Range(min=0, max=100)
    )
    buy_threshold = fields.Decimal(default=3.0, validate=validate.Range(min=0))
    sell_threshold = fields.Decimal(default=2.0, validate=validate.Range(min=0))
    stop_loss_percent = fields.Decimal(default=5.0, validate=validate.Range(min=0))
    take_profit_percent = fields.Decimal(default=10.0, validate=validate.Range(min=0))
    is_active = fields.Boolean(default=True)

    @post_load
    def make_service(self, data, **kwargs):
        """Create a TradingService instance from validated data."""
        # Set current_balance to initial_balance when creating
        data["current_balance"] = data["initial_balance"]
        return data


# Schema for updating a trading service
class TradingServiceUpdateSchema(Schema):
    """Schema for updating a TradingService."""

    name = fields.String(validate=validate.Length(min=1, max=100))
    description = fields.String(allow_none=True)
    stock_symbol = fields.String(validate=validate.Length(min=1, max=10))
    is_active = fields.Boolean()
    minimum_balance = fields.Decimal(validate=validate.Range(min=0))
    allocation_percent = fields.Decimal(validate=validate.Range(min=0, max=100))
    buy_threshold = fields.Decimal(validate=validate.Range(min=0))
    sell_threshold = fields.Decimal(validate=validate.Range(min=0))
    stop_loss_percent = fields.Decimal(validate=validate.Range(min=0))
    take_profit_percent = fields.Decimal(validate=validate.Range(min=0))
    state = fields.String(
        validate=validate.OneOf([state.value for state in ServiceState])
    )
    mode = fields.String(validate=validate.OneOf([mode.value for mode in TradingMode]))


# Schema for deleting a trading service
class TradingServiceDeleteSchema(Schema):
    """Schema for confirming trading service deletion."""

    confirm = fields.Boolean(required=True)
    service_id = fields.Integer(required=True)

    @validates_schema
    def validate_deletion(self, data, **kwargs):
        """Validate deletion confirmation and check for dependencies."""
        if not data.get("confirm"):
            raise ValidationError("Must confirm deletion by setting 'confirm' to true")

        # Check if service has associated transactions
        from app.models import TradingService, TradingTransaction
        from app.services.session_manager import SessionManager

        with SessionManager() as session:
            # Find the service
            service = (
                session.query(TradingService).filter_by(id=data["service_id"]).first()
            )
            if not service:
                return  # Service doesn't exist, let the resource handle this error

            # Check if any transactions are associated with this service
            transactions_count = (
                session.query(TradingTransaction)
                .filter_by(service_id=service.id)
                .count()
            )
            if transactions_count > 0:
                raise ValidationError(
                    f"Cannot delete service because it has {transactions_count} associated transaction(s). Cancel or complete all transactions first."
                )


# Schema for trading action (buy/sell decision)
class TradingServiceActionSchema(Schema):
    """Schema for service actions like buy/sell decisions."""

    action = fields.String(
        required=True, validate=validate.OneOf(["check_buy", "check_sell"])
    )
    stock_symbol = fields.String(required=True, validate=validate.Length(min=1, max=10))
    service_id = fields.Integer(required=True)
    purchase_price = fields.Decimal(required=False)  # Only needed for sell checks

    @validates("stock_symbol")
    def validate_symbol(self, symbol):
        """Validate stock symbol."""
        if not symbol or len(symbol) > 10:
            raise ValidationError("Stock symbol must be 1-10 characters")

        if not symbol.isalnum():
            raise ValidationError("Stock symbol must contain only letters and numbers")


# Schema for trading decision response
class TradingDecisionResponseSchema(Schema):
    """Schema for trading decision responses."""

    should_proceed = fields.Boolean(required=True)
    reason = fields.String(required=True)
    timestamp = fields.DateTime(required=True)
    details = fields.Dict(required=False)
    next_action = fields.String(required=False)


# Create instances for easy importing
service_create_schema = TradingServiceCreateSchema()
service_update_schema = TradingServiceUpdateSchema()
service_delete_schema = TradingServiceDeleteSchema()
service_action_schema = TradingServiceActionSchema()
decision_response_schema = TradingDecisionResponseSchema()
