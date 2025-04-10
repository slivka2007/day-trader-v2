"""Trading Service model.

This module defines the TradingService model which represents an automated
trading service that can buy and sell stocks based on configured parameters
and strategy settings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, relationship, validates

from app.models.base import Base
from app.models.enums import ServiceState, TradingMode
from app.utils.constants import TradingServiceConstants
from app.utils.errors import TradingServiceError
from app.utils.validators import (
    validate_enum_value,
    validate_non_negative_value,
    validate_positive_value,
    validate_range,
    validate_stock_symbol,
)

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
        stock_id: Foreign key to the stock being traded (nullable)
        active_transaction_id: Foreign key to the currently active transaction
        name: Name for the service (max 100 chars)
        description: Optional description of the service
        stock_symbol: Symbol of the stock being traded (max 10 chars)
        state: Current state (ACTIVE, INACTIVE, etc.)
        mode: Current trading mode (BUY, SELL, HOLD)
        is_active: Whether the service is currently active
        initial_balance: Initial funds allocated to the service
        current_balance: Current available funds
        minimum_balance: Minimum balance to maintain (defaults to 0)
        allocation_percent: Percentage of balance to use per trade (defaults to 0.5)
        buy_threshold: Price threshold for buy decisions (defaults to 3.0)
        sell_threshold: Price threshold for sell decisions (defaults to 2.0)
        stop_loss_percent: Stop loss percentage (defaults to 5.0)
        take_profit_percent: Take profit percentage (defaults to 10.0)
        current_shares: Number of shares currently held
        buy_count: Number of completed buy transactions
        sell_count: Number of completed sell transactions
        total_gain_loss: Cumulative profit/loss
        created_at: Timestamp when service was created (inherited from Base)
        updated_at: Timestamp when service was last updated (inherited from Base)
        user: Relationship to the user who owns this service
        stock: Relationship to the stock being traded (optional)
        transactions: Relationship to trading transactions (cascade delete)
        active_transaction: Relationship to the currently active transaction

    Properties:
        can_buy: Whether the service can currently buy stocks
        can_sell: Whether the service can currently sell stocks
        is_profitable: Whether the service has a positive total gain/loss
        has_dependencies: Whether the service has any associated transactions
        has_active_transaction: Whether the service has an active transaction

    """

    #
    # SQLAlchemy configuration
    #
    __tablename__: str = "trading_services"

    #
    # Column definitions
    #

    # Identity and relationships
    id: Mapped[int] = Column(Integer, primary_key=True)
    user_id: Mapped[int] = Column(Integer, ForeignKey("users.id"), nullable=False)
    stock_id: Mapped[int | None] = Column(
        Integer,
        ForeignKey("stocks.id"),
        nullable=True,
    )
    active_transaction_id: Mapped[int | None] = Column(
        Integer,
        ForeignKey("trading_transactions.id"),
        nullable=True,
    )

    # Basic information
    name: Mapped[str] = Column(String(100), nullable=False)
    description: Mapped[str | None] = Column(Text, nullable=True)
    stock_symbol: Mapped[str] = Column(String(10), nullable=False)

    # Service state
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
    initial_balance: Mapped[float] = Column(
        Numeric(precision=18, scale=2),
        nullable=False,
    )
    current_balance: Mapped[float] = Column(
        Numeric(precision=18, scale=2),
        nullable=False,
    )
    minimum_balance: Mapped[float] = Column(
        Numeric(precision=18, scale=2),
        default=0,
        nullable=False,
    )
    allocation_percent: Mapped[float] = Column(
        Numeric(precision=18, scale=2),
        default=0.5,
        nullable=False,
    )

    # Strategy configuration
    buy_threshold: Mapped[float] = Column(
        Numeric(precision=18, scale=2),
        default=3.0,
        nullable=False,
    )
    sell_threshold: Mapped[float] = Column(
        Numeric(precision=18, scale=2),
        default=2.0,
        nullable=False,
    )
    stop_loss_percent: Mapped[float] = Column(
        Numeric(precision=18, scale=2),
        default=5.0,
        nullable=False,
    )
    take_profit_percent: Mapped[float] = Column(
        Numeric(precision=18, scale=2),
        default=10.0,
        nullable=False,
    )

    # Statistics
    current_shares: Mapped[int] = Column(
        Integer,
        nullable=False,
        default=0,
    )
    buy_count: Mapped[int] = Column(
        Integer,
        nullable=False,
        default=0,
    )
    sell_count: Mapped[int] = Column(
        Integer,
        nullable=False,
        default=0,
    )
    total_gain_loss: Mapped[float] = Column(
        Numeric(precision=18, scale=2),
        nullable=False,
        default=0,
    )

    #
    # Relationships
    #
    user: Mapped[User] = relationship("User", back_populates="services")
    stock: Mapped[Stock | None] = relationship("Stock", back_populates="services")
    active_transaction: Mapped[TradingTransaction | None] = relationship(
        "TradingTransaction",
        back_populates="service",
        foreign_keys="TradingService.active_transaction_id",
    )
    transactions: Mapped[list[TradingTransaction]] = relationship(
        "TradingTransaction",
        back_populates="service",
        cascade="all, delete-orphan",
        foreign_keys="TradingTransaction.service_id",
    )

    #
    # Magic methods
    #
    def __repr__(self) -> str:
        """Return string representation of the TradingService object."""
        return (
            f"<TradingService(id={self.id}, name='{self.name}', "
            f"stock_symbol='{self.stock_symbol}', state={self.state}, "
            f"mode={self.mode}, active={self.is_active})>"
        )

    #
    # Validation methods
    #
    @validates("stock_symbol")
    def validate_stock_symbol(self, key: str, symbol: str) -> str:
        """Validate stock symbol.

        Args:
            key: The attribute name being validated
            symbol: The symbol value to validate

        Returns:
            The validated symbol (converted to uppercase)

        Raises:
            TradingServiceError: If the symbol is empty or invalid

        """
        return validate_stock_symbol(
            symbol=symbol,
            error_class=TradingServiceError,
            key=key,
        )

    @validates("state")
    def validate_state(self, key: str, state: str) -> str:
        """Validate service state.

        Args:
            key: The attribute name being validated
            state: The state value to validate

        Returns:
            The validated state value

        Raises:
            TradingServiceError: If the state is not a valid ServiceState value

        """
        return validate_enum_value(
            value=state,
            enum_class=ServiceState,
            error_class=TradingServiceError,
            key=key,
            error_attr="INVALID_STATE",
        )

    @validates("mode")
    def validate_mode(self, key: str, mode: str) -> str:
        """Validate trading mode.

        Args:
            key: The attribute name being validated
            mode: The mode value to validate

        Returns:
            The validated mode value

        Raises:
            TradingServiceError: If the mode is not a valid TradingMode value

        """
        return validate_enum_value(
            value=mode,
            enum_class=TradingMode,
            error_class=TradingServiceError,
            key=key,
            error_attr="INVALID_MODE",
        )

    @validates("initial_balance")
    def validate_initial_balance(self, key: str, value: float) -> float:
        """Validate initial balance is positive.

        Args:
            key: The attribute name being validated
            value: The balance value to validate

        Returns:
            The validated balance value

        Raises:
            TradingServiceError: If the balance is not positive

        """
        return validate_positive_value(
            value=value,
            error_class=TradingServiceError,
            key=key,
            error_attr="INITIAL_BALANCE",
        )

    @validates("current_balance")
    def validate_current_balance(self, key: str, value: float) -> float:
        """Validate current balance is positive.

        Args:
            key: The attribute name being validated
            value: The balance value to validate

        Returns:
            The validated balance value

        Raises:
            TradingServiceError: If the balance is not positive

        """
        return validate_positive_value(
            value=value,
            error_class=TradingServiceError,
            key=key,
            error_attr="CURRENT_BALANCE",
        )

    @validates("minimum_balance")
    def validate_minimum_balance(self, key: str, value: float) -> float:
        """Validate minimum balance is non-negative.

        Args:
            key: The attribute name being validated
            value: The balance value to validate

        Returns:
            The validated balance value

        Raises:
            TradingServiceError: If the balance is negative

        """
        return validate_non_negative_value(
            value=value,
            error_class=TradingServiceError,
            key=key,
            error_attr="MINIMUM_BALANCE",
        )

    @validates("allocation_percent")
    def validate_allocation_percent(self, key: str, value: float) -> float:
        """Validate allocation percent is within the allowed range.

        Args:
            key: The attribute name being validated
            value: The allocation percent to validate

        Returns:
            The validated allocation percent

        Raises:
            TradingServiceError: If the allocation percent is outside the allowed range

        """
        return validate_range(
            value=value,
            bounds=(
                TradingServiceConstants.MIN_ALLOCATION_PERCENT,
                TradingServiceConstants.MAX_ALLOCATION_PERCENT,
            ),
            error_class=TradingServiceError,
            key=key,
            error_attr="ALLOCATION_PERCENT",
        )

    #
    # Properties
    #
    @property
    def can_buy(self) -> bool:
        """Check if the service can buy stocks.

        Determines whether the service is in the right state and has
        sufficient funds to execute a buy transaction.

        Returns:
            True if all conditions for buying are met, False otherwise

        """
        return (
            self.is_active
            and self.state == ServiceState.ACTIVE.value
            and self.mode == TradingMode.BUY.value
            and self.current_balance > self.minimum_balance
        )

    @property
    def can_sell(self) -> bool:
        """Check if the service can sell stocks.

        Determines whether the service is in the right state and has
        shares available to execute a sell transaction.

        Returns:
            True if all conditions for selling are met, False otherwise

        """
        return (
            self.is_active
            and self.state == ServiceState.ACTIVE.value
            and self.mode == TradingMode.SELL.value
            and self.current_shares > 0
        )

    @property
    def is_profitable(self) -> bool:
        """Check if the service is profitable overall.

        Returns:
            True if the service has a positive total gain/loss, False otherwise

        """
        return self.total_gain_loss > 0

    @property
    def has_dependencies(self) -> bool:
        """Check if the service has any dependencies.

        Determines whether there are transactions associated with this service.

        Returns:
            True if there are transactions, False otherwise

        """
        return self.transactions and len(self.transactions) > 0

    @property
    def has_active_transaction(self) -> bool:
        """Check if the service has an active transaction.

        Returns:
            True if there is an active transaction, False otherwise

        """
        return self.active_transaction_id is not None
