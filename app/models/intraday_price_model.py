from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped
from typing import Optional
from datetime import datetime

# Import the shared Base and Stock
from app.models import Base
from app.models.stock_model import Stock

class IntradayPrice(Base):
    """
    Model representing intraday (within day) stock price data.
    
    Stores price information at specific time intervals within a trading day,
    including open, high, low, close prices and trading volume. Each record
    represents a single time interval for a specific stock.
    
    Attributes:
        id: Unique identifier for the price record
        stock_id: Foreign key to the associated Stock
        timestamp: The exact date and time this price data represents
        open: Opening price for the time interval
        high: Highest price during the time interval
        low: Lowest price during the time interval
        close: Closing price for the time interval
        volume: Number of shares traded during the time interval
        stock: Relationship to the parent Stock
    """
    __tablename__ = 'intraday_prices'
    
    id: int = Column(Integer, primary_key=True)
    stock_id: int = Column(Integer, ForeignKey('stocks.id'), nullable=False)
    timestamp: datetime = Column(DateTime, nullable=False)
    open: Optional[float] = Column(Float)
    high: Optional[float] = Column(Float)
    low: Optional[float] = Column(Float)
    close: Optional[float] = Column(Float)
    volume: Optional[int] = Column(Integer)
    stock: Mapped["Stock"] = relationship("Stock", back_populates="intraday_prices")
    __table_args__ = (UniqueConstraint('stock_id', 'timestamp', name='uix_stock_timestamp'),)

    def __repr__(self) -> str:
        """String representation of the IntradayPrice object."""
        return f"<IntradayPrice(id={self.id}, stock_id={self.stock_id}, timestamp={self.timestamp})>"