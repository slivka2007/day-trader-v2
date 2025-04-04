"""Trading Service model schemas."""

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

from app.api.schemas import Schema
from app.models import (
    ServiceAction,
    ServiceState,
    TradingMode,
    TradingService,
)
from app.utils.constants import StockConstants, TradingServiceConstants
from app.utils.errors import TradingServiceError


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
            raise ValidationError(TradingServiceError.INITIAL_BALANCE)

    @validates("stock_symbol")
    def validate_stock_symbol(self, value: str) -> None:
        """Validate stock symbol."""
        if not value or len(value) > StockConstants.MAX_SYMBOL_LENGTH:
            raise ValidationError(TradingServiceError.SYMBOL_LENGTH)

        if not value.isalnum():
            raise ValidationError(TradingServiceError.SYMBOL_FORMAT)

    @validates("allocation_percent")
    def validate_allocation_percent(self, value: float) -> None:
        """Validate allocation percent."""
        if (
            value < TradingServiceConstants.MIN_ALLOCATION_PERCENT
            or value > TradingServiceConstants.MAX_ALLOCATION_PERCENT
        ):
            raise ValidationError(TradingServiceError.ALLOCATION_PERCENT)

    @validates("buy_threshold")
    def validate_buy_threshold(self, value: float) -> None:
        """Validate buy threshold."""
        if value < 0:
            raise ValidationError(TradingServiceError.BUY_THRESHOLD_NEGATIVE)

    @validates("sell_threshold")
    def validate_sell_threshold(self, value: float) -> None:
        """Validate sell threshold."""
        if value < 0:
            raise ValidationError(TradingServiceError.SELL_THRESHOLD_NEGATIVE)


# Create an instance for easy importing
service_schema = TradingServiceSchema()
services_schema = TradingServiceSchema(many=True)


# Schema for creating a trading service
class TradingServiceCreateSchema(Schema):
    """Schema for creating a TradingService."""

    stock_symbol: fields.String = fields.String(
        required=True,
        validate=validate.Length(min=1, max=StockConstants.MAX_SYMBOL_LENGTH),
    )
    name: fields.String = fields.String(
        required=True,
        validate=validate.Length(min=1, max=TradingServiceConstants.MAX_NAME_LENGTH),
    )
    description: fields.String = fields.String(allow_none=True)
    initial_balance: fields.Float = fields.Float(
        required=True,
        validate=validate.Range(min=TradingServiceConstants.MIN_INITIAL_BALANCE),
    )
    minimum_balance: fields.Float = fields.Float(
        default=0,
        validate=validate.Range(min=TradingServiceConstants.MIN_MINIMUM_BALANCE),
    )
    allocation_percent: fields.Float = fields.Float(
        default=TradingServiceConstants.DEFAULT_ALLOCATION_PERCENT,
        validate=validate.Range(
            min=TradingServiceConstants.MIN_ALLOCATION_PERCENT,
            max=TradingServiceConstants.MAX_ALLOCATION_PERCENT,
        ),
    )
    buy_threshold: fields.Float = fields.Float(
        default=TradingServiceConstants.DEFAULT_BUY_THRESHOLD,
        validate=validate.Range(min=TradingServiceConstants.MIN_BUY_THRESHOLD),
    )
    sell_threshold: fields.Float = fields.Float(
        default=TradingServiceConstants.DEFAULT_SELL_THRESHOLD,
        validate=validate.Range(min=TradingServiceConstants.MIN_SELL_THRESHOLD),
    )
    stop_loss_percent: fields.Float = fields.Float(
        default=TradingServiceConstants.DEFAULT_STOP_LOSS_PERCENT,
        validate=validate.Range(min=TradingServiceConstants.MIN_STOP_LOSS_PERCENT),
    )
    take_profit_percent: fields.Float = fields.Float(
        default=TradingServiceConstants.DEFAULT_TAKE_PROFIT_PERCENT,
        validate=validate.Range(min=TradingServiceConstants.MIN_TAKE_PROFIT_PERCENT),
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

    name: fields.String = fields.String(
        validate=validate.Length(
            min=TradingServiceConstants.MIN_NAME_LENGTH,
            max=TradingServiceConstants.MAX_NAME_LENGTH,
        ),
    )
    description: fields.String = fields.String(allow_none=True)
    stock_symbol: fields.String = fields.String(
        validate=validate.Length(
            min=StockConstants.MIN_SYMBOL_LENGTH,
            max=StockConstants.MAX_SYMBOL_LENGTH,
        ),
    )
    is_active: fields.Boolean = fields.Boolean()
    minimum_balance: fields.Float = fields.Float(
        validate=validate.Range(min=TradingServiceConstants.MIN_MINIMUM_BALANCE),
    )
    allocation_percent: fields.Float = fields.Float(
        validate=validate.Range(
            min=TradingServiceConstants.MIN_ALLOCATION_PERCENT,
            max=TradingServiceConstants.MAX_ALLOCATION_PERCENT,
        ),
    )
    buy_threshold: fields.Float = fields.Float(
        validate=validate.Range(min=TradingServiceConstants.MIN_BUY_THRESHOLD),
    )
    sell_threshold: fields.Float = fields.Float(
        validate=validate.Range(min=TradingServiceConstants.MIN_SELL_THRESHOLD),
    )
    stop_loss_percent: fields.Float = fields.Float(
        validate=validate.Range(min=TradingServiceConstants.MIN_STOP_LOSS_PERCENT),
    )
    take_profit_percent: fields.Float = fields.Float(
        validate=validate.Range(min=TradingServiceConstants.MIN_TAKE_PROFIT_PERCENT),
    )
    state: fields.String = fields.String(
        validate=validate.OneOf([state.value for state in ServiceState]),
    )
    mode: fields.String = fields.String(
        validate=validate.OneOf([mode.value for mode in TradingMode]),
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
            raise ValidationError(TradingServiceError.CONFIRM_DELETION)


# Schema for trading action (buy/sell decision)
class TradingServiceActionSchema(Schema):
    """Schema for service actions like buy/sell decisions."""

    action: fields.String = fields.String(
        required=True,
        validate=validate.OneOf([action.value for action in ServiceAction]),
    )
    stock_symbol: fields.String = fields.String(
        required=True,
        validate=validate.Length(
            min=StockConstants.MIN_SYMBOL_LENGTH,
            max=StockConstants.MAX_SYMBOL_LENGTH,
        ),
    )
    service_id: fields.Integer = fields.Integer(required=True)
    purchase_price: fields.Float = fields.Float(
        required=False,
    )  # Only needed for sell checks

    @validates("stock_symbol")
    def validate_symbol(self, symbol: str) -> None:
        """Validate stock symbol."""
        if not symbol or len(symbol) > StockConstants.MAX_SYMBOL_LENGTH:
            raise ValidationError(TradingServiceError.SYMBOL_LENGTH)

        if not symbol.isalnum():
            raise ValidationError(TradingServiceError.SYMBOL_FORMAT)


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
