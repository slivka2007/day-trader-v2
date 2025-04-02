"""Daily price model.

This model represents end-of-day stock price data.
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
from app.utils.current_datetime import get_current_date

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

    """

    __tablename__: str = "stock_daily_prices"

    # Error messages
    ERR_INVALID_SOURCE: str = "Invalid price source: {}"
    ERR_FUTURE_DATE: str = "Price date cannot be in the future: {}"
    ERR_NEGATIVE_PRICE: str = "{} cannot be negative"
    ERR_HIGH_LOW_PRICE: str = "High price cannot be less than low price"
    ERR_LOW_HIGH_PRICE: str = "Low price cannot be greater than high price"

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

    # Relationship
    stock: Mapped[Stock] = relationship("Stock", back_populates="daily_prices")

    # Constraints
    __table_args__: tuple[UniqueConstraint] = (
        UniqueConstraint("stock_id", "price_date", name="uix_stock_daily_date"),
    )

    # Validations
    @validates("source")
    def validate_source(self, source: str) -> str:
        """Validate price source."""
        if source and not PriceSource.is_valid(source):
            raise ValueError(self.ERR_INVALID_SOURCE.format(source))
        return source

    @validates("price_date")
    def validate_price_date(self, price_date: date) -> date:
        """Validate price date is not in the future."""
        if price_date and price_date > get_current_date():
            raise ValueError(self.ERR_FUTURE_DATE.format(price_date))
        return price_date

    @validates("high_price", "low_price", "open_price", "close_price", "adj_close")
    def validate_prices(self, _key: str, value: float) -> float:
        """Validate price values."""
        if value is not None and value < 0:
            raise ValueError(self.ERR_NEGATIVE_PRICE.format(_key))

        # Check high_price >= low_price if both are being set
        if (
            _key == "high_price"
            and value is not None
            and self.low_price is not None
            and value < self.low_price
        ):
            raise ValueError(self.ERR_HIGH_LOW_PRICE)

        if (
            _key == "low_price"
            and value is not None
            and self.high_price is not None
            and value > self.high_price
        ):
            raise ValueError(self.ERR_LOW_HIGH_PRICE)

        return value

    def __repr__(self) -> str:
        """Return string representation of the StockDailyPrice object."""
        return (
            f"<StockDailyPrice(id={self.id}, stock_id={self.stock_id}, "
            f"date={self.price_date})>"
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

    def is_real_data(self) -> bool:
        """Check if the price data is from a real source (not simulated)."""
        return PriceSource.is_real(self.source)
