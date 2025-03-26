"""
Stock model.

This model represents basic information about stocks, including symbols and names.
"""
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import Column, String, Boolean
from sqlalchemy.orm import relationship, Mapped

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.daily_price_model import DailyPrice
    from app.models.intraday_price_model import IntradayPrice
    from app.models.stock_service_model import StockService
    from app.models.stock_transaction_model import StockTransaction

class Stock(Base):
    """
    Model representing a stock entity.
    
    Stores basic information about stocks including symbol and name,
    with relationships to price history data and trading activities.
    
    Attributes:
        id: Unique identifier for the stock
        symbol: The ticker symbol of the stock (unique)
        name: Full company/entity name of the stock
        is_active: Whether the stock is actively traded
        sector: Industry sector the stock belongs to
        description: Brief description of the company/stock
        daily_prices: Relationship to daily price history
        intraday_prices: Relationship to intraday price history
        services: Services trading this stock
        transactions: Transactions for this stock
    """
    __tablename__ = 'stocks'
    
    # Basic information
    symbol = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    sector = Column(String(100), nullable=True)
    description = Column(String(1000), nullable=True)
    
    # Relationships
    daily_prices: Mapped[List["DailyPrice"]] = relationship(
        "DailyPrice", 
        back_populates="stock",
        cascade="all, delete-orphan"
    )
    
    intraday_prices: Mapped[List["IntradayPrice"]] = relationship(
        "IntradayPrice", 
        back_populates="stock",
        cascade="all, delete-orphan"
    )
    
    services: Mapped[List["StockService"]] = relationship(
        "StockService",
        primaryjoin="Stock.id == StockService.stock_id",
        back_populates="stock"
    )
    
    transactions: Mapped[List["StockTransaction"]] = relationship(
        "StockTransaction",
        primaryjoin="Stock.id == StockTransaction.stock_id",
        back_populates="stock"
    )

    def __repr__(self) -> str:
        """String representation of the Stock object."""
        return f"<Stock(id={self.id}, symbol='{self.symbol}', name='{self.name}')>"
