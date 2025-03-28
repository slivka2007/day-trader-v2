"""
Intraday price model.

This model represents intraday (e.g., hourly or minute-by-minute) stock price data.
"""
import logging
from typing import Optional, TYPE_CHECKING, Dict, Any, List, Set, Tuple
from datetime import datetime, timedelta

from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, UniqueConstraint, String, and_
from sqlalchemy.orm import relationship, Mapped, Session, validates
from flask import current_app

from app.models.base import Base
from app.models.enums import PriceSource
from app.utils.current_datetime import get_current_datetime
if TYPE_CHECKING:
    from app.models.stock import Stock

# Set up logging
logger = logging.getLogger(__name__)

class StockIntradayPrice(Base):
    """
    Model representing intraday stock price data.
    
    Stores price information for stocks during the trading day, including timestamp,
    open, high, low, close prices and trading volume. Each record represents a single
    time interval (e.g., minute, 5 minutes, hour) for a specific stock.
    
    Attributes:
        id: Unique identifier for the price record
        stock_id: Foreign key to the associated Stock
        timestamp: The date and time this price data represents
        interval: Time interval in minutes (1, 5, 15, 30, 60)
        open_price: Opening price for the time interval
        high_price: Highest price during the time interval
        low_price: Lowest price during the time interval
        close_price: Closing price for the time interval
        volume: Number of shares traded during the interval
        source: Source of this price data
        stock: Relationship to the parent Stock
    """
    __tablename__ = 'stock_intraday_prices'
    
    # Foreign keys and timestamp
    stock_id = Column(Integer, ForeignKey('stocks.id'), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    interval = Column(Integer, default=1, nullable=False)
    
    # Price data
    open_price = Column(Float, nullable=True)
    high_price = Column(Float, nullable=True)
    low_price = Column(Float, nullable=True)
    close_price = Column(Float, nullable=True)
    volume = Column(Integer, nullable=True)
    
    # Metadata
    source = Column(String(20), default=PriceSource.DELAYED.value, nullable=False)
    
    # Relationship
    stock: Mapped["Stock"] = relationship("Stock", back_populates="intraday_prices")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('stock_id', 'timestamp', 'interval', name='uix_stock_intraday_time'),
    )

    # Validations
    @validates('source')
    def validate_source(self, key, source):
        """Validate price source."""
        if source and not PriceSource.is_valid(source):
            valid_sources = PriceSource.values()
            raise ValueError(f"Invalid price source: {source}. Valid sources are: {', '.join(valid_sources)}")
        return source
    
    @validates('timestamp')
    def validate_timestamp(self, key, timestamp):
        """Validate timestamp is not in the future."""
        if timestamp and timestamp > get_current_datetime():
            raise ValueError(f"Timestamp cannot be in the future: {timestamp}")
        return timestamp
    
    @validates('interval')
    def validate_interval(self, key, interval):
        """Validate interval is one of the valid values."""
        if interval not in [1, 5, 15, 30, 60]:
            raise ValueError(f"Invalid interval {interval}. Must be one of: 1, 5, 15, 30, 60")
        return interval

    def __repr__(self) -> str:
        """String representation of the StockIntradayPrice object."""
        return f"<StockIntradayPrice(id={self.id}, stock_id={self.stock_id}, timestamp={self.timestamp})>"
    
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
    def get_by_timestamp(cls, session: Session, stock_id: int, timestamp: datetime, 
                        interval: int = 1) -> Optional["StockIntradayPrice"]:
        """
        Get a price record by stock ID, timestamp, and interval.
        
        Args:
            session: Database session
            stock_id: Stock ID
            timestamp: Timestamp of the price record
            interval: Time interval in minutes (default: 1)
            
        Returns:
            Price record if found, None otherwise
        """
        return session.query(cls).filter(
            and_(
                cls.stock_id == stock_id,
                cls.timestamp == timestamp,
                cls.interval == interval
            )
        ).first()
    
    @classmethod
    def get_by_time_range(cls, session: Session, stock_id: int, start_time: datetime, 
                         end_time: datetime = None, interval: int = 1) -> List["StockIntradayPrice"]:
        """
        Get price records for a time range.
        
        Args:
            session: Database session
            stock_id: Stock ID
            start_time: Start timestamp (inclusive)
            end_time: End timestamp (inclusive), defaults to current time
            interval: Time interval in minutes (default: 1)
            
        Returns:
            List of price records
        """
        if end_time is None:
            end_time = get_current_datetime()
            
        return session.query(cls).filter(
            and_(
                cls.stock_id == stock_id,
                cls.timestamp >= start_time,
                cls.timestamp <= end_time,
                cls.interval == interval
            )
        ).order_by(cls.timestamp).all()
        
    def update(self, session: Session, data: Dict[str, Any]) -> "StockIntradayPrice":
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
        from app.api.schemas.stock_price import intraday_price_schema
        from app.services.events import EventService
        
        try:
            # Define which fields can be updated
            allowed_fields = {
                'open_price', 'high_price', 'low_price', 'close_price',
                'volume', 'source'
            }
            
            # Validate high/low prices if both are provided
            if 'high_price' in data and 'low_price' in data:
                if data['high_price'] < data['low_price']:
                    raise ValueError("High price cannot be less than low price")
            
            # Use the update_from_dict method from Base
            updated = self.update_from_dict(data, allowed_fields)
            
            # Only emit event if something was updated
            if updated:
                session.commit()
                
                # Get stock symbol for event
                stock_symbol = self.stock.symbol if self.stock else "unknown"
                
                # Prepare response data
                price_data = intraday_price_schema.dump(self)
                
                # Emit WebSocket event
                EventService.emit_price_update(
                    action='updated',
                    price_data=price_data,
                    stock_symbol=stock_symbol
                )
            
            return self
        except Exception as e:
            logger.error(f"Error updating intraday price: {str(e)}")
            session.rollback()
            raise ValueError(f"Could not update intraday price record: {str(e)}")
    
    @classmethod
    def create_price(cls, session: Session, stock_id: int, timestamp: datetime, 
                             interval: int, data: Dict[str, Any]) -> "StockIntradayPrice":
        """
        Create a new intraday price record.
        
        Args:
            session: Database session
            stock_id: Stock ID
            timestamp: Timestamp of the price record
            interval: Time interval in minutes (1, 5, 15, 30, 60)
            data: Price data
            
        Returns:
            The created price record instance
            
        Raises:
            ValueError: If required data is missing or invalid
        """
        from app.api.schemas.stock_price import intraday_price_schema
        from app.services.events import EventService
        from app.models import Stock
        
        try:
            # Validate interval
            if interval not in [1, 5, 15, 30, 60]:
                raise ValueError(f"Invalid interval {interval}. Must be one of: 1, 5, 15, 30, 60")
            
            # Validate timestamp
            if timestamp > get_current_datetime():
                raise ValueError(f"Timestamp cannot be in the future: {timestamp}")
            
            # Verify stock exists
            stock = Stock.get_or_404(session, stock_id)
                
            # Check if price already exists for this timestamp and interval
            existing = cls.get_by_timestamp(session, stock_id, timestamp, interval)
            if existing:
                raise ValueError(f"Price record already exists for stock ID {stock_id} at {timestamp} with interval {interval}")
            
            # Validate price data
            if 'high_price' in data and 'low_price' in data and data['high_price'] < data['low_price']:
                raise ValueError("High price cannot be less than low price")
                
            # Create data dict including required fields
            create_data = {
                'stock_id': stock_id,
                'timestamp': timestamp,
                'interval': interval,
                'source': data.get('source', PriceSource.DELAYED.value)
            }
            
            # Add price data
            for key in ['open_price', 'high_price', 'low_price', 'close_price', 'volume']:
                if key in data:
                    create_data[key] = data[key]
                    
            # Create price record
            price_record = cls.from_dict(create_data)
            session.add(price_record)
            session.commit()
            
            # Prepare response data
            price_data = intraday_price_schema.dump(price_record)
            
            # Emit WebSocket event
            EventService.emit_price_update(
                action='created',
                price_data=price_data,
                stock_symbol=stock.symbol
            )
            
            return price_record
        except Exception as e:
            logger.error(f"Error creating intraday price: {str(e)}")
            session.rollback()
            raise ValueError(f"Could not create intraday price record: {str(e)}")
    
    # Alias for backward compatibility        
    create_intraday_price = create_price
            
    @classmethod
    def get_latest_prices(cls, session: Session, stock_id: int, hours: int = 8, 
                          interval: int = 1) -> List["StockIntradayPrice"]:
        """
        Get the latest price records for a stock.
        
        Args:
            session: Database session
            stock_id: Stock ID
            hours: Number of hours to look back
            interval: Time interval in minutes
            
        Returns:
            List of price records, most recent first
        """
        end_time = get_current_datetime()
        start_time = end_time - timedelta(hours=hours)
        
        return session.query(cls).filter(
            and_(
                cls.stock_id == stock_id,
                cls.timestamp >= start_time,
                cls.timestamp <= end_time,
                cls.interval == interval
            )
        ).order_by(cls.timestamp.desc()).all()
        
    @classmethod
    def get_by_id(cls, session: Session, price_id: int) -> Optional["StockIntradayPrice"]:
        """
        Get an intraday price record by ID.
        
        Args:
            session: Database session
            price_id: Price record ID to retrieve
            
        Returns:
            StockIntradayPrice instance if found, None otherwise
        """
        return session.query(cls).get(price_id)