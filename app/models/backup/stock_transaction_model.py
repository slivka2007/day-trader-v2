"""
Stock transaction model.

This model represents individual buy/sell transactions in the trading system,
tracking price information, dates, and gains/losses.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Column, String, Numeric, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship, Mapped

from app.models.base import Base
from app.models.enums import TransactionState

if TYPE_CHECKING:
    from app.models.stock_service_model import StockService
    from app.models.stock_model import Stock

class StockTransaction(Base):
    """
    Model representing a stock purchase/sale transaction.
    
    Tracks individual buy and sell actions for each service, including
    purchase details, sale details, and gain/loss calculations. Each transaction
    represents a complete buy-sell cycle or an in-progress cycle where the sale
    has not yet occurred.
    
    Attributes:
        id: Unique identifier for the transaction
        service_id: Foreign key to the associated trading service
        stock_id: Optional foreign key to the stock being traded
        stock_symbol: The ticker symbol of the stock traded
        shares: Quantity of shares bought/sold in this transaction
        state: Transaction state (open/closed/cancelled)
        purchase_price: Price per share when purchased
        sale_price: Price per share when sold (null until sold)
        gain_loss: Total profit/loss from this transaction (null until sold)
        purchase_date: When the purchase occurred
        sale_date: When the sale occurred (null until sold)
        service: Relationship to the parent trading service
        stock: Relationship to the stock being traded (if linked)
    """
    __tablename__ = 'trading_transactions'
    
    # Relationship fields
    service_id = Column(Integer, ForeignKey('trading_services.id'), nullable=False)
    stock_id = Column(Integer, ForeignKey('stocks.id'), nullable=True)
    
    # Transaction details
    stock_symbol = Column(String(10), nullable=False, index=True)
    shares = Column(Integer, nullable=False)
    state = Column(String(20), default=TransactionState.OPEN, nullable=False)
    
    # Price information
    purchase_price = Column(Numeric(precision=10, scale=2), nullable=False)
    sale_price = Column(Numeric(precision=10, scale=2), nullable=True)
    gain_loss = Column(Numeric(precision=10, scale=2), nullable=True)
    
    # Timestamps
    purchase_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    sale_date = Column(DateTime, nullable=True)
    
    # Relationships
    service: Mapped["StockService"] = relationship(
        "StockService", 
        back_populates="transactions"
    )
    
    stock: Mapped[Optional["Stock"]] = relationship(
        "Stock",
        foreign_keys=[stock_id],
        lazy="joined"
    )
    
    def __repr__(self) -> str:
        """String representation of the StockTransaction object."""
        return f"<StockTransaction(id={self.id}, symbol='{self.stock_symbol}', shares={self.shares})>"
    
    @property
    def is_complete(self) -> bool:
        """Check if the transaction is complete (sold)."""
        return self.state == TransactionState.CLOSED
    
    @property
    def is_profitable(self) -> bool:
        """Check if the transaction made a profit."""
        return self.is_complete and self.gain_loss > 0
