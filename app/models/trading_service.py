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
    
    @validates('initial_balance')
    def validate_initial_balance(self, key, value):
        """Validate initial balance is positive."""
        if value is not None and float(value) <= 0:
            raise ValueError("Initial balance must be greater than 0")
        return value
    
    @validates('allocation_percent')
    def validate_allocation_percent(self, key, value):
        """Validate allocation percent is between 0 and 100."""
        if value is not None and (float(value) < 0 or float(value) > 100):
            raise ValueError("Allocation percent must be between 0 and 100")
        return value
    
    def __repr__(self) -> str:
        """String representation of the TradingService object."""
        return f"<TradingService(id={self.id}, symbol='{self.stock_symbol}', balance={self.current_balance})>"
    
    # Properties for common conditions and calculations
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
    
    def has_dependencies(self) -> bool:
        """
        Check if the service has any dependencies that would prevent deletion.
        
        Returns:
            True if there are dependencies, False otherwise
        """
        return bool(self.transactions and len(self.transactions) > 0)
    
    # Core model methods for trading logic
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
    
    def update_from_data(self, data: Dict[str, Any], allowed_fields: Set[str] = None) -> bool:
        """
        Update model attributes from a dictionary.
        
        Args:
            data: Dictionary of attributes to update
            allowed_fields: Set of field names that are allowed to be updated
            
        Returns:
            True if any attributes were updated, False otherwise
        """
        updated = False
        for key, value in data.items():
            if allowed_fields is not None and key not in allowed_fields:
                continue
            if hasattr(self, key) and getattr(self, key) != value:
                setattr(self, key, value)
                updated = True
        
        if updated:
            self.updated_at = get_current_datetime()
            
        return updated
    
    # Class methods for database queries
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
        
    @classmethod
    def get_by_id(cls, session: Session, service_id: int) -> Optional["TradingService"]:
        """
        Get a trading service by ID.
        
        Args:
            session: Database session
            service_id: Trading service ID to retrieve
            
        Returns:
            TradingService instance if found, None otherwise
        """
        return session.query(cls).get(service_id)
        
    @classmethod
    def get_all(cls, session: Session) -> List["TradingService"]:
        """
        Get all trading services.
        
        Args:
            session: Database session
            
        Returns:
            List of TradingService instances
        """
        return session.query(cls).all()
