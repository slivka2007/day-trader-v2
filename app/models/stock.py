"""
Stock model.

This model represents basic information about stocks, including symbols and names.
"""
import logging
from typing import List, Optional, TYPE_CHECKING, Dict, Any, Set
from sqlalchemy import Column, String, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, Session, validates
from flask import current_app

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
    
    @classmethod
    def get_by_symbol_or_404(cls, session: Session, symbol: str) -> "Stock":
        """
        Get a stock by its symbol or raise ResourceNotFoundError.
        
        Args:
            session: Database session
            symbol: Stock symbol (case-insensitive)
            
        Returns:
            Stock instance
            
        Raises:
            ResourceNotFoundError: If stock not found
        """
        from app.utils.errors import ResourceNotFoundError
        
        stock = cls.get_by_symbol(session, symbol)
        if not stock:
            raise ResourceNotFoundError('Stock', f"symbol '{symbol.upper()}'")
        return stock

    def update(self, session: Session, data: Dict[str, Any]) -> "Stock":
        """
        Update stock attributes.
        
        Args:
            session: Database session
            data: Dictionary of attributes to update
            
        Returns:
            Updated stock instance
            
        Raises:
            ValueError: If invalid data is provided
        """
        from app.api.schemas.stock import stock_schema
        from app.services.events import EventService
        
        # Define which fields can be updated
        allowed_fields = {
            'name', 'is_active', 'sector', 'description'
        }
        
        # Use the update_from_dict method from Base
        updated = self.update_from_dict(data, allowed_fields)
        
        # Only emit event if something was updated
        if updated:
            session.commit()
            
            # Prepare response data
            try:
                stock_data = stock_schema.dump(self)
                
                # Emit WebSocket event
                EventService.emit(
                    event_type='stock_update',
                    data={
                        'action': 'updated',
                        'stock': stock_data
                    },
                    room=f'stock_{self.symbol}'
                )
            except Exception as e:
                logger.error(f"Error during stock update process: {str(e)}")
        
        return self
    
    @classmethod
    def create_stock(cls, session: Session, data: Dict[str, Any]) -> "Stock":
        """
        Create a new stock.
        
        Args:
            session: Database session
            data: Stock data
            
        Returns:
            The created stock instance
            
        Raises:
            ValueError: If required data is missing or invalid
        """
        from app.api.schemas.stock import stock_schema
        from app.services.events import EventService
        
        # Validate required fields
        if 'symbol' not in data or not data['symbol']:
            raise ValueError("Stock symbol is required")
            
        # Check if symbol already exists
        existing = cls.get_by_symbol(session, data['symbol'])
        if existing:
            raise ValueError(f"Stock with symbol '{data['symbol'].upper()}' already exists")
        
        # Create the stock using from_dict
        try:
            stock = cls.from_dict(data)
            session.add(stock)
            session.commit()
            
            # Prepare response data
            stock_data = stock_schema.dump(stock)
            
            # Emit WebSocket event
            EventService.emit(
                event_type='stock_update',
                data={
                    'action': 'created',
                    'stock': stock_data
                },
                room='stocks'
            )
            
            return stock
        except Exception as e:
            logger.error(f"Error creating stock: {str(e)}")
            session.rollback()
            raise ValueError(f"Could not create stock: {str(e)}")
        
    def change_active_status(self, session: Session, is_active: bool) -> "Stock":
        """
        Change the active status of the stock.
        
        Args:
            session: Database session
            is_active: New active status
            
        Returns:
            Updated stock instance
        """
        from app.api.schemas.stock import stock_schema
        from app.services.events import EventService
        
        # Only update if status is changing
        if self.is_active != is_active:
            self.is_active = is_active
            self.updated_at = get_current_datetime()
            session.commit()
            
            try:
                # Prepare response data
                stock_data = stock_schema.dump(self)
                
                # Emit WebSocket event
                EventService.emit(
                    event_type='stock_update',
                    data={
                        'action': 'status_changed',
                        'stock': stock_data,
                        'is_active': is_active
                    },
                    room=f'stock_{self.symbol}'
                )
            except Exception as e:
                logger.error(f"Error emitting WebSocket event: {str(e)}")
        
        return self
        
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
