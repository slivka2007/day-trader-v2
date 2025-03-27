"""
Trading Transaction model schemas.
"""
from marshmallow import fields, post_load, validates, validates_schema, ValidationError, validate
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from datetime import datetime

from app.models import TradingTransaction, TransactionState
from app.api.schemas import Schema
from app.services.database import get_db_session

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

# Schema for creating a new buy transaction
class TransactionCreateSchema(Schema):
    """Schema for creating a new buy transaction."""
    service_id = fields.Integer(required=True)
    stock_symbol = fields.String(required=False)  # Optional as it can come from service
    shares = fields.Integer(required=True, validate=validate.Range(min=1))
    purchase_price = fields.Decimal(required=True, validate=validate.Range(min=0.01))
    
    @validates_schema
    def validate_service_state(self, data, **kwargs):
        """Validate the service is in a state where it can buy."""
        from app.models import TradingService
        
        with get_db_session() as session:
            service = session.query(TradingService).filter_by(id=data['service_id']).first()
            if not service:
                raise ValidationError("Service not found")
            if not service.can_buy:
                raise ValidationError("Service cannot make purchases in its current state")
            
            # If stock symbol not provided, use the one from service
            if 'stock_symbol' not in data or not data['stock_symbol']:
                data['stock_symbol'] = service.stock_symbol

# Schema for cancelling a transaction
class TransactionCancelSchema(Schema):
    """Schema for cancelling a transaction."""
    reason = fields.String(required=False)

# Schema for deleting a transaction
class TransactionDeleteSchema(Schema):
    """Schema for confirming transaction deletion."""
    confirm = fields.Boolean(required=True)
    transaction_id = fields.Integer(required=True)
    
    @validates_schema
    def validate_deletion(self, data, **kwargs):
        """Validate deletion confirmation."""
        if not data.get('confirm'):
            raise ValidationError("Must confirm deletion by setting 'confirm' to true")
        
        # Check if the transaction is in a state that allows deletion
        with get_db_session() as session:
            transaction = session.query(TradingTransaction).filter_by(id=data['transaction_id']).first()
            if not transaction:
                raise ValidationError("Transaction not found")
            
            if transaction.state != TransactionState.CANCELLED:
                raise ValidationError("Cannot delete an open or closed transaction")

# Create instances for easy importing
transaction_complete_schema = TransactionCompleteSchema()
transaction_create_schema = TransactionCreateSchema()
transaction_cancel_schema = TransactionCancelSchema()
transaction_delete_schema = TransactionDeleteSchema() 