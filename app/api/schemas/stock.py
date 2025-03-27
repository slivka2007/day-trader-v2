"""
Stock model schemas.
"""
from marshmallow import fields, post_load, validates, ValidationError, validate, validates_schema
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

# Schema for deleting a stock
class StockDeleteSchema(Schema):
    """Schema for confirming stock deletion."""
    confirm = fields.Boolean(required=True)
    symbol = fields.String(required=True)
    
    @validates_schema
    def validate_confirmation(self, data, **kwargs):
        """Validate that deletion is properly confirmed and stock has no dependencies."""
        if not data.get('confirm'):
            raise ValidationError("Must confirm deletion by setting 'confirm' to true")
            
        # Check if stock has associated services or transactions
        from app.services.database import get_db_session
        from app.models import Stock, TradingService, TradingTransaction
        
        with get_db_session() as session:
            # Find the stock by symbol
            stock = session.query(Stock).filter_by(symbol=data['symbol']).first()
            if not stock:
                return  # Stock doesn't exist, let the resource handle this error
                
            # Check if any trading services use this stock
            services_count = session.query(TradingService).filter_by(stock_symbol=stock.symbol).count()
            if services_count > 0:
                raise ValidationError(f"Cannot delete stock '{stock.symbol}' because it is used by {services_count} trading service(s)")
                
            # Check if any transactions are associated with this stock
            transactions_count = session.query(TradingTransaction).filter_by(stock_symbol=stock.symbol).count()
            if transactions_count > 0:
                raise ValidationError(f"Cannot delete stock '{stock.symbol}' because it has {transactions_count} associated transaction(s)")

# Create instances for easy importing
stock_input_schema = StockInputSchema()
stock_delete_schema = StockDeleteSchema() 