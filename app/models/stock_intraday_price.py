"""
Intraday price model.

This model represents intraday (e.g., hourly or minute-by-minute) stock price data.
"""
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, UniqueConstraint, String
from sqlalchemy.orm import relationship, Mapped

from app.models.base import Base
from app.models.enums import PriceSource
if TYPE_CHECKING:
    from app.models.stock import Stock

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
    source = Column(String(20), default=PriceSource.DELAYED, nullable=False)
    
    # Relationship
    stock: Mapped["Stock"] = relationship("Stock", back_populates="intraday_prices")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('stock_id', 'timestamp', 'interval', name='uix_stock_intraday_time'),
    )

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