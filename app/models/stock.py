"""Stock model.

This model represents basic information about stocks, including symbols and names.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, String
from sqlalchemy.orm import Mapped, relationship, validates

from app.models.base import Base
from app.utils.errors import StockError

if TYPE_CHECKING:
    from app.models.stock_daily_price import StockDailyPrice
    from app.models.stock_intraday_price import StockIntradayPrice
    from app.models.trading_service import TradingService
    from app.models.trading_transaction import TradingTransaction


class Stock(Base):
    """Model representing a stock entity.

    Stores basic information about stocks including symbol and name,
    with relationships to price history data and trading activities.

    Attributes:
        id: Unique identifier for the stock
        symbol: The ticker symbol of the stock (unique)
        name: Full company/entity name of the stock
        is_active: Whether the stock is actively traded
        sector: Industry sector the stock belongs to
        description: Brief description of the company/stock
        daily_prices: Relationship to daily price history
        intraday_prices: Relationship to intraday price history
        services: Services trading this stock
        transactions: Transactions for this stock

    """

    __tablename__: str = "stocks"

    # Constants
    MAX_SYMBOL_LENGTH: int = 10

    # Basic information
    symbol: Mapped[str] = Column(
        String(MAX_SYMBOL_LENGTH),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str | None] = Column(String(200), nullable=True)
    is_active: Mapped[bool] = Column(Boolean, default=True, nullable=False)
    sector: Mapped[str | None] = Column(String(100), nullable=True)
    description: Mapped[str | None] = Column(String(1000), nullable=True)

    # Relationships
    daily_prices: Mapped[list[StockDailyPrice]] = relationship(
        "StockDailyPrice",
        back_populates="stock",
        cascade="all, delete-orphan",
    )

    intraday_prices: Mapped[list[StockIntradayPrice]] = relationship(
        "StockIntradayPrice",
        back_populates="stock",
        cascade="all, delete-orphan",
    )

    services: Mapped[list[TradingService]] = relationship(
        "TradingService",
        primaryjoin="Stock.id == TradingService.stock_id",
        back_populates="stock",
    )

    transactions: Mapped[list[TradingTransaction]] = relationship(
        "TradingTransaction",
        primaryjoin="Stock.id == TradingTransaction.stock_id",
        back_populates="stock",
    )

    # Validations
    @validates("symbol")
    def validate_symbol(self, symbol: str) -> str:
        """Validate stock symbol."""
        if not symbol:
            raise ValueError(StockError.SYMBOL_REQUIRED)

        # Convert to uppercase
        symbol: str = symbol.strip().upper()

        if len(symbol) > self.MAX_SYMBOL_LENGTH:
            raise ValueError(StockError.SYMBOL_LENGTH.format(self.MAX_SYMBOL_LENGTH))

        return symbol

    def __repr__(self) -> str:
        """Return string representation of the Stock object."""
        return f"<Stock(id={self.id}, symbol='{self.symbol}', name='{self.name}')>"

    # Simple intrinsic business logic
    def has_dependencies(self) -> bool:
        """Check if the stock has any dependencies.

        Returns:
            True if stock has dependencies, False otherwise

        """
        return (self.services is not None and len(self.services) > 0) or (
            self.transactions is not None and len(self.transactions) > 0
        )
