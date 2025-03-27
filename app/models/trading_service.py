"""
Trading Service model.

This model represents a trading service that can buy and sell stocks.
"""
from typing import List, Optional, TYPE_CHECKING, Dict, Any, Union
from decimal import Decimal
from datetime import datetime

from sqlalchemy import Column, ForeignKey, String, Integer, Numeric, DateTime, Boolean, Text, Enum
from sqlalchemy.orm import relationship, Mapped, Session
from sqlalchemy.sql import func
from flask import current_app

from app.models.base import Base, TimestampMixin
from app.models.enums import ServiceState, TradingMode

if TYPE_CHECKING:
    from app.models.stock import Stock
    from app.models.trading_transaction import TradingTransaction

class TradingService(Base, TimestampMixin):
    """
    Model representing a stock trading service.
    
    Manages the trading of a specific stock, tracking balance, shares, and performance.
    
    Attributes:
        id: Unique identifier for the service
        stock_id: Foreign key to the stock being traded
        stock_symbol: Symbol of the stock being traded
        name: Optional name for the service
        initial_balance: Initial funds allocated to the service
        current_balance: Current available funds
        total_gain_loss: Cumulative profit/loss
        current_shares: Number of shares currently held
        state: Current state (ACTIVE, INACTIVE, etc.)
        mode: Current trading mode (BUY, SELL, HOLD)
        started_at: When the service was started
        stopped_at: When the service was stopped
        buy_count: Number of completed buy transactions
        sell_count: Number of completed sell transactions
        stock: Relationship to the stock
        transactions: Relationship to transactions
    """
    __tablename__ = 'trading_services'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    stock_symbol = Column(String(10), nullable=False)
    service_state = Column(Enum(ServiceState), default=ServiceState.INACTIVE, nullable=False)
    mode = Column(Enum(TradingMode), default=TradingMode.BUY, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Financial configuration
    initial_balance = Column(Numeric(precision=18, scale=2), nullable=False)
    fund_balance = Column(Numeric(precision=18, scale=2), nullable=False)
    minimum_balance = Column(Numeric(precision=18, scale=2), default=0, nullable=False)
    allocation_percent = Column(Numeric(precision=18, scale=2), default=0.5, nullable=False)
    
    # Strategy configuration
    buy_threshold = Column(Numeric(precision=18, scale=2), default=3.0, nullable=False)
    sell_threshold = Column(Numeric(precision=18, scale=2), default=2.0, nullable=False)
    stop_loss_percent = Column(Numeric(precision=18, scale=2), default=5.0, nullable=False)
    take_profit_percent = Column(Numeric(precision=18, scale=2), default=10.0, nullable=False)
    
    # Statistics
    current_shares = Column(Integer, nullable=False, default=0)
    buy_count = Column(Integer, nullable=False, default=0)
    sell_count = Column(Integer, nullable=False, default=0)
    total_gain_loss = Column(Numeric(precision=18, scale=2), nullable=False, default=0)
    
    # Relationships
    user = relationship("User", back_populates="services")
    transactions = relationship("TradingTransaction", back_populates="service", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        """String representation of the TradingService object."""
        return f"<TradingService(id={self.id}, symbol='{self.stock_symbol}', balance={self.fund_balance})>"
    
    @property
    def can_buy(self) -> bool:
        """Check if the service can buy stocks."""
        return (
            self.is_active and 
            self.service_state == ServiceState.ACTIVE and
            self.mode == TradingMode.BUY and
            self.fund_balance > self.minimum_balance
        )
    
    @property
    def can_sell(self) -> bool:
        """Check if the service can sell stocks."""
        return (
            self.is_active and 
            self.service_state == ServiceState.ACTIVE and
            self.mode == TradingMode.SELL and
            self.current_shares > 0
        )
    
    @property
    def is_profitable(self) -> bool:
        """Check if the service is profitable overall."""
        return self.total_gain_loss > 0
    
    @property
    def performance_pct(self) -> float:
        """Calculate performance as a percentage of initial balance."""
        if not self.initial_balance:
            return 0.0
        total_value = self.fund_balance + (self.current_shares * self.get_current_price())
        return ((total_value - self.initial_balance) / self.initial_balance) * 100
    
    def get_current_price(self) -> float:
        """Get the current price of the configured stock."""
        # This is a placeholder - in a real implementation, this would get the current price
        # from a stock price service or model
        return 0.0
    
    def update(self, session: Session, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update service attributes.
        
        Args:
            session: Database session
            data: Dictionary of attributes to update
            
        Returns:
            Dictionary containing updated service data
            
        Raises:
            ValueError: If invalid data is provided
        """
        from app.api.schemas.trading_service import service_schema
        from app.services.events import EventService
        
        # Define which fields can be updated
        allowed_fields = {
            'name', 'description', 'stock_symbol', 'is_active',
            'minimum_balance', 'allocation_percent', 'buy_threshold',
            'sell_threshold', 'stop_loss_percent', 'take_profit_percent'
        }
        
        # Update fields
        for key, value in data.items():
            if key in allowed_fields and value is not None:
                setattr(self, key, value)
                
        self.updated_at = datetime.utcnow()
        
        try:
            # Emit WebSocket event
            service_data = service_schema.dump(self)
            EventService.emit_service_update(
                action='updated',
                service_data=service_data,
                service_id=self.id
            )
            
            return service_data
            
        except Exception as e:
            current_app.logger.error(f"Error emitting WebSocket event: {str(e)}")
            return service_schema.dump(self)
    
    def change_state(self, session: Session, new_state: ServiceState) -> Dict[str, Any]:
        """
        Change the service state.
        
        Args:
            session: Database session
            new_state: The new state to set
            
        Returns:
            Dictionary containing updated service data
            
        Raises:
            ValueError: If the state transition is invalid
        """
        from app.api.schemas.trading_service import service_schema
        from app.services.events import EventService
        
        previous_state = self.service_state
        
        # Update state
        self.service_state = new_state
        self.updated_at = datetime.utcnow()
        
        try:
            # Emit WebSocket event
            service_data = service_schema.dump(self)
            
            EventService.emit_service_update(
                action='state_changed',
                service_data=service_data,
                service_id=self.id
            )
            
            return {
                'message': f'Service state changed from {previous_state} to {new_state}',
                'service': service_data,
                'previous_state': str(previous_state),
                'new_state': str(new_state)
            }
            
        except Exception as e:
            current_app.logger.error(f"Error emitting WebSocket event: {str(e)}")
            return {
                'message': f'Service state changed from {previous_state} to {new_state}',
                'service': service_schema.dump(self),
                'previous_state': str(previous_state),
                'new_state': str(new_state)
            }
    
    def toggle_active(self, session: Session) -> Dict[str, Any]:
        """
        Toggle the active status of the service.
        
        Args:
            session: Database session
            
        Returns:
            Dictionary containing updated service data
        """
        from app.api.schemas.trading_service import service_schema
        from app.services.events import EventService
        
        # Toggle active status
        self.is_active = not self.is_active
        self.updated_at = datetime.utcnow()
        
        try:
            # Emit WebSocket event
            service_data = service_schema.dump(self)
            
            EventService.emit_service_update(
                action='toggled',
                service_data=service_data,
                service_id=self.id
            )
            
            return service_data
            
        except Exception as e:
            current_app.logger.error(f"Error emitting WebSocket event: {str(e)}")
            return service_schema.dump(self)
    
    def check_buy_condition(self, current_price: float, historical_prices: List[float] = None) -> Dict[str, Any]:
        """
        Check if the service should buy the configured stock.
        
        Args:
            current_price: Current price of the stock
            historical_prices: List of historical prices (optional)
            
        Returns:
            Dictionary containing the decision and relevant information
        """
        if not self.can_buy:
            return {
                'can_buy': False,
                'reason': f"Service cannot buy in current state (state: {self.service_state}, mode: {self.mode})",
                'fund_balance': self.fund_balance,
                'minimum_balance': self.minimum_balance
            }
            
        # Calculate maximum shares that can be purchased
        max_amount = self.fund_balance * self.allocation_percent
        max_shares = max_amount / current_price if current_price > 0 else 0
        
        # TODO: Add actual strategy logic here
        # For now, we always return that the service can buy if it's in the right state
        
        return {
            'can_buy': True,
            'current_price': current_price,
            'max_shares': max_shares,
            'max_amount': max_amount,
            'fund_balance': self.fund_balance,
            'remaining_balance': self.fund_balance - (max_shares * current_price)
        }
    
    def check_sell_condition(self, current_price: float, historical_prices: List[float] = None) -> Dict[str, Any]:
        """
        Check if the service should sell its current holdings.
        
        Args:
            current_price: Current price of the stock
            historical_prices: List of historical prices (optional)
            
        Returns:
            Dictionary containing the decision and relevant information
        """
        if not self.can_sell:
            return {
                'can_sell': False,
                'reason': f"Service cannot sell in current state (state: {self.service_state}, mode: {self.mode})",
                'current_shares': self.current_shares
            }
            
        # Get the latest transaction to check purchase price
        latest_transaction = None
        if self.transactions:
            from app.models.enums import TransactionState
            open_transactions = [t for t in self.transactions if t.state == TransactionState.OPEN]
            if open_transactions:
                latest_transaction = sorted(open_transactions, key=lambda t: t.purchase_date, reverse=True)[0]
        
        if not latest_transaction:
            return {
                'can_sell': False,
                'reason': "No open transactions found",
                'current_shares': self.current_shares
            }
            
        # Calculate potential gain/loss
        purchase_price = float(latest_transaction.purchase_price)
        potential_gain_loss = (current_price - purchase_price) * self.current_shares
        gain_percent = ((current_price - purchase_price) / purchase_price) * 100 if purchase_price > 0 else 0
        
        # Check stop loss
        if gain_percent <= -self.stop_loss_percent:
            return {
                'can_sell': True,
                'reason': f"Stop loss triggered ({gain_percent:.2f}% < -{self.stop_loss_percent:.2f}%)",
                'current_shares': self.current_shares,
                'current_price': current_price,
                'purchase_price': purchase_price,
                'potential_gain_loss': potential_gain_loss,
                'gain_percent': gain_percent
            }
            
        # Check take profit
        if gain_percent >= self.take_profit_percent:
            return {
                'can_sell': True,
                'reason': f"Take profit triggered ({gain_percent:.2f}% > {self.take_profit_percent:.2f}%)",
                'current_shares': self.current_shares,
                'current_price': current_price,
                'purchase_price': purchase_price,
                'potential_gain_loss': potential_gain_loss,
                'gain_percent': gain_percent
            }
            
        # TODO: Add more sophisticated strategy logic here
        
        return {
            'can_sell': False,
            'reason': "Strategy conditions not met",
            'current_shares': self.current_shares,
            'current_price': current_price,
            'purchase_price': purchase_price,
            'potential_gain_loss': potential_gain_loss,
            'gain_percent': gain_percent
        }
    
    @classmethod
    def create_service(cls, session: Session, user_id: int, data: Dict[str, Any]) -> "TradingService":
        """
        Create a new trading service.
        
        Args:
            session: Database session
            user_id: User ID
            data: Service configuration data
            
        Returns:
            The created service instance
            
        Raises:
            ValueError: If required data is missing or invalid
        """
        from app.api.schemas.trading_service import service_schema
        from app.services.events import EventService
        
        # Create the service
        service = cls(
            user_id=user_id,
            name=data['name'],
            stock_symbol=data['stock_symbol'].upper(),
            initial_balance=data['initial_balance'],
            fund_balance=data['initial_balance'],
            minimum_balance=data.get('minimum_balance', 0),
            allocation_percent=data.get('allocation_percent', 0.5),
            description=data.get('description', ''),
            is_active=data.get('is_active', True)
        )
        
        session.add(service)
        session.commit()
        
        try:
            # Emit WebSocket event
            service_data = service_schema.dump(service)
            EventService.emit_service_update(
                action='created',
                service_data=service_data
            )
            
            return service
            
        except Exception as e:
            current_app.logger.error(f"Error emitting WebSocket event: {str(e)}")
            return service
