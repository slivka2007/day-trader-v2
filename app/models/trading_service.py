"""Trading Service model.

This model represents a trading service that can buy and sell stocks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, relationship, validates

from app.models.base import Base
from app.models.enums import ServiceState, TradingMode
from app.utils.constants import TradingServiceConstants
from app.utils.errors import TradingServiceError

if TYPE_CHECKING:
    from app.models.stock import Stock
    from app.models.trading_transaction import TradingTransaction
    from app.models.user import User


class TradingService(Base):
    """Model representing a stock trading service.

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

    __tablename__: str = "trading_services"

    # Constants
    MAX_ALLOCATION_PERCENT: float = TradingServiceConstants.MAX_ALLOCATION_PERCENT

    id: Mapped[int] = Column(Integer, primary_key=True)
    user_id: Mapped[int] = Column(Integer, ForeignKey("users.id"), nullable=False)
    stock_id: Mapped[int | None] = Column(
        Integer,
        ForeignKey("stocks.id"),
        nullable=True,
    )
    name: Mapped[str] = Column(String(100), nullable=False)
    description: Mapped[str | None] = Column(Text, nullable=True)
    stock_symbol: Mapped[str] = Column(String(10), nullable=False)
    state: Mapped[str] = Column(
        String(20),
        default=ServiceState.INACTIVE.value,
        nullable=False,
    )
    mode: Mapped[str] = Column(
        String(20),
        default=TradingMode.BUY.value,
        nullable=False,
    )
    is_active: Mapped[bool] = Column(Boolean, default=True, nullable=False)

    # Financial configuration
    initial_balance = Column(Numeric(precision=18, scale=2), nullable=False)
    current_balance = Column(Numeric(precision=18, scale=2), nullable=False)
    minimum_balance = Column(Numeric(precision=18, scale=2), default=0, nullable=False)
    allocation_percent = Column(
        Numeric(precision=18, scale=2),
        default=0.5,
        nullable=False,
    )

    # Strategy configuration
    buy_threshold = Column(Numeric(precision=18, scale=2), default=3.0, nullable=False)
    sell_threshold = Column(Numeric(precision=18, scale=2), default=2.0, nullable=False)
    stop_loss_percent = Column(
        Numeric(precision=18, scale=2),
        default=5.0,
        nullable=False,
    )
    take_profit_percent = Column(
        Numeric(precision=18, scale=2),
        default=10.0,
        nullable=False,
    )

    # Statistics
    current_shares = Column(Integer, nullable=False, default=0)
    buy_count = Column(Integer, nullable=False, default=0)
    sell_count = Column(Integer, nullable=False, default=0)
    total_gain_loss = Column(Numeric(precision=18, scale=2), nullable=False, default=0)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="services")
    stock: Mapped[Stock | None] = relationship("Stock", back_populates="services")
    transactions: Mapped[list[TradingTransaction]] = relationship(
        "TradingTransaction",
        back_populates="service",
        cascade="all, delete-orphan",
    )

    # Validations
    @validates("stock_symbol")
    def validate_stock_symbol(self, key: str, symbol: str) -> str:
        """Validate stock symbol."""
        if not symbol:
            raise TradingServiceError(
                TradingServiceError.SYMBOL_REQUIRED.format(key, symbol),
            )
        return symbol.strip().upper()

    @validates("state")
    def validate_state(self, key: str, state: str) -> str:
        """Validate service state."""
        if state and not ServiceState.is_valid(state):
            raise TradingServiceError(
                TradingServiceError.INVALID_STATE.format(key, state),
            )
        return state

    @validates("mode")
    def validate_mode(self, key: str, mode: str) -> str:
        """Validate trading mode."""
        if mode and not TradingMode.is_valid(mode):
            raise TradingServiceError(
                TradingServiceError.INVALID_MODE.format(key, mode),
            )
        return mode

    @validates("initial_balance")
    def validate_initial_balance(self, key: str, value: float) -> float:
        """Validate initial balance is positive."""
        if value is not None and value <= 0:
            raise TradingServiceError(
                TradingServiceError.INITIAL_BALANCE.format(key, value),
            )
        return value

    @validates("allocation_percent")
    def validate_allocation_percent(self, key: str, value: float) -> float:
        """Validate allocation percent is between 0 and MAX_ALLOCATION_PERCENT."""
        if value is not None and (value < 0 or value > self.MAX_ALLOCATION_PERCENT):
            raise TradingServiceError(
                TradingServiceError.ALLOCATION_PERCENT.format(key, value),
            )
        return value

    def __repr__(self) -> str:
        """Return string representation of the TradingService object."""
        return (
            f"<TradingService(id={self.id}, user_id={self.user_id}, "
            f"stock_id={self.stock_id}, stock_symbol='{self.stock_symbol}', "
            f"name='{self.name}', description='{self.description}', "
            f"state={self.state}, mode={self.mode}, "
            f"is_active={self.is_active}, "
            f"initial_balance={self.initial_balance}, "
            f"current_balance={self.current_balance}, "
            f"minimum_balance={self.minimum_balance}, "
            f"allocation_percent={self.allocation_percent}, "
            f"buy_threshold={self.buy_threshold}, "
            f"sell_threshold={self.sell_threshold}, "
            f"stop_loss_percent={self.stop_loss_percent}, "
            f"take_profit_percent={self.take_profit_percent}, "
            f"current_shares={self.current_shares}, "
            f"buy_count={self.buy_count}, "
            f"sell_count={self.sell_count}, "
            f"total_gain_loss={self.total_gain_loss}, "
            f"transactions={len(self.transactions)})>"
        )

    # Properties for common conditions and calculations
    @property
    def can_buy(self) -> bool:
        """Check if the service can buy stocks."""
        return (
            self.is_active
            and self.state == ServiceState.ACTIVE.value
            and self.mode == TradingMode.BUY.value
            and self.current_balance > self.minimum_balance
        )

    @property
    def can_sell(self) -> bool:
        """Check if the service can sell stocks."""
        return (
            self.is_active
            and self.state == ServiceState.ACTIVE.value
            and self.mode == TradingMode.SELL.value
            and self.current_shares > 0
        )

    @property
    def is_profitable(self) -> bool:
        """Check if the service is profitable overall."""
        return self.total_gain_loss > 0

    def has_dependencies(self) -> bool:
        """Check if the service has any dependencies.

        Returns:
            True if there are dependencies, False otherwise

        """
        return self.transactions and len(self.transactions) > 0
