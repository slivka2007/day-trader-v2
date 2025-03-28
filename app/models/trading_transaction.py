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

    def complete_transaction(self, session: Session, sale_price: Decimal) -> "TradingTransaction":
        """
        Complete a transaction by selling shares.
        
        Args:
            session: Database session
            sale_price: Price per share for the sale
            
        Returns:
            Updated transaction instance
            
        Raises:
            ValueError: If transaction is already completed
        """
        from app.api.schemas.trading_transaction import transaction_schema
        from app.api.schemas.trading_service import service_schema
        from app.services.events import EventService
        
        try:
            if self.state == TransactionState.CLOSED.value:
                raise ValueError("Transaction is already completed")
            
            if sale_price <= 0:
                raise ValueError("Sale price must be greater than zero")
            
            self.sale_price = sale_price
            self.sale_date = get_current_datetime()
            self.state = TransactionState.CLOSED.value
            self.gain_loss = (self.sale_price - self.purchase_price) * self.shares
            
            service = self.service
            service.current_balance += (self.sale_price * self.shares)
            service.total_gain_loss += self.gain_loss
            service.current_shares -= self.shares
            service.sell_count += 1
            
            if service.current_shares == 0:
                service.mode = TradingMode.BUY.value
            
            session.commit()
            
            # Prepare response data
            transaction_data = transaction_schema.dump(self)
            service_data = service_schema.dump(service)
            
            # Emit WebSocket events
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
            
            return self
        except Exception as e:
            logger.error(f"Error completing transaction: {str(e)}")
            session.rollback()
            raise ValueError(f"Could not complete transaction: {str(e)}")

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
        from app.api.schemas.trading_transaction import transaction_schema
        from app.services.events import EventService
        
        try:
            # Verify service exists
            service = TradingService.get_or_404(session, service_id)
                
            # Validate input
            if shares <= 0:
                raise ValueError("Shares must be greater than zero")
                
            if purchase_price <= 0:
                raise ValueError("Purchase price must be greater than zero")
                
            total_cost = shares * purchase_price
            if total_cost > service.current_balance:
                raise ValueError(f"Insufficient funds. Required: ${total_cost:.2f}, Available: ${service.current_balance:.2f}")
            
            if not service.can_buy:
                raise ValueError(f"Service is not in a state that allows buying (current state: {service.state})")
            
            # Find stock if it exists
            stock = Stock.get_by_symbol(session, stock_symbol)
            stock_id = stock.id if stock else None
            
            # Create transaction
            transaction_data = {
                'service_id': service_id,
                'stock_id': stock_id,
                'stock_symbol': stock_symbol.upper(),
                'shares': shares,
                'purchase_price': purchase_price,
                'state': TransactionState.OPEN.value,
                'purchase_date': get_current_datetime()
            }
            
            transaction = cls.from_dict(transaction_data)
            session.add(transaction)
            
            # Update service
            service.current_balance -= total_cost
            service.current_shares += shares
            service.buy_count += 1
            service.mode = TradingMode.SELL.value
            
            session.commit()
            
            # Prepare response data
            transaction_data = transaction_schema.dump(transaction)
            
            # Emit WebSocket event
            EventService.emit_transaction_update(
                action='created',
                transaction_data=transaction_data,
                service_id=service_id
            )
            
            return transaction
        except Exception as e:
            logger.error(f"Error creating buy transaction: {str(e)}")
            session.rollback()
            raise ValueError(f"Could not create buy transaction: {str(e)}")
    
    def cancel_transaction(self, session: Session, reason: str = "User cancelled") -> "TradingTransaction":
        """
        Cancel a transaction.
        
        Args:
            session: Database session
            reason: Reason for cancellation
            
        Returns:
            Updated transaction instance
            
        Raises:
            ValueError: If the transaction is already completed
        """
        from app.api.schemas.trading_transaction import transaction_schema
        from app.api.schemas.trading_service import service_schema
        from app.services.events import EventService
        
        try:
            if self.state == TransactionState.CLOSED.value:
                raise ValueError("Cannot cancel a completed transaction")
                
            if self.state == TransactionState.CANCELLED.value:
                raise ValueError("Transaction is already cancelled")
                
            self.state = TransactionState.CANCELLED.value
            self.notes = reason
            
            service = self.service
            service.current_balance += (self.purchase_price * self.shares)
            service.current_shares -= self.shares
            
            session.commit()
            
            # Prepare response data
            transaction_data = transaction_schema.dump(self)
            service_data = service_schema.dump(service)
            
            # Emit WebSocket events
            EventService.emit_transaction_update(
                action='cancelled',
                transaction_data=transaction_data,
                service_id=service.id,
                additional_data={'reason': reason}
            )
            
            EventService.emit_service_update(
                action='updated',
                service_data=service_data,
                service_id=service.id
            )
            
            return self
        except Exception as e:
            logger.error(f"Error cancelling transaction: {str(e)}")
            session.rollback()
            raise ValueError(f"Could not cancel transaction: {str(e)}")
    
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
