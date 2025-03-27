"""
Stock Price model schemas.
"""
from marshmallow import fields, post_load, validates, validates_schema, ValidationError, validate
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from datetime import datetime, date, timedelta

from app.models import StockDailyPrice, StockIntradayPrice, PriceSource
from app.api.schemas import Schema
from app.services.database import get_db_session

# Daily price schemas
class StockDailyPriceSchema(SQLAlchemyAutoSchema):
    """Schema for serializing/deserializing StockDailyPrice models."""
    
    class Meta:
        model = StockDailyPrice
        include_relationships = False
        load_instance = True
        exclude = ('created_at', 'updated_at')
    
    # Add computed properties
    change = fields.Float(dump_only=True)
    change_percent = fields.Float(dump_only=True)

# Create instances for easy importing
daily_price_schema = StockDailyPriceSchema()
daily_prices_schema = StockDailyPriceSchema(many=True)

# Schema for creating/updating a daily price
class StockDailyPriceInputSchema(Schema):
    """Schema for creating or updating a StockDailyPrice."""
    price_date = fields.Date(required=True)
    open_price = fields.Float(allow_none=True)
    high_price = fields.Float(allow_none=True)
    low_price = fields.Float(allow_none=True)
    close_price = fields.Float(allow_none=True)
    adj_close = fields.Float(allow_none=True)
    volume = fields.Integer(allow_none=True)
    source = fields.String(validate=validate.OneOf([source.value for source in PriceSource]), default=PriceSource.HISTORICAL.value)
    
    @validates('price_date')
    def validate_price_date(self, price_date):
        """Validate price date."""
        if price_date > date.today():
            raise ValidationError('Price date cannot be in the future')
    
    @post_load
    def make_daily_price(self, data, **kwargs):
        """Create a StockDailyPrice instance from validated data."""
        return StockDailyPrice(**data)

# Schema for deleting a daily price
class StockDailyPriceDeleteSchema(Schema):
    """Schema for confirming daily price deletion."""
    confirm = fields.Boolean(required=True)
    price_id = fields.Integer(required=True)
    
    @validates_schema
    def validate_deletion(self, data, **kwargs):
        """Validate deletion confirmation and check for dependencies."""
        if not data.get('confirm'):
            raise ValidationError("Must confirm deletion by setting 'confirm' to true")
        
        # Verify the price record exists and can be deleted
        with get_db_session() as session:
            price = session.query(StockDailyPrice).filter_by(id=data['price_id']).first()
            if not price:
                raise ValidationError("Daily price record not found")
                
            # Check if this is recent data (within last 30 days)
            # Recent data is often used for analysis and should be protected
            thirty_days_ago = datetime.now().date() - timedelta(days=30)
            if price.price_date >= thirty_days_ago:
                raise ValidationError("Cannot delete recent price data (less than 30 days old). This data may be in use for active analyses.")
                
            # Could add additional checks for dependencies here:
            # - Check if used in any reports
            # - Check if referenced by any trading algorithms
            # - etc.

# Intraday price schemas
class StockIntradayPriceSchema(SQLAlchemyAutoSchema):
    """Schema for serializing/deserializing StockIntradayPrice models."""
    
    class Meta:
        model = StockIntradayPrice
        include_relationships = False
        load_instance = True
        exclude = ('created_at', 'updated_at')
    
    # Add computed properties
    change = fields.Float(dump_only=True)
    change_percent = fields.Float(dump_only=True)

# Create instances for easy importing
intraday_price_schema = StockIntradayPriceSchema()
intraday_prices_schema = StockIntradayPriceSchema(many=True)

# Schema for creating/updating an intraday price
class StockIntradayPriceInputSchema(Schema):
    """Schema for creating or updating a StockIntradayPrice."""
    timestamp = fields.DateTime(required=True)
    interval = fields.Integer(validate=validate.OneOf([1, 5, 15, 30, 60]), default=1)
    open_price = fields.Float(allow_none=True)
    high_price = fields.Float(allow_none=True)
    low_price = fields.Float(allow_none=True)
    close_price = fields.Float(allow_none=True)
    volume = fields.Integer(allow_none=True)
    source = fields.String(validate=validate.OneOf([source.value for source in PriceSource]), default=PriceSource.DELAYED.value)
    
    @validates('timestamp')
    def validate_timestamp(self, timestamp):
        """Validate timestamp."""
        if timestamp > datetime.now():
            raise ValidationError('Timestamp cannot be in the future')
    
    @post_load
    def make_intraday_price(self, data, **kwargs):
        """Create a StockIntradayPrice instance from validated data."""
        return StockIntradayPrice(**data)

# Schema for deleting an intraday price
class StockIntradayPriceDeleteSchema(Schema):
    """Schema for confirming intraday price deletion."""
    confirm = fields.Boolean(required=True)
    price_id = fields.Integer(required=True)
    
    @validates_schema
    def validate_deletion(self, data, **kwargs):
        """Validate deletion confirmation and check for dependencies."""
        if not data.get('confirm'):
            raise ValidationError("Must confirm deletion by setting 'confirm' to true")
        
        # Verify the price record exists and can be deleted
        with get_db_session() as session:
            price = session.query(StockIntradayPrice).filter_by(id=data['price_id']).first()
            if not price:
                raise ValidationError("Intraday price record not found")
                
            # Check if this is recent data (within last 7 days)
            # Recent data is often used for analysis and should be protected
            seven_days_ago = datetime.now() - timedelta(days=7)
            if price.timestamp >= seven_days_ago:
                raise ValidationError("Cannot delete recent price data (less than 7 days old). This data may be in use for active analyses.")
                
            # Could add additional checks for dependencies here:
            # - Check if used in any reports
            # - Check if referenced by any trading algorithms
            # - etc.

# Create instances for easy importing
daily_price_input_schema = StockDailyPriceInputSchema()
daily_price_delete_schema = StockDailyPriceDeleteSchema()
intraday_price_input_schema = StockIntradayPriceInputSchema()
intraday_price_delete_schema = StockIntradayPriceDeleteSchema() 