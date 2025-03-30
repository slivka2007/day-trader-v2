"""
Daily price model.

This model represents end-of-day stock price data.
"""
from typing import Optional, TYPE_CHECKING, Dict, Any, Set

from sqlalchemy import Column, Integer, Float, Date, ForeignKey, UniqueConstraint, String
from sqlalchemy.orm import relationship, Mapped, validates

from app.models.base import Base
from app.models.enums import PriceSource
from app.utils.current_datetime import get_current_date
if TYPE_CHECKING:
    from app.models.stock import Stock

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
    
    @validates('high_price', 'low_price', 'open_price', 'close_price', 'adj_close')
    def validate_prices(self, key, value):
        """Validate price values."""
        if value is not None and value < 0:
            raise ValueError(f"{key} cannot be negative")
        
        # Check high_price >= low_price if both are being set
        if key == 'high_price' and value is not None and hasattr(self, 'low_price') and self.low_price is not None:
            if value < self.low_price:
                raise ValueError("High price cannot be less than low price")
        
        if key == 'low_price' and value is not None and hasattr(self, 'high_price') and self.high_price is not None:
            if self.high_price < value:
                raise ValueError("Low price cannot be greater than high price")
        
        return value

    def __repr__(self) -> str:
        """String representation of the StockDailyPrice object."""
        return f"<StockDailyPrice(id={self.id}, stock_id={self.stock_id}, date={self.price_date})>"
    
    @property
    def change(self) -> Optional[float]:
        """Calculate the change in price from open to close."""
        attr = self.__dict__
        open_price = attr.get('open_price')
        close_price = attr.get('close_price')
        if open_price is None or close_price is None:
            return None
        return float(close_price - open_price)
    
    @property
    def change_percent(self) -> Optional[float]:
        """Calculate the percentage change from open to close."""
        attr = self.__dict__
        open_price = attr.get('open_price')
        close_price = attr.get('close_price')
        if open_price is None or close_price is None or float(open_price) == 0:
            return None
        return float((close_price - open_price) / open_price * 100)
    
    @property
    def is_real_data(self) -> bool:
        """Check if the price data is from a real source (not simulated)."""
        source = self.__dict__.get('source')
        if source is None:
            return False
        return bool(PriceSource.is_real(str(source)))
    
    def update_from_dict(self, data: Dict[str, Any], allowed_fields: Optional[Set[str]] = None) -> bool:
        """
        Update price record attributes from a dictionary.
        
        Args:
            data: Dictionary with attribute key/value pairs
            allowed_fields: Set of field names that are allowed to be updated
            
        Returns:
            True if any fields were updated, False otherwise
        """
        return super().update_from_dict(data, allowed_fields)
