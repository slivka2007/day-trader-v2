"""
Stock model.

This model represents basic information about stocks, including symbols and names.
"""
import logging
from typing import List, Optional, TYPE_CHECKING, Dict, Any, Set
from sqlalchemy import Column, String, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, Session, validates
from flask import current_app
from sqlalchemy.sql import or_

from app.models.base import Base
from app.utils.current_datetime import get_current_datetime
if TYPE_CHECKING:
    from app.models.stock_daily_price import StockDailyPrice
    from app.models.stock_intraday_price import StockIntradayPrice
    from app.models.trading_service import TradingService
    from app.models.trading_transaction import TradingTransaction

# Set up logging
logger = logging.getLogger(__name__)

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
    
    # Basic model methods - service layer will handle business logic, event emission, etc.
    @classmethod
    def get_by_symbol(cls, session: Session, symbol: str) -> Optional["Stock"]:
        """
        Get a stock by its symbol.
        
        Args:
            session: Database session
            symbol: Stock symbol (case-insensitive)
            
        Returns:
            Stock instance if found, None otherwise
        """
        if not symbol:
            return None
            
        return session.query(cls).filter(cls.symbol == symbol.upper()).first()
    
    def update_from_data(self, data: Dict[str, Any], allowed_fields: Optional[Set[str]] = None) -> bool:
        """
        Update stock attributes directly without committing to the database.
        This is a simplified version for use by the service layer.
        
        Args:
            data: Dictionary of attributes to update
            allowed_fields: Set of field names that are allowed to be updated
                           
        Returns:
            True if any fields were updated, False otherwise
        """
        return self.update_from_dict(data, allowed_fields)
    
    def get_latest_price(self) -> Optional[float]:
        """
        Get the latest price for this stock.
        
        Returns:
            Latest closing price if available, None otherwise
        """
        if not self.daily_prices:
            return None
            
        # Sort prices by date, descending
        sorted_prices = sorted(
            self.daily_prices, 
            key=lambda p: p.price_date,
            reverse=True
        )
        
        # Return the close price of the most recent record
        return sorted_prices[0].close_price if sorted_prices else None
        
    def has_dependencies(self) -> bool:
        """
        Check if the stock has any dependencies that would prevent deletion.
        
        Returns:
            True if stock has dependencies, False otherwise
        """
        return (
            (self.services and len(self.services) > 0) or
            (self.transactions and len(self.transactions) > 0)
        )

    @classmethod
    def get_by_id(cls, session: Session, stock_id: int) -> Optional["Stock"]:
        """
        Get a stock by ID.
        
        Args:
            session: Database session
            stock_id: Stock ID to retrieve
            
        Returns:
            Stock instance if found, None otherwise
        """
        return session.query(cls).get(stock_id)
        
    @classmethod
    def get_all(cls, session: Session) -> List["Stock"]:
        """
        Get all stocks.
        
        Args:
            session: Database session
            
        Returns:
            List of Stock instances
        """
        return session.query(cls).all()
        
    @classmethod
    def search_stocks(cls, session: Session, query: str, limit: int = 10) -> List["Stock"]:
        """
        Search stocks by symbol or name.
        
        Args:
            session: Database session
            query: Search query string
            limit: Maximum number of results to return
            
        Returns:
            List of matching Stock instances
        """
        search_term = f"%{query}%"
        return session.query(cls).filter(
            or_(
                cls.symbol.ilike(search_term),
                cls.name.ilike(search_term)
            )
        ).limit(limit).all()
