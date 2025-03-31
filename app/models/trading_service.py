"""
Trading Service model.

This model represents a trading service that can buy and sell stocks.
"""

from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Column, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, relationship, validates

from app.models.base import Base
from app.models.enums import ServiceState, TradingMode

if TYPE_CHECKING:
    from app.models.stock import Stock
    from app.models.trading_transaction import TradingTransaction
    from app.models.user import User


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

    __tablename__ = "trading_services"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=True)
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
    allocation_percent = Column(
        Numeric(precision=18, scale=2), default=0.5, nullable=False
    )

    # Strategy configuration
    buy_threshold = Column(Numeric(precision=18, scale=2), default=3.0, nullable=False)
    sell_threshold = Column(Numeric(precision=18, scale=2), default=2.0, nullable=False)
    stop_loss_percent = Column(
        Numeric(precision=18, scale=2), default=5.0, nullable=False
    )
    take_profit_percent = Column(
        Numeric(precision=18, scale=2), default=10.0, nullable=False
    )

    # Statistics
    current_shares = Column(Integer, nullable=False, default=0)
    buy_count = Column(Integer, nullable=False, default=0)
    sell_count = Column(Integer, nullable=False, default=0)
    total_gain_loss = Column(Numeric(precision=18, scale=2), nullable=False, default=0)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="services")
    stock: Mapped[Optional["Stock"]] = relationship("Stock", back_populates="services")
    transactions: Mapped[List["TradingTransaction"]] = relationship(
        "TradingTransaction", back_populates="service", cascade="all, delete-orphan"
    )

    # Validations
    @validates("stock_symbol")
    def validate_stock_symbol(self, _key, symbol) -> str:
        """Validate stock symbol."""
        if not symbol:
            raise ValueError("Stock symbol is required")
        return symbol.strip().upper()

    @validates("state")
    def validate_state(self, _key, state) -> str:
        """Validate service state."""
        if state and not ServiceState.is_valid(state):
            valid_states = ServiceState.values()
            raise ValueError(
                f"Invalid service state: {state}. "
                f"Valid states are: {', '.join(valid_states)}"
            )
        return state

    @validates("mode")
    def validate_mode(self, _key, mode) -> str:
        """Validate trading mode."""
        if mode and not TradingMode.is_valid(mode):
            valid_modes = TradingMode.values()
            raise ValueError(
                f"Invalid trading mode: {mode}. "
                f"Valid modes are: {', '.join(valid_modes)}"
            )
        return mode

    @validates("initial_balance")
    def validate_initial_balance(self, _key, value) -> float:
        """Validate initial balance is positive."""
        if value is not None and float(value) <= 0:
            raise ValueError("Initial balance must be greater than 0")
        return value

    @validates("allocation_percent")
    def validate_allocation_percent(self, _key, value) -> float:
        """Validate allocation percent is between 0 and 100."""
        if value is not None and (float(value) < 0 or float(value) > 100):
            raise ValueError("Allocation percent must be between 0 and 100")
        return value

    def __repr__(self) -> str:
        """String representation of the TradingService object."""
        return (
            f"<TradingService(id={self.id}, symbol='{self.stock_symbol}', "
            f"balance={self.current_balance})>"
        )

    # Properties for common conditions and calculations
    @property
    def can_buy(self) -> bool:
        """Check if the service can buy stocks."""
        attr = self.__dict__
        return bool(
            attr.get("is_active", False)
            and attr.get("state") == ServiceState.ACTIVE.value
            and attr.get("mode") == TradingMode.BUY.value
            and attr.get("current_balance", 0) > attr.get("minimum_balance", 0)
        )

    @property
    def can_sell(self) -> bool:
        """Check if the service can sell stocks."""
        attr = self.__dict__
        return bool(
            attr.get("is_active", False)
            and attr.get("state") == ServiceState.ACTIVE.value
            and attr.get("mode") == TradingMode.SELL.value
            and attr.get("current_shares", 0) > 0
        )

    @property
    def is_profitable(self) -> bool:
        """Check if the service is profitable overall."""
        total_gain_loss = self.__dict__.get("total_gain_loss", 0)
        return bool(Decimal(str(total_gain_loss)) > 0)

    def has_dependencies(self) -> bool:
        """
        Check if the service has any dependencies.

        Returns:
            True if there are dependencies, False otherwise
        """
        return bool(self.transactions and len(self.transactions) > 0)
