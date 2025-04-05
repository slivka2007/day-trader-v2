"""Stock model.

This module defines the Stock model which represents basic information about
traded securities, including symbols, names, and sector data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, String
from sqlalchemy.orm import Mapped, relationship, validates

from app.models.base import Base
from app.utils.constants import StockConstants
from app.utils.errors import StockError
from app.utils.validators import validate_max_length, validate_stock_symbol

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

    Properties:
        has_dependencies: Whether the stock has any trading services or transactions
        has_prices: Whether the stock has any price data (daily or intraday)

    """

    #
    # SQLAlchemy configuration
    #
    __tablename__: str = "stocks"

    #
    # Constants
    #
    MAX_SYMBOL_LENGTH: int = StockConstants.MAX_SYMBOL_LENGTH
    MAX_NAME_LENGTH: int = StockConstants.MAX_NAME_LENGTH
    MAX_SECTOR_LENGTH: int = StockConstants.MAX_SECTOR_LENGTH
    MAX_DESCRIPTION_LENGTH: int = StockConstants.MAX_DESCRIPTION_LENGTH

    #
    # Column definitions
    #

    # Basic information
    symbol: Mapped[str] = Column(
        String(MAX_SYMBOL_LENGTH),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str | None] = Column(String(MAX_NAME_LENGTH), nullable=True)
    is_active: Mapped[bool] = Column(Boolean, default=True, nullable=False)
    sector: Mapped[str | None] = Column(String(MAX_SECTOR_LENGTH), nullable=True)
    description: Mapped[str | None] = Column(
        String(MAX_DESCRIPTION_LENGTH),
        nullable=True,
    )

    #
    # Relationships
    #
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

    #
    # Magic methods
    #
    def __repr__(self) -> str:
        """Return string representation of the Stock object."""
        return (
            f"<Stock(id={self.id}, symbol='{self.symbol}', name='{self.name}', "
            f"active={self.is_active})>"
        )

    #
    # Validation methods
    #
    @validates("symbol")
    def validate_symbol(self, key: str, symbol: str) -> str:
        """Validate stock symbol.

        Args:
            key: The attribute name being validated
            symbol: The symbol value to validate

        Returns:
            The validated symbol (converted to uppercase)

        Raises:
            StockError: If the symbol is invalid, empty, or has an invalid format

        """
        return validate_stock_symbol(
            symbol=symbol,
            error_class=StockError,
            key=key,
            max_length=self.MAX_SYMBOL_LENGTH,
        )

    @validates("name")
    def validate_name(self, key: str, name: str | None) -> str | None:
        """Validate stock name.

        Args:
            key: The attribute name being validated
            name: The name value to validate

        Returns:
            The validated name

        Raises:
            StockError: If the name exceeds the maximum length

        """
        return validate_max_length(
            value=name,
            max_length=self.MAX_NAME_LENGTH,
            error_class=StockError,
            key=key,
            error_attr="NAME_LENGTH",
        )

    @validates("sector")
    def validate_sector(self, key: str, sector: str | None) -> str | None:
        """Validate stock sector.

        Args:
            key: The attribute name being validated
            sector: The sector value to validate

        Returns:
            The validated sector

        Raises:
            StockError: If the sector exceeds the maximum length

        """
        return validate_max_length(
            value=sector,
            max_length=self.MAX_SECTOR_LENGTH,
            error_class=StockError,
            key=key,
            error_attr="SECTOR_LENGTH",
        )

    @validates("description")
    def validate_description(self, key: str, description: str | None) -> str | None:
        """Validate stock description.

        Args:
            key: The attribute name being validated
            description: The description value to validate

        Returns:
            The validated description

        Raises:
            StockError: If the description exceeds the maximum length

        """
        return validate_max_length(
            value=description,
            max_length=self.MAX_DESCRIPTION_LENGTH,
            error_class=StockError,
            key=key,
            error_attr="DESCRIPTION_LENGTH",
        )

    #
    # Properties
    #
    @property
    def has_dependencies(self) -> bool:
        """Check if the stock has any dependencies.

        Dependencies include services using this stock or transactions
        involving this stock.

        Returns:
            True if stock has dependencies, False otherwise

        """
        return (self.services is not None and len(self.services) > 0) or (
            self.transactions is not None and len(self.transactions) > 0
        )

    @property
    def has_prices(self) -> bool:
        """Check if the stock has any price data.

        Checks for both daily and intraday price data.

        Returns:
            True if stock has price data, False otherwise

        """
        return (self.daily_prices is not None and len(self.daily_prices) > 0) or (
            self.intraday_prices is not None and len(self.intraday_prices) > 0
        )
