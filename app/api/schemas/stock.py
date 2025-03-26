"""
Stock model schemas.
"""
from marshmallow import fields, post_load, validates, ValidationError, validate
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from app.models import Stock
from app.api.schemas import Schema

class StockSchema(SQLAlchemyAutoSchema):
    """Schema for serializing/deserializing Stock models."""
    
    class Meta:
        model = Stock
        include_relationships = False
        load_instance = True
        exclude = ('created_at', 'updated_at')
    
    # Add validation for stock symbol
    @validates('symbol')
    def validate_symbol(self, symbol):
        """Validate stock symbol format."""
        if not symbol or len(symbol) > 10:
            raise ValidationError('Stock symbol must be 1-10 characters')
        
        if not symbol.isalnum():
            raise ValidationError('Stock symbol must contain only letters and numbers')

# Create an instance for easy importing
stock_schema = StockSchema()
stocks_schema = StockSchema(many=True)

# Schema for creating/updating a stock with only necessary fields
class StockInputSchema(Schema):
    """Schema for creating or updating a Stock."""
    symbol = fields.String(required=True, validate=validate.Length(min=1, max=10))
    name = fields.String(allow_none=True)
    is_active = fields.Boolean(default=True)
    sector = fields.String(allow_none=True)
    description = fields.String(allow_none=True)
    
    @post_load
    def make_stock(self, data, **kwargs):
        """Create a Stock instance from validated data."""
        return Stock(**data)

# Create an instance for easy importing
stock_input_schema = StockInputSchema() 