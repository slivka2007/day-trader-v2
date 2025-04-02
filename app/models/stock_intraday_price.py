"""Intraday price model.

This model represents intraday (e.g., hourly or minute-by-minute) stock price data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

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
from app.models.enums import PriceSource
from app.utils.current_datetime import get_current_datetime

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

    """

    __tablename__: str = "stock_intraday_prices"

    # Error messages
    ERR_INVALID_SOURCE: str = "Invalid price source: {}"
    ERR_FUTURE_TIMESTAMP: str = "Timestamp cannot be in the future: {}"
    ERR_INVALID_INTERVAL: str = "Invalid interval {}. Must be one of: 1, 5, 15, 30, 60"
    VALID_INTERVALS: ClassVar[list[int]] = [1, 5, 15, 30, 60]

    # Foreign keys and timestamp
    stock_id: Mapped[int] = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    timestamp: Mapped[datetime] = Column(DateTime, nullable=False)
    interval: Mapped[int] = Column(Integer, default=1, nullable=False)

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

    # Relationship
    stock: Mapped[Stock] = relationship("Stock", back_populates="intraday_prices")

    # Constraints
    __table_args__: tuple[UniqueConstraint] = (
        UniqueConstraint(
            "stock_id",
            "timestamp",
            "interval",
            name="uix_stock_intraday_time",
        ),
    )

    # Validations
    @validates("source")
    def validate_source(self, source: str) -> str:
        """Validate price source."""
        if source and not PriceSource.is_valid(source):
            raise ValueError(self.ERR_INVALID_SOURCE.format(source))
        return source

    @validates("timestamp")
    def validate_timestamp(self, timestamp: datetime) -> datetime:
        """Validate timestamp is not in the future."""
        if timestamp and timestamp > get_current_datetime():
            raise ValueError(self.ERR_FUTURE_TIMESTAMP.format(timestamp))
        return timestamp

    @validates("interval")
    def validate_interval(self, interval: int) -> int:
        """Validate interval is one of the valid values."""
        if interval not in self.VALID_INTERVALS:
            raise ValueError(self.ERR_INVALID_INTERVAL.format(interval))
        return interval

    def __repr__(self) -> str:
        """Return string representation of the StockIntradayPrice object."""
        return (
            f"<StockIntradayPrice(id={self.id}, stock_id={self.stock_id}, "
            f"timestamp={self.timestamp})>"
        )

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
