"""Intraday price model.

This module defines the StockIntradayPrice model which represents intraday
(e.g., hourly or minute-by-minute) stock price data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, relationship, validates

from app.models.base import Base
from app.models.enums import IntradayInterval, PriceSource
from app.utils.errors import StockPriceError
from app.utils.validators import (
    validate_enum_value,
    validate_non_negative_value,
    validate_not_future_datetime,
)

if TYPE_CHECKING:
    from datetime import datetime

    from app.models.stock import Stock


class StockIntradayPrice(Base):
    """Model representing intraday stock price data.

    Stores price information for stocks during the trading day, including timestamp,
    open, high, low, close prices and trading volume. Each record represents a single
    time interval (e.g., minute, 5 minutes, hour) for a specific stock.

    Attributes:
        id: Unique identifier for the price record
        stock_id: Foreign key to the associated Stock
        timestamp: The date and time this price data represents
        interval: Time interval in minutes (1, 5, 15, 30, 60)
        open_price: Opening price for the time interval
        high_price: Highest price during the time interval
        low_price: Lowest price during the time interval
        close_price: Closing price for the time interval
        volume: Number of shares traded during the interval
        source: Source of this price data
        stock: Relationship to the parent Stock

    Properties:
        change: Price change from open to close (close_price - open_price)
        change_percent: Percentage price change from open to close
        is_real_data: Whether price data is from a real source (not simulated)
        is_delayed: Whether price data is delayed
        is_simulated: Whether price data is simulated
        is_historical: Whether price data is historical
        is_real_time: Whether price data is real-time

    """

    #
    # SQLAlchemy configuration
    #
    __tablename__: str = "stock_intraday_prices"

    # Constraints
    __table_args__: tuple[UniqueConstraint] = (
        UniqueConstraint(
            "stock_id",
            "timestamp",
            "interval",
            name="uix_stock_intraday_time",
        ),
    )

    #
    # Column definitions
    #

    # Foreign keys and timestamp
    stock_id: Mapped[int] = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    timestamp: Mapped[datetime] = Column(DateTime, nullable=False)
    interval: Mapped[int] = Column(
        Integer,
        default=IntradayInterval.ONE_MINUTE.value,
        nullable=False,
    )

    # Price data
    open_price: Mapped[float | None] = Column(Float, nullable=True)
    high_price: Mapped[float | None] = Column(Float, nullable=True)
    low_price: Mapped[float | None] = Column(Float, nullable=True)
    close_price: Mapped[float | None] = Column(Float, nullable=True)
    volume: Mapped[int | None] = Column(Integer, nullable=True)

    # Metadata
    source: Mapped[str] = Column(
        String(20),
        default=PriceSource.DELAYED.value,
        nullable=False,
    )

    #
    # Relationships
    #
    stock: Mapped[Stock] = relationship("Stock", back_populates="intraday_prices")

    #
    # Magic methods
    #
    def __repr__(self) -> str:
        """Return string representation of the StockIntradayPrice object."""
        return (
            f"<StockIntradayPrice(id={self.id}, stock_id={self.stock_id}, "
            f"timestamp={self.timestamp}, interval={self.interval}, "
            f"close={self.close_price}, source={self.source})>"
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

    @validates("timestamp")
    def validate_timestamp(self, key: str, timestamp: datetime) -> datetime:
        """Validate timestamp is not in the future.

        Args:
            key: The attribute name being validated
            timestamp: The timestamp value to validate

        Returns:
            The validated timestamp value

        Raises:
            StockPriceError: If the timestamp is in the future

        """
        return validate_not_future_datetime(
            datetime_value=timestamp,
            error_class=StockPriceError,
            key=key,
            error_attr="FUTURE_TIMESTAMP",
        )

    @validates("interval")
    def validate_interval(self, key: str, interval: int) -> int:
        """Validate interval is one of the valid values.

        Args:
            key: The attribute name being validated
            interval: The interval value to validate

        Returns:
            The validated interval value

        Raises:
            StockPriceError: If the interval is not a valid value

        """
        if not IntradayInterval.is_valid_interval(interval):
            raise StockPriceError(
                StockPriceError.INVALID_INTERVAL.format(key=key, value=interval),
            )
        return interval

    @validates("high_price", "low_price", "open_price", "close_price")
    def validate_prices(self, key: str, value: float) -> float:
        """Validate price values.

        Ensures prices are non-negative.

        Args:
            key: The attribute name being validated
            value: The price value to validate

        Returns:
            The validated price value

        Raises:
            StockPriceError: If the price value is negative

        """
        return validate_non_negative_value(
            value=value,
            error_class=StockPriceError,
            key=key,
            error_attr="NEGATIVE_PRICE",
        )

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
    def is_delayed(self) -> bool:
        """Check if the price data is delayed."""
        return PriceSource.is_delayed(self.source)

    @property
    def is_simulated(self) -> bool:
        """Check if the price data is simulated."""
        return PriceSource.is_simulated(self.source)

    @property
    def is_historical(self) -> bool:
        """Check if the price data is historical."""
        return PriceSource.is_historical(self.source)

    @property
    def is_real_time(self) -> bool:
        """Check if the price data is real-time."""
        return PriceSource.is_real_time(self.source)

    @property
    def is_valid(self) -> bool:
        """Check if the price data is valid."""
        return PriceSource.is_valid(self.source)
