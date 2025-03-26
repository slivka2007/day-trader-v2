"""
Trading Transaction model schemas.
"""
from marshmallow import fields, post_load, validates, ValidationError
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from app.models import TradingTransaction, TransactionState
from app.api.schemas import Schema

class TradingTransactionSchema(SQLAlchemyAutoSchema):
    """Schema for serializing/deserializing TradingTransaction models."""
    
    class Meta:
        model = TradingTransaction
        include_relationships = False
        load_instance = True
        exclude = ('created_at', 'updated_at')
    
    # Add custom fields and validation as needed
    is_complete = fields.Boolean(dump_only=True)
    is_profitable = fields.Boolean(dump_only=True)

# Create instances for easy importing
transaction_schema = TradingTransactionSchema()
transactions_schema = TradingTransactionSchema(many=True)

# Schema for completing a transaction (selling shares)
class TransactionCompleteSchema(Schema):
    """Schema for completing (selling) a transaction."""
    sale_price = fields.Decimal(required=True, validate=validate.Range(min=0.01))
    
    @validates('sale_price')
    def validate_sale_price(self, value):
        """Validate sale price is valid."""
        if value <= 0:
            raise ValidationError('Sale price must be greater than 0')

# Create an instance for easy importing
transaction_complete_schema = TransactionCompleteSchema() 