"""Trading Transaction model.

This module defines the TradingTransaction model which represents buy and sell
transactions for stocks, tracking prices, shares, and profit/loss calculations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, relationship, validates

from app.models.base import Base
from app.models.enums import TransactionState
from app.utils.current_datetime import get_current_datetime
from app.utils.errors import TransactionError
from app.utils.validators import (
    validate_enum_value,
    validate_positive_value,
    validate_stock_symbol,
)

if TYPE_CHECKING:
    from datetime import datetime

    from app.models.stock import Stock
    from app.models.trading_service import TradingService


class TradingTransaction(Base):
    """Model representing a stock trading transaction.

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
        notes: Optional transaction notes
        service: Relationship to the trading service
        stock: Relationship to the stock

    Properties:
        is_complete: Whether the transaction is completed (sold)
        is_profitable: Whether the transaction resulted in a profit
        can_be_cancelled: Whether the transaction can be cancelled
        calculated_gain_loss: Calculated gain/loss based on prices

    """

    #
    # SQLAlchemy configuration
    #
    __tablename__: str = "trading_transactions"

    #
    # Column definitions
    #

    # Identity and relationships
    id: Mapped[int] = Column(Integer, primary_key=True)
    service_id: Mapped[int] = Column(
        Integer,
        ForeignKey("trading_services.id"),
        nullable=False,
    )
    stock_id: Mapped[int] = Column(Integer, ForeignKey("stocks.id"), nullable=True)

    # Transaction details
    stock_symbol: Mapped[str] = Column(String(10), nullable=False, index=True)
    shares: Mapped[float] = Column(Numeric(precision=18, scale=2), nullable=False)
    state: Mapped[str] = Column(
        String(20),
        default=TransactionState.OPEN.value,
        nullable=False,
    )

    # Price information
    purchase_price: Mapped[float] = Column(
        Numeric(precision=18, scale=2),
        nullable=False,
    )
    sale_price: Mapped[float | None] = Column(
        Numeric(precision=18, scale=2),
        nullable=True,
    )
    gain_loss: Mapped[float | None] = Column(
        Numeric(precision=18, scale=2),
        nullable=True,
    )

    # Timestamps
    purchase_date: Mapped[datetime] = Column(
        DateTime,
        default=get_current_datetime,
        nullable=False,
    )
    sale_date: Mapped[datetime | None] = Column(DateTime, nullable=True)

    # Additional information
    notes: Mapped[str | None] = Column(Text, nullable=True)

    #
    # Relationships
    #
    service: Mapped[TradingService] = relationship(
        "TradingService",
        back_populates="transactions",
    )
    stock: Mapped[Stock | None] = relationship("Stock", back_populates="transactions")

    #
    # Magic methods
    #
    def __repr__(self) -> str:
        """Return string representation of the TradingTransaction object."""
        return (
            f"<TradingTransaction(id={self.id}, symbol='{self.stock_symbol}', "
            f"shares={self.shares}, state='{self.state}')>"
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
            TransactionError: If the symbol is empty or invalid

        """
        return validate_stock_symbol(
            symbol=symbol,
            error_class=TransactionError,
            key=key,
        )

    @validates("state")
    def validate_state(self, key: str, state: str) -> str:
        """Validate transaction state.

        Args:
            key: The attribute name being validated
            state: The state value to validate

        Returns:
            The validated state

        Raises:
            TransactionError: If the state is not a valid TransactionState

        """
        return validate_enum_value(
            value=state,
            enum_class=TransactionState,
            error_class=TransactionError,
            key=key,
            error_attr="INVALID_STATE",
        )

    @validates("shares")
    def validate_shares(self, key: str, shares: float) -> float:
        """Validate shares amount.

        Args:
            key: The attribute name being validated
            shares: The number of shares to validate

        Returns:
            The validated shares amount

        Raises:
            TransactionError: If shares is not positive

        """
        return validate_positive_value(
            value=shares,
            error_class=TransactionError,
            key=key,
            error_attr="SHARES_POSITIVE",
        )

    @validates("purchase_price")
    def validate_purchase_price(self, key: str, price: float) -> float:
        """Validate purchase price.

        Args:
            key: The attribute name being validated
            price: The price value to validate

        Returns:
            The validated price

        Raises:
            TransactionError: If price is not positive

        """
        return validate_positive_value(
            value=price,
            error_class=TransactionError,
            key=key,
            error_attr="PRICE_POSITIVE",
        )

    #
    # Properties
    #
    @property
    def is_complete(self) -> bool:
        """Check if the transaction is completed (sold).

        Returns:
            True if the transaction has been closed, False otherwise

        """
        return self.state == TransactionState.CLOSED.value

    @property
    def is_profitable(self) -> bool:
        """Check if the transaction is profitable.

        Returns:
            True if the transaction is complete and has a positive gain, False otherwise

        """
        if not self.is_complete or self.gain_loss is None:
            return False
        return self.gain_loss > 0

    @property
    def can_be_cancelled(self) -> bool:
        """Check if the transaction can be cancelled.

        Returns:
            True if the transaction is in a state that allows cancellation

        """
        return TransactionState.can_be_cancelled(self.state)

    @property
    def calculated_gain_loss(self) -> float:
        """Calculate the gain/loss amount based on current prices.

        Returns:
            The calculated gain or loss amount as a float

        """
        if (
            self.sale_price is not None
            and self.purchase_price is not None
            and self.shares is not None
        ):
            return (self.sale_price - self.purchase_price) * self.shares
        return 0
