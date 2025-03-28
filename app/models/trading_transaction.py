"""
Trading Transaction model.

This model represents a stock trading transaction (buy and sell).
"""
import logging
from typing import Optional, TYPE_CHECKING, Dict, Any, List
from decimal import Decimal
from datetime import datetime

from sqlalchemy import Column, ForeignKey, String, Integer, Numeric, DateTime, Boolean, Text, and_
from sqlalchemy.orm import relationship, Mapped, Session, validates
from flask import current_app

from app.models.base import Base
from app.models.enums import TransactionState, TradingMode
from app.utils.current_datetime import get_current_datetime
if TYPE_CHECKING:
    from app.models.stock import Stock
    from app.models.trading_service import TradingService

# Set up logging
logger = logging.getLogger(__name__)

class TradingTransaction(Base):
    """
    Model representing a stock trading transaction.
    
    Stores information about buy and sell transactions, including prices,
    shares, and profit/loss calculations.
    
    Attributes:
        id: Unique identifier for the transaction
        service_id: Foreign key to the related trading service
        stock_id: Foreign key to the stock being traded
        stock_symbol: Symbol of the stock being traded
        shares: Number of shares bought/sold
        state: Transaction state (OPEN, CLOSED, CANCELLED)
        purchase_price: Price per share at purchase
        sale_price: Price per share at sale (null until sold)
        gain_loss: Calculated profit/loss from transaction
        purchase_date: Date/time of purchase
        sale_date: Date/time of sale (null until sold)
        service: Relationship to the trading service
        stock: Relationship to the stock
    """
    __tablename__ = 'trading_transactions'
    
    id = Column(Integer, primary_key=True)
    service_id = Column(Integer, ForeignKey('trading_services.id'), nullable=False)
    stock_id = Column(Integer, ForeignKey('stocks.id'), nullable=True)
    stock_symbol = Column(String(10), nullable=False, index=True)
    shares = Column(Numeric(precision=18, scale=2), nullable=False)
    state = Column(String(20), default=TransactionState.OPEN.value, nullable=False)
    purchase_price = Column(Numeric(precision=18, scale=2), nullable=False)
    sale_price = Column(Numeric(precision=18, scale=2), nullable=True)
    gain_loss = Column(Numeric(precision=18, scale=2), nullable=True)
    purchase_date = Column(DateTime, default=get_current_datetime, nullable=False)
    sale_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Relationships
    service: Mapped["TradingService"] = relationship("TradingService", back_populates="transactions")
    stock: Mapped[Optional["Stock"]] = relationship("Stock", back_populates="transactions")
    
    # Validations
    @validates('stock_symbol')
    def validate_stock_symbol(self, key, symbol):
        """Validate stock symbol."""
        if not symbol:
            raise ValueError("Stock symbol is required")
        return symbol.strip().upper()
    
    @validates('state')
    def validate_state(self, key, state):
        """Validate transaction state."""
        if state and not TransactionState.is_valid(state):
            valid_states = TransactionState.values()
            raise ValueError(f"Invalid transaction state: {state}. Valid states are: {', '.join(valid_states)}")
        return state
    
    @validates('shares')
    def validate_shares(self, key, shares):
        """Validate shares amount."""
        if shares is not None and float(shares) <= 0:
            raise ValueError("Shares must be greater than zero")
        return shares
    
    def __repr__(self) -> str:
        """String representation of the TradingTransaction object."""
        return f"<TradingTransaction(id={self.id}, symbol='{self.stock_symbol}', shares={self.shares})>"
    
    # Business logic methods
    @property
    def is_complete(self) -> bool:
        """Check if the transaction is completed (sold)."""
        return self.state == TransactionState.CLOSED.value

    @property
    def is_profitable(self) -> bool:
        """Check if the transaction is profitable."""
        if not self.is_complete or self.gain_loss is None:
            return False
        return Decimal(str(self.gain_loss)) > 0
    
    @property
    def can_be_cancelled(self) -> bool:
        """Check if the transaction can be cancelled."""
        return TransactionState.can_be_cancelled(self.state)
    
    @property
    def duration_days(self) -> Optional[int]:
        """Get the duration of the transaction in days."""
        if not self.purchase_date:
            return None
            
        end_date = self.sale_date if self.sale_date else get_current_datetime()
        return (end_date - self.purchase_date).days
    
    @property
    def total_cost(self) -> Decimal:
        """Calculate the total cost of the purchase."""
        if self.purchase_price and self.shares:
            return self.purchase_price * self.shares
        return Decimal('0')
    
    @property
    def total_revenue(self) -> Decimal:
        """Calculate the total revenue from the sale."""
        if self.sale_price and self.shares:
            return self.sale_price * self.shares
        return Decimal('0')
    
    @property
    def profit_loss_percent(self) -> float:
        """Calculate the profit/loss as a percentage."""
        if self.purchase_price and self.sale_price and self.purchase_price > 0:
            return float(((self.sale_price - self.purchase_price) / self.purchase_price) * 100)
        return 0.0
    
    def calculate_gain_loss(self) -> Decimal:
        """Calculate the gain/loss amount based on current prices."""
        if self.sale_price and self.purchase_price and self.shares:
            return (self.sale_price - self.purchase_price) * self.shares
        return Decimal('0')
    
    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """
        Update transaction attributes from a dictionary.
        
        Args:
            data: Dictionary with attribute key/value pairs
            
        Returns:
            None
        """
        for key, value in data.items():
            if hasattr(self, key) and key not in ['id', 'created_at', 'updated_at']:
                setattr(self, key, value)
        
        # Recalculate gain/loss if needed
        if 'sale_price' in data and self.sale_price and self.purchase_price:
            self.gain_loss = self.calculate_gain_loss()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert transaction to a dictionary.
        
        Returns:
            Dictionary of transaction attributes
        """
        return {
            'id': self.id,
            'service_id': self.service_id,
            'stock_id': self.stock_id,
            'stock_symbol': self.stock_symbol,
            'shares': float(self.shares) if self.shares else None,
            'state': self.state,
            'purchase_price': float(self.purchase_price) if self.purchase_price else None,
            'sale_price': float(self.sale_price) if self.sale_price else None,
            'gain_loss': float(self.gain_loss) if self.gain_loss else None,
            'purchase_date': self.purchase_date.isoformat() if self.purchase_date else None,
            'sale_date': self.sale_date.isoformat() if self.sale_date else None,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_complete': self.is_complete,
            'is_profitable': self.is_profitable,
            'duration_days': self.duration_days,
            'total_cost': float(self.total_cost) if self.total_cost else 0.0,
            'total_revenue': float(self.total_revenue) if self.total_revenue else 0.0,
            'profit_loss_percent': self.profit_loss_percent
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradingTransaction":
        """
        Create a new transaction instance from a dictionary.
        
        Args:
            data: Dictionary with attribute key/value pairs
            
        Returns:
            New TradingTransaction instance
        """
        return cls(**{k: v for k, v in data.items() if k in [
            'service_id', 'stock_id', 'stock_symbol', 'shares', 'state',
            'purchase_price', 'sale_price', 'gain_loss', 'purchase_date',
            'sale_date', 'notes'
        ]})
    
    @classmethod
    def get_by_service(cls, session: Session, service_id: int, state: Optional[str] = None) -> List["TradingTransaction"]:
        """
        Get transactions for a service.
        
        Args:
            session: Database session
            service_id: Service ID
            state: Optional state filter
            
        Returns:
            List of transactions
        """
        query = session.query(cls).filter(cls.service_id == service_id)
        
        if state:
            if not TransactionState.is_valid(state):
                raise ValueError(f"Invalid transaction state: {state}")
            query = query.filter(cls.state == state)
            
        return query.order_by(cls.purchase_date.desc()).all()

    @classmethod
    def get_open_transactions(cls, session: Session, service_id: Optional[int] = None) -> List["TradingTransaction"]:
        """
        Get all open transactions.
        
        Args:
            session: Database session
            service_id: Optional service ID filter
            
        Returns:
            List of open transactions
        """
        query = session.query(cls).filter(cls.state == TransactionState.OPEN.value)
        
        if service_id is not None:
            query = query.filter(cls.service_id == service_id)
            
        return query.order_by(cls.purchase_date).all()
            
    @classmethod
    def get_by_id(cls, session: Session, transaction_id: int) -> Optional["TradingTransaction"]:
        """
        Get a transaction by ID.
        
        Args:
            session: Database session
            transaction_id: Transaction ID
            
        Returns:
            TradingTransaction instance if found, None otherwise
        """
        return session.query(cls).get(transaction_id)
