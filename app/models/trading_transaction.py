"""
Trading Transaction model.

This model represents a stock trading transaction (buy and sell).
"""
from typing import Optional, TYPE_CHECKING
from decimal import Decimal
from datetime import datetime

from sqlalchemy import Column, ForeignKey, String, Integer, Numeric, DateTime, Text
from sqlalchemy.orm import relationship, Mapped, validates

from app.models.base import Base
from app.models.enums import TransactionState
from app.utils.current_datetime import get_current_datetime
if TYPE_CHECKING:
    from app.models.stock import Stock
    from app.models.trading_service import TradingService

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
    
    # Simple, intrinsic properties
    @property
    def is_complete(self) -> bool:
        """Check if the transaction is completed (sold)."""
        return self.state == TransactionState.CLOSED.value  # type: ignore

    @property
    def is_profitable(self) -> bool:
        """Check if the transaction is profitable."""
        if not self.is_complete or self.gain_loss is None:  # type: ignore
            return False
        return Decimal(str(self.gain_loss)) > 0  # type: ignore
    
    @property
    def can_be_cancelled(self) -> bool:
        """Check if the transaction can be cancelled."""
        return TransactionState.can_be_cancelled(self.state)  # type: ignore
    
    def calculate_gain_loss(self) -> Decimal:
        """Calculate the gain/loss amount based on current prices."""
        if self.sale_price and self.purchase_price and self.shares:  # type: ignore
            return (self.sale_price - self.purchase_price) * self.shares  # type: ignore
        return Decimal('0')
