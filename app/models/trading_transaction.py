"""
Trading Transaction model.

This model represents a stock trading transaction (buy and sell).
"""
from typing import Optional, TYPE_CHECKING, Dict, Any
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Column, ForeignKey, String, Integer, Numeric, DateTime, Boolean, Text, Enum
from sqlalchemy.orm import relationship, Mapped, Session
from flask import current_app

from app.models.base import Base, TimestampMixin
from app.models.enums import TransactionState, TradingMode

if TYPE_CHECKING:
    from app.models.stock import Stock
    from app.models.trading_service import TradingService

class TradingTransaction(Base, TimestampMixin):
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
    state = Column(Enum(TransactionState), default=TransactionState.OPEN, nullable=False)
    purchase_price = Column(Numeric(precision=18, scale=2), nullable=False)
    sale_price = Column(Numeric(precision=18, scale=2), nullable=True)
    gain_loss = Column(Numeric(precision=18, scale=2), nullable=True)
    purchase_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    sale_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Relationships
    service: Mapped["TradingService"] = relationship("TradingService", back_populates="transactions")
    stock: Mapped[Optional["Stock"]] = relationship("Stock", back_populates="transactions")
    
    def __repr__(self) -> str:
        """String representation of the TradingTransaction object."""
        return f"<TradingTransaction(id={self.id}, symbol='{self.stock_symbol}', shares={self.shares})>"
    
    # Business logic methods
    @property
    def is_complete(self) -> bool:
        """Check if the transaction is completed (sold)."""
        return self.state == TransactionState.CLOSED

    @property
    def is_profitable(self) -> bool:
        """Check if the transaction is profitable."""
        if not self.is_complete or self.gain_loss is None:
            return False
        return self.gain_loss > 0

    def complete_transaction(self, session: Session, sale_price: Decimal) -> Dict[str, Any]:
        """
        Complete a transaction by selling shares.
        
        Args:
            session: Database session
            sale_price: Price per share for the sale
            
        Returns:
            Dictionary containing transaction data
            
        Raises:
            ValueError: If transaction is already completed
        """
        from app.api.schemas.trading_transaction import transaction_schema
        from app.api.schemas.trading_service import service_schema
        from app.services.events import EventService
        
        if self.state == TransactionState.CLOSED:
            raise ValueError("Transaction is already completed")
        
        self.sale_price = sale_price
        self.sale_date = datetime.utcnow()
        self.state = TransactionState.CLOSED
        self.gain_loss = (self.sale_price - self.purchase_price) * self.shares
        
        service = self.service
        service.fund_balance += (self.sale_price * self.shares)
        service.total_gain_loss += self.gain_loss
        service.current_shares -= self.shares
        service.sell_count += 1
        
        if service.current_shares == 0:
            service.mode = TradingMode.BUY
        
        try:
            transaction_data = transaction_schema.dump(self)
            service_data = service_schema.dump(service)
            
            EventService.emit_transaction_update(
                action='completed',
                transaction_data=transaction_data,
                service_id=service.id
            )
            
            EventService.emit_service_update(
                action='updated',
                service_data=service_data,
                service_id=service.id
            )
            
            return transaction_data
            
        except Exception as e:
            current_app.logger.error(f"Error emitting WebSocket events: {str(e)}")
            return transaction_schema.dump(self)

    @classmethod
    def create_buy_transaction(cls, session: Session, service_id: int, stock_symbol: str, 
                              shares: float, purchase_price: float) -> 'TradingTransaction':
        """
        Create a new buy transaction for a trading service.
        
        Args:
            session: Database session
            service_id: Trading service ID
            stock_symbol: Stock symbol to buy
            shares: Number of shares to buy
            purchase_price: Price per share
            
        Returns:
            The created transaction instance
            
        Raises:
            ValueError: If the service doesn't have enough funds or is not in BUY mode
        """
        from app.models.trading_service import TradingService
        from app.models.stock import Stock
        
        service = session.query(TradingService).filter_by(id=service_id).first()
        if not service:
            raise ValueError(f"Trading service with ID {service_id} not found")
            
        total_cost = shares * purchase_price
        if total_cost > service.fund_balance:
            raise ValueError(f"Insufficient funds. Required: ${total_cost:.2f}, Available: ${service.fund_balance:.2f}")
        
        if not service.can_buy:
            raise ValueError(f"Service is not in a state that allows buying (current state: {service.state})")
        
        stock = session.query(Stock).filter_by(symbol=stock_symbol).first()
        stock_id = stock.id if stock else None
        
        transaction = cls(
            service_id=service_id,
            stock_id=stock_id,
            stock_symbol=stock_symbol.upper(),
            shares=shares,
            purchase_price=purchase_price,
            state=TransactionState.OPEN
        )
        
        service.fund_balance -= total_cost
        service.current_shares += shares
        service.buy_count += 1
        
        service.mode = TradingMode.SELL
        
        return transaction
    
    def cancel_transaction(self, session: Session, reason: str = "User cancelled") -> Dict[str, Any]:
        """
        Cancel a transaction.
        
        Args:
            session: Database session
            reason: Reason for cancellation
            
        Returns:
            Dictionary containing transaction data
            
        Raises:
            ValueError: If the transaction is already completed
        """
        from app.api.schemas.trading_transaction import transaction_schema
        from app.services.events import EventService
        
        if self.state == TransactionState.CLOSED:
            raise ValueError("Cannot cancel a completed transaction")
            
        if self.state == TransactionState.CANCELLED:
            raise ValueError("Transaction is already cancelled")
            
        self.state = TransactionState.CANCELLED
        self.notes = reason
        
        service = self.service
        service.fund_balance += (self.purchase_price * self.shares)
        service.current_shares -= self.shares
        
        try:
            transaction_data = transaction_schema.dump(self)
            
            EventService.emit_transaction_update(
                action='cancelled',
                transaction_data=transaction_data,
                service_id=service.id,
                additional_data={'reason': reason}
            )
            
            return transaction_data
            
        except Exception as e:
            current_app.logger.error(f"Error emitting WebSocket events: {str(e)}")
            return transaction_schema.dump(self)
