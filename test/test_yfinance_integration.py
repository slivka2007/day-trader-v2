"""Integration tests for the Yahoo Finance data provider.

This module tests real data retrieval from Yahoo Finance through the
daily_price_service and intraday_price_service.
"""

# ruff: noqa: S101  # Allow assert usage in tests

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from datetime import date, datetime, timedelta

    from sqlalchemy.orm import Session

    from app.models.stock import Stock
    from app.models.stock_daily_price import StockDailyPrice
    from app.models.stock_intraday_price import StockIntradayPrice

from app.models.enums import IntradayInterval, PriceSource
from app.services.daily_price_service import DailyPriceService
from app.services.intraday_price_service import IntradayPriceService
from app.services.stock_service import StockService
from app.utils.current_datetime import TIMEZONE, get_current_date, get_current_datetime
from app.utils.errors import APIError, BusinessLogicError, StockError
from test.utils import create_test_stock

# Set up logger
logger: logging.Logger = logging.getLogger(__name__)


class TestYFinanceIntegration:
    """Integration tests for Yahoo Finance data provider."""

    # Constants
    MAX_ACCEPTABLE_PRICE_AGE_DAYS: int = 5

    @pytest.fixture(autouse=True)
    def setup(self, db_session: Session, **_kwargs: object) -> None:
        """Set up test data and services."""
        self.session: Session = db_session
        test_stock_dict: dict[str, object] = create_test_stock()
        self.test_stock: Stock = StockService.get_by_id(
            self.session,
            test_stock_dict["id"],
        )

        # Create a real stock for testing actual YFinance data
        self.real_stock_symbol: str = "AAPL"
        real_stock: Stock | None = StockService.find_by_symbol(
            self.session,
            self.real_stock_symbol,
        )
        if not real_stock:
            real_stock_data: dict[str, object] = {
                "symbol": self.real_stock_symbol,
                "name": "Apple Inc.",
                "sector": "Technology",
                "description": "Technology company that designs, manufactures, and "
                "sells smartphones, personal computers, tablets, wearables, and "
                "accessories.",
            }
            self.real_stock: Stock = StockService.create_stock(
                self.session,
                real_stock_data,
            )
        else:
            self.real_stock = real_stock

    def test_update_stock_daily_prices(self) -> None:
        """Test fetching daily price data from Yahoo Finance."""
        # Try getting daily prices for a real stock
        daily_prices: list[StockDailyPrice] = (
            DailyPriceService.update_stock_daily_prices(
                self.session,
                self.real_stock.id,
                period="1mo",  # Use a shorter period for testing
            )
        )

        # Verify we got some data
        assert len(daily_prices) > 0, "No daily prices were returned"

        # Verify fields are populated correctly
        for price in daily_prices:
            assert price.stock_id == self.real_stock.id
            assert price.price_date is not None
            assert price.open_price is not None
            assert price.high_price is not None
            assert price.low_price is not None
            assert price.close_price is not None
            assert price.volume is not None

            # Check price relationships
            assert price.high_price >= price.low_price, (
                f"High price {price.high_price} is less than low price "
                f"{price.low_price} for {price.price_date}"
            )

            # Verify source is set correctly
            assert price.source == PriceSource.HISTORICAL.value

    def test_update_latest_daily_price(self) -> None:
        """Test fetching the latest daily price for a stock."""
        # Get the latest daily price for a real stock
        latest_daily: StockDailyPrice = DailyPriceService.update_latest_daily_price(
            self.session,
            self.real_stock.id,
        )

        # Verify we got data
        assert latest_daily is not None, "No latest daily price was returned"
        assert latest_daily.stock_id == self.real_stock.id

        # Verify price is recent
        today: date = get_current_date()
        price_date: date = latest_daily.price_date
        # Allow for weekends and holidays - price should be within 5 days
        date_diff: int = (today - price_date).days
        assert date_diff <= self.MAX_ACCEPTABLE_PRICE_AGE_DAYS, (
            f"Latest price date {price_date} is more than "
            f"{self.MAX_ACCEPTABLE_PRICE_AGE_DAYS} days old from today {today}"
        )

        # Verify source is set
        assert latest_daily.source is not None

    def test_update_stock_intraday_prices(self) -> None:
        """Test fetching intraday price data from Yahoo Finance."""
        # Try getting intraday prices for a real stock
        intraday_prices: list[StockIntradayPrice] = (
            IntradayPriceService.update_stock_intraday_prices(
                self.session,
                self.real_stock.id,
                interval="5m",  # Use 5-minute intervals for fewer data points
                period="1d",  # Use just one day of data
            )
        )

        # Verify we got some data (there may be no data if market is closed)
        if len(intraday_prices) > 0:
            # Verify fields are populated correctly
            for price in intraday_prices:
                assert price.stock_id == self.real_stock.id
                assert price.timestamp is not None
                assert price.interval == IntradayPriceService.INTERVAL_MAPPING["5m"]

                # Some prices might be None during market hours or pre/post market
                # So we don't strictly assert these are not None

                # Check relationships where data exists
                if price.high_price is not None and price.low_price is not None:
                    assert price.high_price >= price.low_price, (
                        f"High price {price.high_price} is less than low price "
                        f"{price.low_price} for {price.timestamp}"
                    )

                # Verify source is set
                assert price.source == PriceSource.DELAYED.value

    def test_update_latest_intraday_price(self) -> None:
        """Test fetching the latest intraday price for a stock."""
        try:
            # Get the latest intraday price for a real stock
            latest_intraday: StockIntradayPrice = (
                IntradayPriceService.update_latest_intraday_price(
                    self.session,
                    self.real_stock.id,
                )
            )

            # Verify we got data
            assert latest_intraday is not None, "No latest intraday price was returned"
            assert latest_intraday.stock_id == self.real_stock.id

            # Verify timestamp is recent (within last day to account for market hours)
            now: datetime = get_current_datetime()
            timestamp: datetime = latest_intraday.timestamp.astimezone(
                TIMEZONE,
            )
            # Time difference should be within a day
            time_diff: timedelta = now - timestamp
            assert time_diff.total_seconds() <= 24 * 60 * 60, (
                f"Latest timestamp {timestamp} is more than 24 hours old from now {now}"
            )

            # Verify interval and source are set
            assert latest_intraday.interval == IntradayInterval.ONE_MINUTE.value
            assert latest_intraday.source == PriceSource.DELAYED.value
        except (APIError, BusinessLogicError, StockError) as e:
            # This test may fail if market is closed or if there's a connectivity issue
            logger.warning("Could not update latest intraday price: %s", e)
            pytest.skip(f"Skipping test due to error: {e}")

    def test_combined_price_update(self) -> None:
        """Test the combined price update operation."""
        # Use the service to update all prices
        result: dict[str, any] = DailyPriceService.update_all_prices(
            self.session,
            self.real_stock.id,
            daily_period="1mo",
            intraday_interval="15m",
            intraday_period="1d",
        )

        # Verify the structure of the result
        assert "daily_prices" in result
        assert "intraday_prices" in result
        assert "latest_daily_price" in result
        assert "latest_intraday_price" in result

        # Check that at least some of the operations succeeded
        # Note: Some operations might fail legitimately (e.g., market closed)
        success_count: int = sum(
            1
            for key in result
            if isinstance(result[key], dict) and result[key].get("success", False)
        )

        # We should have at least one successful operation
        assert success_count > 0, f"No operations succeeded: {result}"
