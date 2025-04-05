"""Daily price model.

This module defines the StockDailyPrice model which represents end-of-day stock price
data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    Column,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, relationship, validates

from app.models.base import Base
from app.models.enums import PriceSource
from app.utils.errors import StockPriceError
from app.utils.validators import (
    validate_enum_value,
    validate_non_negative_value,
    validate_not_future_date,
)

if TYPE_CHECKING:
    from datetime import date

    from app.models.stock import Stock


class StockDailyPrice(Base):
    """Model representing daily stock price data.

    Stores end-of-day price information for stocks, including open, high, low,
    close prices and trading volume. Each record represents a single trading day
    for a specific stock.

    Attributes:
        id: Unique identifier for the price record
        stock_id: Foreign key to the associated Stock
        price_date: The trading date this price data represents
        open_price: Opening price for the trading day
        high_price: Highest price during the trading day
        low_price: Lowest price during the trading day
        close_price: Closing price for the trading day
        adj_close: Adjusted closing price (accounts for dividends, splits)
        volume: Number of shares traded during the day
        source: Source of this price data
        stock: Relationship to the parent Stock

    Properties:
        change: Price change from open to close (close_price - open_price)
        change_percent: Percentage price change from open to close
        is_real_data: Whether price data is from a real source (not simulated)
        trading_range: Trading range for the day (high_price - low_price)
        trading_range_percent: Trading range as a percentage of low price

    """

    #
    # SQLAlchemy configuration
    #
    __tablename__: str = "stock_daily_prices"

    # Constraints
    __table_args__: tuple[UniqueConstraint] = (
        UniqueConstraint("stock_id", "price_date", name="uix_stock_daily_date"),
    )

    #
    # Column definitions
    #

    # Foreign keys and date
    stock_id: Mapped[int] = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    price_date: Mapped[date] = Column(Date, nullable=False)

    # Price data
    open_price: Mapped[float | None] = Column(Float, nullable=True)
    high_price: Mapped[float | None] = Column(Float, nullable=True)
    low_price: Mapped[float | None] = Column(Float, nullable=True)
    close_price: Mapped[float | None] = Column(Float, nullable=True)
    adj_close: Mapped[float | None] = Column(Float, nullable=True)
    volume: Mapped[int | None] = Column(Integer, nullable=True)

    # Metadata
    source: Mapped[str] = Column(
        String(20),
        default=PriceSource.HISTORICAL.value,
        nullable=False,
    )

    #
    # Relationships
    #
    stock: Mapped[Stock] = relationship("Stock", back_populates="daily_prices")

    #
    # Magic methods
    #
    def __repr__(self) -> str:
        """Return string representation of the StockDailyPrice object."""
        return (
            f"<StockDailyPrice(id={self.id}, stock_id={self.stock_id}, "
            f"date={self.price_date}, close={self.close_price}, "
            f"source={self.source})>"
        )

    #
    # Validation methods
    #
    @validates("source")
    def validate_source(self, key: str, source: str) -> str:
        """Validate price source.

        Args:
            key: The attribute name being validated
            source: The source value to validate

        Returns:
            The validated source value

        Raises:
            StockPriceError: If the source value is not valid

        """
        return validate_enum_value(
            value=source,
            enum_class=PriceSource,
            error_class=StockPriceError,
            key=key,
            error_attr="INVALID_SOURCE",
        )

    @validates("price_date")
    def validate_price_date(self, key: str, price_date: date) -> date:
        """Validate price date is not in the future.

        Args:
            key: The attribute name being validated
            price_date: The date value to validate

        Returns:
            The validated date value

        Raises:
            StockPriceError: If the date is in the future

        """
        return validate_not_future_date(
            date_value=price_date,
            error_class=StockPriceError,
            key=key,
            error_attr="FUTURE_DATE",
        )

    @validates("high_price", "low_price", "open_price", "close_price", "adj_close")
    def validate_prices(self, key: str, value: float) -> float:
        """Validate price values.

        Ensures prices are non-negative and maintains logical relationships
        between high and low prices.

        Args:
            key: The attribute name being validated
            value: The price value to validate

        Returns:
            The validated price value

        Raises:
            StockPriceError: If the price value is invalid

        """
        # First validate that the price is non-negative
        value = validate_non_negative_value(
            value=value,
            error_class=StockPriceError,
            key=key,
            error_attr="NEGATIVE_PRICE",
        )

        # Check high_price >= low_price if both are being set
        if (
            key == "high_price"
            and value is not None
            and self.low_price is not None
            and value < self.low_price
        ):
            raise StockPriceError(
                StockPriceError.HIGH_LOW_PRICE.format(key=key, value=value),
            )

        if (
            key == "low_price"
            and value is not None
            and self.high_price is not None
            and value > self.high_price
        ):
            raise StockPriceError(
                StockPriceError.LOW_HIGH_PRICE.format(key=key, value=value),
            )

        return value

    #
    # Properties
    #
    @property
    def change(self) -> float | None:
        """Calculate the change in price from open to close."""
        return (
            None
            if self.open_price is None or self.close_price is None
            else self.close_price - self.open_price
        )

    @property
    def change_percent(self) -> float | None:
        """Calculate the percentage change from open to close."""
        return (
            None
            if self.open_price is None
            or self.close_price is None
            or self.open_price == 0
            else (self.close_price - self.open_price) / self.open_price * 100
        )

    @property
    def is_real_data(self) -> bool:
        """Check if the price data is from a real source (not simulated)."""
        return PriceSource.is_real(self.source)

    @property
    def trading_range(self) -> float | None:
        """Calculate the trading range (high - low) for the day."""
        return (
            None
            if self.high_price is None or self.low_price is None
            else self.high_price - self.low_price
        )

    @property
    def trading_range_percent(self) -> float | None:
        """Calculate the trading range as a percentage of the low price."""
        return (
            None
            if self.high_price is None or self.low_price is None or self.low_price == 0
            else (self.high_price - self.low_price) / self.low_price * 100
        )
