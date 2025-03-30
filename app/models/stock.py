"""
Stock model.

This model represents basic information about stocks, including symbols and names.
"""
from typing import List, TYPE_CHECKING
from sqlalchemy import Column, String, Boolean
from sqlalchemy.orm import relationship, Mapped, validates

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.stock_daily_price import StockDailyPrice
    from app.models.stock_intraday_price import StockIntradayPrice
    from app.models.trading_service import TradingService
    from app.models.trading_transaction import TradingTransaction

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
    daily_prices: Mapped[List["StockDailyPrice"]] = relationship(
        "StockDailyPrice", 
        back_populates="stock",
        cascade="all, delete-orphan"
    )
    
    intraday_prices: Mapped[List["StockIntradayPrice"]] = relationship(
        "StockIntradayPrice", 
        back_populates="stock",
        cascade="all, delete-orphan"
    )
    
    services: Mapped[List["TradingService"]] = relationship(
        "TradingService",
        primaryjoin="Stock.id == TradingService.stock_id",
        back_populates="stock"
    )
    
    transactions: Mapped[List["TradingTransaction"]] = relationship(
        "TradingTransaction",
        primaryjoin="Stock.id == TradingTransaction.stock_id",
        back_populates="stock"
    )
    
    # Validations
    @validates('symbol')
    def validate_symbol(self, key, symbol):
        """Validate stock symbol."""
        if not symbol:
            raise ValueError("Stock symbol is required")
        
        # Convert to uppercase
        symbol = symbol.strip().upper()
        
        if len(symbol) > 10:
            raise ValueError("Stock symbol must be 10 characters or less")
            
        return symbol

    def __repr__(self) -> str:
        """String representation of the Stock object."""
        return f"<Stock(id={self.id}, symbol='{self.symbol}', name='{self.name}')>"
    
    # Simple intrinsic business logic
    def has_dependencies(self) -> bool:
        """
        Check if the stock has any dependencies.
        
        Returns:
            True if stock has dependencies, False otherwise
        """
        return bool(
            (self.services is not None and len(self.services) > 0) or
            (self.transactions is not None and len(self.transactions) > 0)
        )
