"""
Trading Service model schemas.
"""
from marshmallow import fields, post_load, validates, ValidationError, validate
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from decimal import Decimal

from app.models import TradingService, ServiceState, TradingMode
from app.api.schemas import Schema

class TradingServiceSchema(SQLAlchemyAutoSchema):
    """Schema for serializing/deserializing TradingService models."""
    
    class Meta:
        model = TradingService
        include_relationships = False
        load_instance = True
        exclude = ('created_at', 'updated_at')
    
    # Add validation for trading service fields
    @validates('initial_balance')
    def validate_initial_balance(self, value):
        """Validate initial balance is positive."""
        if value <= 0:
            raise ValidationError('Initial balance must be greater than 0')

# Create an instance for easy importing
service_schema = TradingServiceSchema()
services_schema = TradingServiceSchema(many=True)

# Schema for creating a trading service
class TradingServiceCreateSchema(Schema):
    """Schema for creating a TradingService."""
    stock_symbol = fields.String(required=True, validate=validate.Length(min=1, max=10))
    name = fields.String(allow_none=True)
    initial_balance = fields.Decimal(required=True, validate=validate.Range(min=1))
    
    @post_load
    def make_service(self, data, **kwargs):
        """Create a TradingService instance from validated data."""
        # Set current_balance to initial_balance when creating
        data['current_balance'] = data['initial_balance']
        return TradingService(**data)

# Schema for updating a trading service
class TradingServiceUpdateSchema(Schema):
    """Schema for updating a TradingService."""
    name = fields.String(allow_none=True)
    state = fields.String(validate=validate.OneOf([state.value for state in ServiceState]))
    mode = fields.String(validate=validate.OneOf([mode.value for mode in TradingMode]))

# Create instances for easy importing
service_create_schema = TradingServiceCreateSchema()
service_update_schema = TradingServiceUpdateSchema() 