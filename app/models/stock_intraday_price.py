"""
Intraday price model.

This model represents intraday (e.g., hourly or minute-by-minute) stock price data.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

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
    from app.models.stock import Stock


class StockIntradayPrice(Base):
    """
    Model representing intraday stock price data.

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

    __tablename__ = "stock_intraday_prices"

    # Foreign keys and timestamp
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    interval = Column(Integer, default=1, nullable=False)

    # Price data
    open_price = Column(Float, nullable=True)
    high_price = Column(Float, nullable=True)
    low_price = Column(Float, nullable=True)
    close_price = Column(Float, nullable=True)
    volume = Column(Integer, nullable=True)

    # Metadata
    source = Column(String(20), default=PriceSource.DELAYED.value, nullable=False)

    # Relationship
    stock: Mapped["Stock"] = relationship("Stock", back_populates="intraday_prices")

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "stock_id", "timestamp", "interval", name="uix_stock_intraday_time"
        ),
    )

    # Validations
    @validates("source")
    def validate_source(self, _key, source) -> str:
        """Validate price source."""
        if source and not PriceSource.is_valid(source):
            valid_sources = PriceSource.values()
            raise ValueError(
                f"Invalid price source: {source}. "
                f"Valid sources are: {', '.join(valid_sources)}"
            )
        return source

    @validates("timestamp")
    def validate_timestamp(self, _key, timestamp) -> datetime:
        """Validate timestamp is not in the future."""
        if timestamp and timestamp > get_current_datetime():
            raise ValueError(f"Timestamp cannot be in the future: {timestamp}")
        return timestamp

    @validates("interval")
    def validate_interval(self, _key, interval) -> int:
        """Validate interval is one of the valid values."""
        if interval not in [1, 5, 15, 30, 60]:
            raise ValueError(
                f"Invalid interval {interval}. Must be one of: 1, 5, 15, 30, 60"
            )
        return interval

    def __repr__(self) -> str:
        """String representation of the StockIntradayPrice object."""
        return (
            f"<StockIntradayPrice(id={self.id}, stock_id={self.stock_id}, "
            f"timestamp={self.timestamp})>"
        )

    @property
    def change(self) -> Optional[float]:
        """Calculate the change in price from open to close."""
        attr = self.__dict__
        open_price = attr.get("open_price")
        close_price = attr.get("close_price")
        if open_price is None or close_price is None:
            return None
        return float(close_price - open_price)

    @property
    def change_percent(self) -> Optional[float]:
        """Calculate the percentage change from open to close."""
        attr = self.__dict__
        open_price = attr.get("open_price")
        close_price = attr.get("close_price")
        if open_price is None or close_price is None or float(open_price) == 0:
            return None
        return float((close_price - open_price) / open_price * 100)

    @property
    def is_real_data(self) -> bool:
        """Check if the price data is from a real source (not simulated)."""
        source = self.__dict__.get("source")
        if source is None:
            return False
        return bool(PriceSource.is_real(str(source)))
