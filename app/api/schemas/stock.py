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
    
    # Add calculated fields
    has_services = fields.Method("check_has_services", dump_only=True)
    has_transactions = fields.Method("check_has_transactions", dump_only=True)
    price_count = fields.Method("count_prices", dump_only=True)
    
    def check_has_services(self, obj):
        """Check if the stock has any associated services."""
        return len(obj.services) > 0 if obj.services else False
    
    def check_has_transactions(self, obj):
        """Check if the stock has any associated transactions."""
        return len(obj.transactions) > 0 if obj.transactions else False
    
    def count_prices(self, obj):
        """Count the number of price data points available."""
        daily_count = len(obj.daily_prices) if obj.daily_prices else 0
        intraday_count = len(obj.intraday_prices) if obj.intraday_prices else 0
        return {
            'daily': daily_count,
            'intraday': intraday_count,
            'total': daily_count + intraday_count
        }
    
    # Add validation for stock symbol
    @validates('symbol')
    def validate_symbol(self, symbol):
        """Validate stock symbol format."""
        if not symbol or len(symbol) > 10:
            raise ValidationError('Stock symbol must be 1-10 characters')
        
        if not symbol.isalnum():
            raise ValidationError('Stock symbol must contain only letters and numbers')
    
    @validates('name')
    def validate_name(self, name):
        """Validate stock name."""
        if name and len(name) > 200:
            raise ValidationError('Stock name must be 200 characters or less')
    
    @validates('sector')
    def validate_sector(self, sector):
        """Validate stock sector."""
        if sector and len(sector) > 100:
            raise ValidationError('Stock sector must be 100 characters or less')
    
    @validates('description')
    def validate_description(self, description):
        """Validate stock description."""
        if description and len(description) > 1000:
            raise ValidationError('Stock description must be 1000 characters or less')

# Create an instance for easy importing
stock_schema = StockSchema()
stocks_schema = StockSchema(many=True)

# Schema for creating/updating a stock with only necessary fields
class StockInputSchema(Schema):
    """Schema for creating or updating a Stock."""
    symbol = fields.String(required=True, validate=validate.Length(min=1, max=10))
    name = fields.String(allow_none=True, validate=validate.Length(max=200))
    is_active = fields.Boolean(default=True)
    sector = fields.String(allow_none=True, validate=validate.Length(max=100))
    description = fields.String(allow_none=True, validate=validate.Length(max=1000))
    
    @validates('symbol')
    def validate_symbol(self, symbol):
        """Validate stock symbol format."""
        if not symbol.isalnum():
            raise ValidationError('Stock symbol must contain only letters and numbers')
    
    @post_load
    def make_stock(self, data, **kwargs):
        """Create a Stock instance from validated data."""
        # Ensure symbol is uppercase
        if 'symbol' in data:
            data['symbol'] = data['symbol'].upper()
        return data

# Schema for deleting a stock
class StockDeleteSchema(Schema):
    """Schema for confirming stock deletion."""
    confirm = fields.Boolean(required=True)
    stock_id = fields.Integer(required=True)
    
    @validates_schema
    def validate_deletion(self, data, **kwargs):
        """Validate that deletion is properly confirmed and stock has no dependencies."""
        if not data.get('confirm'):
            raise ValidationError("Must confirm deletion by setting 'confirm' to true")
            
        # Check if stock has associated services or transactions
        from app.services.database import get_db_session
        from app.models import Stock, TradingService, TradingTransaction
        
        with get_db_session() as session:
            # Find the stock by ID
            stock = session.query(Stock).filter_by(id=data['stock_id']).first()
            if not stock:
                return  # Stock doesn't exist, let the resource handle this error
                
            # Check if any trading services use this stock
            services_count = session.query(TradingService).filter_by(stock_id=stock.id).count()
            if services_count > 0:
                raise ValidationError(f"Cannot delete stock '{stock.symbol}' because it is used by {services_count} trading service(s)")
                
            # Check if any transactions are associated with this stock
            transactions_count = session.query(TradingTransaction).filter_by(stock_id=stock.id).count()
            if transactions_count > 0:
                raise ValidationError(f"Cannot delete stock '{stock.symbol}' because it has {transactions_count} associated transaction(s)")

# Create instances for easy importing
stock_input_schema = StockInputSchema()
stock_delete_schema = StockDeleteSchema() 