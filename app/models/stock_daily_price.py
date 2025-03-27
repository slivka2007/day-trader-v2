"""
Daily price model.

This model represents end-of-day stock price data.
"""
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Column, Integer, Float, Date, ForeignKey, UniqueConstraint, String
from sqlalchemy.orm import relationship, Mapped

from app.models.base import Base
from app.models.enums import PriceSource
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
    source = Column(String(20), default=PriceSource.HISTORICAL, nullable=False)
    
    # Relationship
    stock: Mapped["Stock"] = relationship("Stock", back_populates="daily_prices")
    
    # Constraints
    __table_args__ = (UniqueConstraint('stock_id', 'price_date', name='uix_stock_daily_date'),)

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
