"""Price service interface that combines daily and intraday price operations.

This service provides a simplified interface by delegating to specialized
DailyPriceService and IntradayPriceService implementations.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models.stock_daily_price import StockDailyPrice
    from app.models.stock_intraday_price import StockIntradayPrice

from app.services.daily_price_service import DailyPriceService
from app.services.intraday_price_service import IntradayPriceService
from app.services.technical_analysis_service import TechnicalAnalysisService
from app.utils.current_datetime import get_current_date

# Set up logging
logger: logging.Logger = logging.getLogger(__name__)


class PriceService:
    """Service aggregating stock price operations across daily and intraday prices."""

    @staticmethod
    def update_all_prices(
        session: Session,
        stock_id: int,
        daily_period: str = DailyPriceService.DEFAULT_DAILY_PERIOD,
        intraday_interval: str = IntradayPriceService.DEFAULT_INTRADAY_INTERVAL,
        intraday_period: str = IntradayPriceService.DEFAULT_INTRADAY_PERIOD,
    ) -> dict[str, any]:
        """Update all price records (daily and intraday) for a stock.

        Args:
            session: Database session
            stock_id: Stock ID
            daily_period: Time period for daily data
            intraday_interval: Time interval for intraday data
            intraday_period: Time period for intraday data

        Returns:
            Dictionary with results for each operation

        Raises:
            ResourceNotFoundError: If stock not found
            BusinessLogicError: For other business logic errors

        """
        result: dict[str, any] = {
            "daily_prices": None,
            "intraday_prices": None,
            "latest_daily_price": None,
            "latest_intraday_price": None,
        }

        # Update daily prices
        try:
            daily_prices: list[StockDailyPrice] = (
                DailyPriceService.update_stock_daily_prices(
                    session,
                    stock_id,
                    daily_period,
                )
            )
            result["daily_prices"] = {
                "success": True,
                "count": len(daily_prices),
            }
        except Exception as e:
            logger.exception("Error updating daily prices")
            result["daily_prices"] = {
                "success": False,
                "error": str(e),
            }

        # Update intraday prices
        try:
            intraday_prices: list[StockIntradayPrice] = (
                IntradayPriceService.update_stock_intraday_prices(
                    session,
                    stock_id,
                    intraday_interval,
                    intraday_period,
                )
            )
            result["intraday_prices"] = {
                "success": True,
                "count": len(intraday_prices),
            }
        except Exception as e:
            logger.exception("Error updating intraday prices")
            result["intraday_prices"] = {
                "success": False,
                "error": str(e),
            }

        # Update latest daily price
        try:
            latest_daily: StockDailyPrice = DailyPriceService.update_latest_daily_price(
                session,
                stock_id,
            )
            result["latest_daily_price"] = {
                "success": True,
                "date": latest_daily.price_date.isoformat(),
            }
        except Exception as e:
            logger.exception("Error updating latest daily price")
            result["latest_daily_price"] = {
                "success": False,
                "error": str(e),
            }

        # Update latest intraday price
        try:
            latest_intraday: StockIntradayPrice = (
                IntradayPriceService.update_latest_intraday_price(
                    session,
                    stock_id,
                )
            )
            result["latest_intraday_price"] = {
                "success": True,
                "timestamp": latest_intraday.timestamp.isoformat(),
            }
        except Exception as e:
            logger.exception("Error updating latest intraday price")
            result["latest_intraday_price"] = {
                "success": False,
                "error": str(e),
            }

        return result

    @staticmethod
    def get_price_analysis(session: Session, stock_id: int) -> dict[str, any]:
        """Get comprehensive price analysis for trading decisions.

        Args:
            session: Database session
            stock_id: Stock ID

        Returns:
            Dictionary with various technical indicators and analysis results

        """
        # Get recent price data
        end_date: date = get_current_date()
        start_date: date = end_date - datetime.timedelta(days=200)
        prices: list[StockDailyPrice] = (
            DailyPriceService.get_daily_prices_by_date_range(
                session,
                stock_id,
                start_date,
                end_date,
            )
        )

        if not prices:
            return {
                "has_data": False,
                "message": "No price data available for analysis",
            }

        close_prices: list[float] = [
            p.close_price for p in prices if p.close_price is not None
        ]

        if not close_prices:
            return {
                "has_data": False,
                "message": "No closing price data available for analysis",
            }

        # Use TechnicalAnalysisService for price analysis
        return TechnicalAnalysisService.get_price_analysis(close_prices)

    @staticmethod
    def is_price_trending_up(session: Session, stock_id: int, days: int = 10) -> bool:
        """Determine if a stock price is trending upward.

        Args:
            session: Database session
            stock_id: Stock ID
            days: Number of days to analyze

        Returns:
            True if price is trending up, False otherwise

        """
        prices: list[StockDailyPrice] = DailyPriceService.get_latest_daily_prices(
            session,
            stock_id,
            days,
        )

        if len(prices) < TechnicalAnalysisService.MIN_DATA_POINTS:
            return False

        # Extract closing prices
        close_prices: list[float] = [
            price.close_price for price in prices if price.close_price is not None
        ]
        close_prices.reverse()  # Change to oldest to newest

        if len(close_prices) < TechnicalAnalysisService.MIN_DATA_POINTS:
            return False

        # Use TechnicalAnalysisService
        return TechnicalAnalysisService.is_price_trending_up(close_prices)

    @staticmethod
    def calculate_moving_averages_for_stock(
        session: Session,
        stock_id: int,
        periods: list[int] = [5, 10, 20, 50, 200] | [],
    ) -> dict[int, float | None]:
        """Calculate multiple moving averages for a stock.

        Args:
            session: Database session
            stock_id: Stock ID
            periods: List of MA periods to calculate

        Returns:
            Dictionary mapping period to MA value

        """
        # Get the last 200 days of data (or the maximum period in periods)
        max_period: int = max(periods)
        end_date: date = get_current_date()
        start_date: date = end_date - datetime.timedelta(days=max_period * 2)

        # Get prices
        prices: list[StockDailyPrice] = (
            DailyPriceService.get_daily_prices_by_date_range(
                session,
                stock_id,
                start_date,
                end_date,
            )
        )

        # Extract closing prices
        close_prices: list[float] = [
            price.close_price for price in prices if price.close_price is not None
        ]

        # Use TechnicalAnalysisService to calculate MAs
        return TechnicalAnalysisService.calculate_moving_averages(close_prices, periods)
