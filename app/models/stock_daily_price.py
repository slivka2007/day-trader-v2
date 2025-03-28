"""
Daily price model.

This model represents end-of-day stock price data.
"""
import logging
from typing import Optional, TYPE_CHECKING, Dict, Any, Set, Tuple, List
from datetime import date, timedelta

from sqlalchemy import Column, Integer, Float, Date, ForeignKey, UniqueConstraint, String, and_
from sqlalchemy.orm import relationship, Mapped, Session, validates
from flask import current_app

from app.models.base import Base
from app.models.enums import PriceSource
from app.utils.current_datetime import get_current_datetime, get_current_date
if TYPE_CHECKING:
    from app.models.stock import Stock

# Set up logging
logger = logging.getLogger(__name__)

class StockDailyPrice(Base):
    """
    Model representing daily stock price data.
    
    Stores end-of-day price information for stocks, including open, high, low,
    close prices and trading volume. Each record represents a single trading day
    for a specific stock.
    
    Attributes:
        id: Unique identifier for the price record
        stock_id: Foreign key to the associated Stock
        price_date: The trading date this price data represents
        open_price: Opening price for the trading day
        high_price: Highest price during the trading day
        low_price: Lowest price during the trading day
        close_price: Closing price for the trading day
        adj_close: Adjusted closing price (accounts for dividends, splits)
        volume: Number of shares traded during the day
        source: Source of this price data
        stock: Relationship to the parent Stock
    """
    __tablename__ = 'stock_daily_prices'
    
    # Foreign keys and date
    stock_id = Column(Integer, ForeignKey('stocks.id'), nullable=False)
    price_date = Column(Date, nullable=False)
    
    # Price data
    open_price = Column(Float, nullable=True)
    high_price = Column(Float, nullable=True)
    low_price = Column(Float, nullable=True)
    close_price = Column(Float, nullable=True)
    adj_close = Column(Float, nullable=True)
    volume = Column(Integer, nullable=True)
    
    # Metadata
    source = Column(String(20), default=PriceSource.HISTORICAL.value, nullable=False)
    
    # Relationship
    stock: Mapped["Stock"] = relationship("Stock", back_populates="daily_prices")
    
    # Constraints
    __table_args__ = (UniqueConstraint('stock_id', 'price_date', name='uix_stock_daily_date'),)
    
    # Validations
    @validates('source')
    def validate_source(self, key, source):
        """Validate price source."""
        if source and not PriceSource.is_valid(source):
            valid_sources = PriceSource.values()
            raise ValueError(f"Invalid price source: {source}. Valid sources are: {', '.join(valid_sources)}")
        return source
    
    @validates('price_date')
    def validate_price_date(self, key, price_date):
        """Validate price date is not in the future."""
        if price_date and price_date > get_current_date():
            raise ValueError(f"Price date cannot be in the future: {price_date}")
        return price_date

    def __repr__(self) -> str:
        """String representation of the StockDailyPrice object."""
        return f"<StockDailyPrice(id={self.id}, stock_id={self.stock_id}, date={self.price_date})>"
    
    @property
    def change(self) -> Optional[float]:
        """Calculate the change in price from open to close."""
        if self.open_price is None or self.close_price is None:
            return None
        return self.close_price - self.open_price
    
    @property
    def change_percent(self) -> Optional[float]:
        """Calculate the percentage change from open to close."""
        if self.open_price is None or self.close_price is None or self.open_price == 0:
            return None
        return (self.close_price - self.open_price) / self.open_price * 100
    
    @property
    def is_real_data(self) -> bool:
        """Check if the price data is from a real source (not simulated)."""
        return PriceSource.is_real(self.source)
    
    @classmethod
    def get_by_date(cls, session: Session, stock_id: int, price_date: date) -> Optional["StockDailyPrice"]:
        """
        Get a price record by stock ID and date.
        
        Args:
            session: Database session
            stock_id: Stock ID
            price_date: Date of the price record
            
        Returns:
            Price record if found, None otherwise
        """
        return session.query(cls).filter(
            and_(cls.stock_id == stock_id, cls.price_date == price_date)
        ).first()
    
    @classmethod
    def get_by_date_range(cls, session: Session, stock_id: int, 
                      start_date: date, end_date: date = None) -> List["StockDailyPrice"]:
        """
        Get price records for a date range.
        
        Args:
            session: Database session
            stock_id: Stock ID
            start_date: Start date (inclusive)
            end_date: End date (inclusive), defaults to today
            
        Returns:
            List of price records
        """
        if end_date is None:
            end_date = get_current_date()
            
        return session.query(cls).filter(
            and_(
                cls.stock_id == stock_id,
                cls.price_date >= start_date,
                cls.price_date <= end_date
            )
        ).order_by(cls.price_date).all()
        
    def update(self, session: Session, data: Dict[str, Any]) -> "StockDailyPrice":
        """
        Update price record attributes.
        
        Args:
            session: Database session
            data: Dictionary of attributes to update
            
        Returns:
            Updated price record
            
        Raises:
            ValueError: If invalid data is provided
        """
        from app.api.schemas.stock_price import daily_price_schema
        from app.services.events import EventService
        
        try:
            # Define which fields can be updated
            allowed_fields = {
                'open_price', 'high_price', 'low_price', 'close_price', 
                'adj_close', 'volume', 'source'
            }
            
            # Use the update_from_dict method from Base
            updated = self.update_from_dict(data, allowed_fields)
            
            # Only emit event if something was updated
            if updated:
                session.commit()
                
                # Get stock symbol for event
                stock_symbol = self.stock.symbol if self.stock else "unknown"
                
                # Prepare response data
                price_data = daily_price_schema.dump(self)
                
                # Emit WebSocket event
                EventService.emit_price_update(
                    action='updated',
                    price_data=price_data,
                    stock_symbol=stock_symbol
                )
            
            return self
        except Exception as e:
            logger.error(f"Error during price update process: {str(e)}")
            session.rollback()
            raise ValueError(f"Could not update daily price record: {str(e)}")
    
    @classmethod
    def create_price(cls, session: Session, stock_id: int, price_date: date, 
                          data: Dict[str, Any]) -> "StockDailyPrice":
        """
        Create a new daily price record.
        
        Args:
            session: Database session
            stock_id: Stock ID
            price_date: Date of the price record
            data: Price data
            
        Returns:
            The created price record instance
            
        Raises:
            ValueError: If required data is missing or invalid
        """
        from app.api.schemas.stock_price import daily_price_schema
        from app.services.events import EventService
        from app.models import Stock
        
        try:
            # Verify stock exists
            stock = Stock.get_or_404(session, stock_id)
                
            # Check if price already exists for this date
            existing = cls.get_by_date(session, stock_id, price_date)
            if existing:
                raise ValueError(f"Price record already exists for stock ID {stock_id} on {price_date}")
            
            # Validate price data
            if 'high_price' in data and 'low_price' in data:
                if data['high_price'] < data['low_price']:
                    raise ValueError("High price cannot be less than low price")
            
            # Create the data dict including date and stock_id
            create_data = {'stock_id': stock_id, 'price_date': price_date}
            create_data.update(data)
            
            # Create price record
            price_record = cls.from_dict(create_data)
            session.add(price_record)
            session.commit()
            
            # Prepare response data
            price_data = daily_price_schema.dump(price_record)
            
            # Emit WebSocket event
            EventService.emit_price_update(
                action='created',
                price_data=price_data,
                stock_symbol=stock.symbol
            )
            
            return price_record
        except Exception as e:
            logger.error(f"Error creating daily price: {str(e)}")
            session.rollback()
            raise ValueError(f"Could not create daily price record: {str(e)}")
    
    # Alias for backward compatibility
    create_daily_price = create_price
    
    @classmethod
    def get_latest_prices(cls, session: Session, stock_id: int, days: int = 30) -> List["StockDailyPrice"]:
        """
        Get the latest price records for a stock.
        
        Args:
            session: Database session
            stock_id: Stock ID
            days: Number of days to look back
            
        Returns:
            List of price records, most recent first
        """
        end_date = get_current_date()
        start_date = end_date - timedelta(days=days)
        
        return session.query(cls).filter(
            and_(
                cls.stock_id == stock_id,
                cls.price_date >= start_date,
                cls.price_date <= end_date
            )
        ).order_by(cls.price_date.desc()).all()
        
    @classmethod
    def get_by_id(cls, session: Session, price_id: int) -> Optional["StockDailyPrice"]:
        """
        Get a daily price record by ID.
        
        Args:
            session: Database session
            price_id: Price record ID to retrieve
            
        Returns:
            StockDailyPrice instance if found, None otherwise
        """
        return session.query(cls).get(price_id)
