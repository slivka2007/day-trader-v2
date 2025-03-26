"""
Stock trading service model.

This model represents a service that trades a specific stock, tracking
its balances, transactions, and operational state.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import Column, String, Numeric, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship, Mapped

from app.models.base import Base
from app.models.enums import ServiceState, TradingMode

if TYPE_CHECKING:
    from app.models.stock_transaction_model import StockTransaction
    from app.models.stock_model import Stock

class StockService(Base):
    """
    Model representing a stock trading service instance.
    
    Stores information about each trading service, including its current state,
    balances, transaction counts, and relationship to transactions. This is the
    core model that tracks the lifecycle of a trading service from creation to
    termination.
    
    Attributes:
        id: Unique identifier for the service
        stock_id: Optional foreign key to the stock being traded
        stock_symbol: The ticker symbol of the stock being traded
        name: Optional name for this service
        initial_balance: The initial funds allocated to the service
        current_balance: The current available funds
        total_gain_loss: The cumulative profit or loss from completed transactions
        current_shares: The number of shares currently held
        state: Service operational state (active/inactive/etc)
        mode: Current trading mode (buy/sell/hold)
        started_at: When the service was last started
        stopped_at: When the service was last stopped
        buy_count: Count of completed buy transactions
        sell_count: Count of completed sell transactions
        transactions: List of transactions associated with this service
        stock: Relationship to the stock being traded (if linked)
    """
    __tablename__ = 'trading_services'
    
    # Identification fields
    stock_id = Column(Integer, ForeignKey('stocks.id'), nullable=True)
    stock_symbol = Column(String(10), nullable=False, index=True)
    name = Column(String(100), nullable=True)
    
    # Balance fields
    initial_balance = Column(Numeric(precision=10, scale=2), nullable=False)
    current_balance = Column(Numeric(precision=10, scale=2), nullable=False)
    total_gain_loss = Column(Numeric(precision=10, scale=2), default=0, nullable=False)
    
    # Position tracking
    current_shares = Column(Integer, default=0, nullable=False)
    
    # Transaction counts
    buy_count = Column(Integer, default=0, nullable=False)
    sell_count = Column(Integer, default=0, nullable=False)

    # Service state tracking
    state = Column(String(20), default=ServiceState.ACTIVE, nullable=False)
    mode = Column(String(10), default=TradingMode.BUY, nullable=False)
    
    # Operation timestamps
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    stopped_at = Column(DateTime, nullable=True)
    
    # Relationships
    transactions: Mapped[List["StockTransaction"]] = relationship(
        "StockTransaction", 
        back_populates="service",
        cascade="all, delete-orphan"
    )
    
    stock: Mapped[Optional["Stock"]] = relationship(
        "Stock",
        foreign_keys=[stock_id],
        lazy="joined"
    )
    
    def __repr__(self) -> str:
        """String representation of the StockService object."""
        return f"<StockService(id={self.id}, symbol='{self.stock_symbol}', state='{self.state}')>"
    
    @property
    def is_active(self) -> bool:
        """Check if the service is in active state."""
        return self.state == ServiceState.ACTIVE
