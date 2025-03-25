from sqlalchemy import Column, Integer, Float, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped
from typing import Optional

# Import the shared Base and Stock
from app.models import Base
from app.models.stock_model import Stock

class DailyPrice(Base):
    """
    Model representing daily stock price data.
    
    Stores end-of-day price information for stocks, including open, high, low,
    close prices and trading volume. Each record represents a single trading day
    for a specific stock.
    
    Attributes:
        id: Unique identifier for the price record
        stock_id: Foreign key to the associated Stock
        date: The trading date this price data represents
        open: Opening price for the trading day
        high: Highest price during the trading day
        low: Lowest price during the trading day
        close: Closing price for the trading day
        adj_close: Adjusted closing price (accounts for dividends, splits)
        volume: Number of shares traded during the day
        stock: Relationship to the parent Stock
    """
    __tablename__ = 'daily_prices'
    
    id: int = Column(Integer, primary_key=True)
    stock_id: int = Column(Integer, ForeignKey('stocks.id'), nullable=False)
    date: Date = Column(Date, nullable=False)
    open: Optional[float] = Column(Float)
    high: Optional[float] = Column(Float)
    low: Optional[float] = Column(Float)
    close: Optional[float] = Column(Float)
    adj_close: Optional[float] = Column(Float)
    volume: Optional[int] = Column(Integer)
    stock: Mapped["Stock"] = relationship("Stock", back_populates="daily_prices")
    __table_args__ = (UniqueConstraint('stock_id', 'date', name='uix_stock_date'),)

    def __repr__(self) -> str:
        """String representation of the DailyPrice object."""
        return f"<DailyPrice(id={self.id}, stock_id={self.stock_id}, date={self.date})>"
