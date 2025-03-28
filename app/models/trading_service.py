"""
Trading Service model.

This model represents a trading service that can buy and sell stocks.
"""
import logging
from typing import List, Optional, TYPE_CHECKING, Dict, Any, Union, Set
from decimal import Decimal

from sqlalchemy import Column, ForeignKey, String, Integer, Numeric, DateTime, Boolean, Text, Enum, and_
from sqlalchemy.orm import relationship, Mapped, Session, validates
from sqlalchemy.sql import func
from flask import current_app

from app.models.base import Base
from app.models.enums import ServiceState, TradingMode
from app.utils.current_datetime import get_current_datetime
if TYPE_CHECKING:
    from app.models.stock import Stock
    from app.models.trading_transaction import TradingTransaction
    from app.models.user import User

# Set up logging
logger = logging.getLogger(__name__)

class TradingService(Base):
    """
    Model representing a stock trading service.
    
    Manages the trading of a specific stock, tracking balance, shares, and performance.
    
    Attributes:
        id: Unique identifier for the service
        user_id: Foreign key to the user who owns this service
        stock_id: Foreign key to the stock being traded
        stock_symbol: Symbol of the stock being traded
        name: Optional name for the service
        initial_balance: Initial funds allocated to the service
        current_balance: Current available funds
        total_gain_loss: Cumulative profit/loss
        current_shares: Number of shares currently held
        state: Current state (ACTIVE, INACTIVE, etc.)
        mode: Current trading mode (BUY, SELL, HOLD)
        buy_count: Number of completed buy transactions
        sell_count: Number of completed sell transactions
        user: Relationship to the user who owns this service
        stock: Relationship to the stock being traded
        transactions: Relationship to trading transactions
    """
    __tablename__ = 'trading_services'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    stock_id = Column(Integer, ForeignKey('stocks.id'), nullable=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    stock_symbol = Column(String(10), nullable=False)
    state = Column(String(20), default=ServiceState.INACTIVE.value, nullable=False)
    mode = Column(String(20), default=TradingMode.BUY.value, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Financial configuration
    initial_balance = Column(Numeric(precision=18, scale=2), nullable=False)
    current_balance = Column(Numeric(precision=18, scale=2), nullable=False)
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
    user: Mapped["User"] = relationship("User", back_populates="services")
    stock: Mapped[Optional["Stock"]] = relationship("Stock", back_populates="services")
    transactions: Mapped[List["TradingTransaction"]] = relationship("TradingTransaction", back_populates="service", cascade="all, delete-orphan")
    
    # Validations
    @validates('stock_symbol')
    def validate_stock_symbol(self, key, symbol):
        """Validate stock symbol."""
        if not symbol:
            raise ValueError("Stock symbol is required")
        return symbol.strip().upper()
    
    @validates('state')
    def validate_state(self, key, state):
        """Validate service state."""
        if state and not ServiceState.is_valid(state):
            valid_states = ServiceState.values()
            raise ValueError(f"Invalid service state: {state}. Valid states are: {', '.join(valid_states)}")
        return state
    
    @validates('mode')
    def validate_mode(self, key, mode):
        """Validate trading mode."""
        if mode and not TradingMode.is_valid(mode):
            valid_modes = TradingMode.values()
            raise ValueError(f"Invalid trading mode: {mode}. Valid modes are: {', '.join(valid_modes)}")
        return mode
    
    def __repr__(self) -> str:
        """String representation of the TradingService object."""
        return f"<TradingService(id={self.id}, symbol='{self.stock_symbol}', balance={self.current_balance})>"
    
    @property
    def can_buy(self) -> bool:
        """Check if the service can buy stocks."""
        return (
            self.is_active and 
            self.state == ServiceState.ACTIVE.value and
            self.mode == TradingMode.BUY.value and
            self.current_balance > self.minimum_balance
        )
    
    @property
    def can_sell(self) -> bool:
        """Check if the service can sell stocks."""
        return (
            self.is_active and 
            self.state == ServiceState.ACTIVE.value and
            self.mode == TradingMode.SELL.value and
            self.current_shares > 0
        )
    
    @property
    def is_profitable(self) -> bool:
        """Check if the service is profitable overall."""
        return Decimal(str(self.total_gain_loss)) > 0
    
    @property
    def performance_pct(self) -> float:
        """Calculate performance as a percentage of initial balance."""
        if not self.initial_balance:
            return 0.0
        total_value = self.current_balance + (self.current_shares * self.get_current_price())
        return ((total_value - self.initial_balance) / self.initial_balance) * 100
    
    def get_current_price(self) -> float:
        """Get the current price of the configured stock."""
        # Get the latest price from the stock model if available
        if self.stock and hasattr(self.stock, 'get_latest_price'):
            latest_price = self.stock.get_latest_price()
            if latest_price is not None:
                return latest_price
        
        # Fallback
        return 0.0
    
    @classmethod
    def get_by_user(cls, session: Session, user_id: int) -> List["TradingService"]:
        """
        Get all services for a user.
        
        Args:
            session: Database session
            user_id: User ID
            
        Returns:
            List of services
        """
        return session.query(cls).filter(cls.user_id == user_id).all()
    
    @classmethod
    def get_by_stock(cls, session: Session, stock_symbol: str) -> List["TradingService"]:
        """
        Get all services for a stock.
        
        Args:
            session: Database session
            stock_symbol: Stock symbol
            
        Returns:
            List of services
        """
        return session.query(cls).filter(cls.stock_symbol == stock_symbol.upper()).all()
    
    def update(self, session: Session, data: Dict[str, Any]) -> "TradingService":
        """
        Update service attributes.
        
        Args:
            session: Database session
            data: Dictionary of attributes to update
            
        Returns:
            Updated service instance
            
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
        
        # Use the update_from_dict method from Base
        updated = self.update_from_dict(data, allowed_fields)
        
        # Only emit event if something was updated
        if updated:
            session.commit()
            
            try:
                # Prepare response data
                service_data = service_schema.dump(self)
                
                # Emit WebSocket event
                EventService.emit_service_update(
                    action='updated',
                    service_data=service_data,
                    service_id=self.id
                )
            except Exception as e:
                logger.error(f"Error during service update process: {str(e)}")
        
        return self
    
    def change_state(self, session: Session, new_state: str) -> "TradingService":
        """
        Change the service state.
        
        Args:
            session: Database session
            new_state: The new state to set
            
        Returns:
            Updated service instance
            
        Raises:
            ValueError: If the state transition is invalid
        """
        from app.api.schemas.trading_service import service_schema
        from app.services.events import EventService
        
        # Validate state
        if not ServiceState.is_valid(new_state):
            valid_states = ServiceState.values()
            raise ValueError(f"Invalid service state: {new_state}. Valid states are: {', '.join(valid_states)}")
        
        previous_state = self.state
        
        # Only update if state is changing
        if previous_state != new_state:
            self.state = new_state
            self.updated_at = get_current_datetime()
            session.commit()
            
            try:
                # Prepare response data
                service_data = service_schema.dump(self)
                
                # Emit WebSocket event
                EventService.emit_service_update(
                    action='state_changed',
                    service_data=service_data,
                    service_id=self.id
                )
            except Exception as e:
                logger.error(f"Error emitting WebSocket event: {str(e)}")
        
        return self
    
    def toggle_active(self, session: Session) -> "TradingService":
        """
        Toggle the active status of the service.
        
        Args:
            session: Database session
            
        Returns:
            Updated service instance
        """
        from app.api.schemas.trading_service import service_schema
        from app.services.events import EventService
        
        # Toggle active status
        self.is_active = not self.is_active
        self.updated_at = get_current_datetime()
        session.commit()
        
        try:
            # Prepare response data
            service_data = service_schema.dump(self)
            
            # Emit WebSocket event
            EventService.emit_service_update(
                action='toggled',
                service_data=service_data,
                service_id=self.id
            )
        except Exception as e:
            logger.error(f"Error emitting WebSocket event: {str(e)}")
        
        return self
    
    def change_mode(self, session: Session, new_mode: str) -> "TradingService":
        """
        Change the trading mode.
        
        Args:
            session: Database session
            new_mode: The new mode to set
            
        Returns:
            Updated service instance
            
        Raises:
            ValueError: If the mode is invalid
        """
        from app.api.schemas.trading_service import service_schema
        from app.services.events import EventService
        
        # Validate mode
        if not TradingMode.is_valid(new_mode):
            valid_modes = TradingMode.values()
            raise ValueError(f"Invalid trading mode: {new_mode}. Valid modes are: {', '.join(valid_modes)}")
        
        previous_mode = self.mode
        
        # Only update if mode is changing
        if previous_mode != new_mode:
            self.mode = new_mode
            self.updated_at = get_current_datetime()
            session.commit()
            
            try:
                # Prepare response data
                service_data = service_schema.dump(self)
                
                # Emit WebSocket event
                EventService.emit_service_update(
                    action='mode_changed',
                    service_data=service_data,
                    service_id=self.id
                )
            except Exception as e:
                logger.error(f"Error emitting WebSocket event: {str(e)}")
        
        return self
    
    def check_buy_condition(self, current_price: float, historical_prices: List[float] = None) -> Dict[str, Any]:
        """
        Check if the conditions for buying are met.
        
        Args:
            current_price: Current stock price
            historical_prices: List of historical prices for analysis
            
        Returns:
            Dictionary with buy decision information
        """
        if not self.can_buy:
            return {
                'should_buy': False,
                'can_buy': False,
                'reason': 'Service cannot buy at this time'
            }
            
        # Simple threshold-based buy decision
        # In a real implementation, this would include more sophisticated analysis
        if historical_prices and len(historical_prices) >= 2:
            percent_change = ((current_price - historical_prices[-2]) / historical_prices[-2]) * 100
            if percent_change <= -self.buy_threshold:
                return {
                    'should_buy': True,
                    'can_buy': True,
                    'reason': f'Price dropped by {abs(percent_change):.2f}%, which exceeds buy threshold of {self.buy_threshold}%'
                }
                
        return {
            'should_buy': False,
            'can_buy': True,
            'reason': 'Buy conditions not met'
        }
        
    def check_sell_condition(self, current_price: float, historical_prices: List[float] = None) -> Dict[str, Any]:
        """
        Check if the conditions for selling are met.
        
        Args:
            current_price: Current stock price
            historical_prices: List of historical prices for analysis
            
        Returns:
            Dictionary with sell decision information
        """
        if not self.can_sell:
            return {
                'should_sell': False,
                'can_sell': False,
                'reason': 'Service cannot sell at this time'
            }
            
        # Simple threshold-based sell decision
        # In a real implementation, this would include more sophisticated analysis
        if historical_prices and len(historical_prices) >= 2:
            percent_change = ((current_price - historical_prices[-2]) / historical_prices[-2]) * 100
            if percent_change >= self.sell_threshold:
                return {
                    'should_sell': True,
                    'can_sell': True,
                    'reason': f'Price increased by {percent_change:.2f}%, which exceeds sell threshold of {self.sell_threshold}%'
                }
                
        return {
            'should_sell': False,
            'can_sell': True,
            'reason': 'Sell conditions not met'
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
        from app.models import User, Stock
        
        try:
            # Validate required fields
            required_fields = ['name', 'stock_symbol', 'initial_balance']
            for field in required_fields:
                if field not in data or not data[field]:
                    raise ValueError(f"Field '{field}' is required")
            
            # Verify user exists
            user = User.get_or_404(session, user_id)
            
            # Check if stock exists and update stock_id
            stock_symbol = data['stock_symbol'].upper()
            stock = Stock.get_by_symbol(session, stock_symbol)
            if stock:
                data['stock_id'] = stock.id
                
            # Set user_id
            data['user_id'] = user_id
            
            # Create the service
            service = cls.from_dict(data)
            session.add(service)
            session.commit()
            
            # Prepare response data
            service_data = service_schema.dump(service)
            
            # Emit WebSocket event
            EventService.emit_service_update(
                action='created',
                service_data=service_data
            )
            
            return service
        except Exception as e:
            logger.error(f"Error creating trading service: {str(e)}")
            session.rollback()
            raise ValueError(f"Could not create trading service: {str(e)}")
