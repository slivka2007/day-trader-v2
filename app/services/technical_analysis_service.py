"""Technical analysis service for stock price data.

This service provides functions for analyzing stock price data, calculating
technical indicators, and generating trading signals. It does not interact
directly with the database.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from app.utils.constants import PriceAnalysisConstants
from app.utils.current_datetime import get_current_date

# Set up logging
logger: logging.Logger = logging.getLogger(__name__)


class TechnicalAnalysisService:
    """Service for technical analysis of stock price data."""

    # Constants for technical analysis
    MIN_DATA_POINTS: ClassVar[int] = PriceAnalysisConstants.MIN_DATA_POINTS
    SHORT_MA_PERIOD: ClassVar[int] = PriceAnalysisConstants.SHORT_MA_PERIOD
    MEDIUM_MA_PERIOD: ClassVar[int] = PriceAnalysisConstants.MEDIUM_MA_PERIOD
    LONG_MA_PERIOD: ClassVar[int] = PriceAnalysisConstants.LONG_MA_PERIOD
    EXTENDED_MA_PERIOD: ClassVar[int] = PriceAnalysisConstants.EXTENDED_MA_PERIOD
    MAX_MA_PERIOD: ClassVar[int] = PriceAnalysisConstants.MAX_MA_PERIOD

    # RSI constants
    RSI_OVERSOLD: ClassVar[int] = PriceAnalysisConstants.RSI_OVERSOLD
    RSI_OVERBOUGHT: ClassVar[int] = PriceAnalysisConstants.RSI_OVERBOUGHT
    RSI_MIN_PERIODS: ClassVar[int] = PriceAnalysisConstants.RSI_MIN_PERIODS

    # Constants for default periods
    DEFAULT_MA_PERIOD: ClassVar[int] = PriceAnalysisConstants.DEFAULT_MA_PERIOD
    DEFAULT_BB_PERIOD: ClassVar[int] = PriceAnalysisConstants.DEFAULT_BB_PERIOD

    @staticmethod
    def calculate_simple_moving_average(
        prices: list[float],
        period: int = PriceAnalysisConstants.DEFAULT_MA_PERIOD,
    ) -> float | None:
        """Calculate simple moving average for a list of prices.

        Args:
            prices: List of prices (oldest to newest)
            period: SMA period

        Returns:
            SMA value if enough data points available, None otherwise

        """
        if len(prices) < period:
            return None

        return sum(prices[-period:]) / period

    @staticmethod
    def calculate_moving_averages(
        close_prices: list[float],
        periods: list[int] | None = None,
    ) -> dict[int, float | None]:
        """Calculate multiple moving averages.

        Args:
            close_prices: List of closing prices (oldest to newest)
            periods: List of MA periods to calculate

        Returns:
            Dictionary mapping period to MA value

        """
        if periods is None:
            periods = [
                TechnicalAnalysisService.SHORT_MA_PERIOD,
                TechnicalAnalysisService.MEDIUM_MA_PERIOD,
                TechnicalAnalysisService.LONG_MA_PERIOD,
                TechnicalAnalysisService.EXTENDED_MA_PERIOD,
                TechnicalAnalysisService.MAX_MA_PERIOD,
            ]

        # Calculate MAs for each period
        result: dict[int, float | None] = {}
        for period in periods:
            result[period] = TechnicalAnalysisService.calculate_simple_moving_average(
                close_prices,
                period,
            )

        return result

    @staticmethod
    def calculate_rsi(
        prices: list[float],
        period: int = 14,
    ) -> float | None:
        """Calculate Relative Strength Index (RSI) for a list of prices.

        Args:
            prices: List of prices (oldest to newest)
            period: RSI period

        Returns:
            RSI value if enough data points available, None otherwise

        """
        if len(prices) < period + 1:
            return None

        # Calculate price changes
        changes: list[float] = [
            prices[i + 1] - prices[i] for i in range(len(prices) - 1)
        ]

        # Separate gains and losses
        gains: list[float] = [max(0, change) for change in changes]
        losses: list[float] = [max(0, -change) for change in changes]

        # Calculate average gain and loss
        avg_gain: float = sum(gains[-period:]) / period
        avg_loss: float = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0

        rs: float = avg_gain / avg_loss
        rsi: float = 100 - (100 / (1 + rs))

        return rsi

    @staticmethod
    def calculate_bollinger_bands(
        prices: list[float],
        period: int = PriceAnalysisConstants.DEFAULT_BB_PERIOD,
        num_std: float = 2.0,
    ) -> dict[str, float | None]:
        """Calculate Bollinger Bands for a list of prices.

        Args:
            prices: List of prices (oldest to newest)
            period: Period for SMA calculation
            num_std: Number of standard deviations for bands

        Returns:
            Dictionary with 'upper', 'middle', and 'lower' band values

        """
        if len(prices) < period:
            return {"upper": None, "middle": None, "lower": None}

        # Calculate SMA
        sma: float | None = TechnicalAnalysisService.calculate_simple_moving_average(
            prices,
            period,
        )

        # Early return if SMA is None
        if sma is None:
            return {"upper": None, "middle": None, "lower": None}

        # Calculate standard deviation
        recent_prices: list[float] = prices[-period:]
        std_dev: float = (
            sum((price - sma) ** 2 for price in recent_prices) / period
        ) ** 0.5

        # Calculate bands
        upper_band: float = sma + (std_dev * num_std)
        lower_band: float = sma - (std_dev * num_std)

        return {"upper": upper_band, "middle": sma, "lower": lower_band}

    @staticmethod
    def is_price_trending_up(
        close_prices: list[float],
    ) -> bool:
        """Determine if a stock price is trending upward.

        Args:
            close_prices: List of closing prices (oldest to newest)

        Returns:
            True if price is trending up, False otherwise

        """
        if len(close_prices) < TechnicalAnalysisService.MIN_DATA_POINTS:
            return False

        # Calculate 5-day and 10-day MAs
        ma5: float | None = TechnicalAnalysisService.calculate_simple_moving_average(
            close_prices,
            TechnicalAnalysisService.SHORT_MA_PERIOD,
        )

        if len(close_prices) >= TechnicalAnalysisService.MEDIUM_MA_PERIOD:
            ma10: float | None = (
                TechnicalAnalysisService.calculate_simple_moving_average(
                    close_prices,
                    TechnicalAnalysisService.MEDIUM_MA_PERIOD,
                )
            )
            # 5-day MA above 10-day MA suggests uptrend
            return ma5 is not None and ma10 is not None and ma5 > ma10

        # If not enough data for 10-day MA, check if recent prices are above 5-day MA
        return ma5 is not None and close_prices[-1] > ma5

    @staticmethod
    def calculate_price_changes(
        close_prices: list[float],
    ) -> dict[str, float]:
        """Calculate price changes over different periods.

        Args:
            close_prices: List of closing prices (oldest to newest)

        Returns:
            Dictionary with price changes for different periods

        """
        price_changes: dict[str, float] = {}
        periods: list[int] = [1, 5, 10, 30, 90]

        for period in periods:
            if len(close_prices) > period:
                change: float = (
                    (close_prices[-1] - close_prices[-(period + 1)])
                    / close_prices[-(period + 1)]
                    * 100
                )
                price_changes[f"{period}_day"] = change

        return price_changes

    @staticmethod
    def analyze_signals(
        rsi: float | None,
        moving_averages: dict[int, float | None],
        bollinger_bands: dict[str, float | None],
        latest_price: float | None,
    ) -> dict[str, str]:
        """Analyze trading signals from technical indicators.

        Args:
            rsi: RSI value
            moving_averages: Dictionary of moving averages
            bollinger_bands: Dictionary with Bollinger Bands values
            latest_price: Latest price

        Returns:
            Dictionary with signal analysis

        """
        signals: dict[str, str] = {}

        if rsi is not None:
            if rsi < TechnicalAnalysisService.RSI_OVERSOLD:
                signals["rsi"] = "oversold"
            elif rsi > TechnicalAnalysisService.RSI_OVERBOUGHT:
                signals["rsi"] = "overbought"
            else:
                signals["rsi"] = "neutral"

        if (
            TechnicalAnalysisService.SHORT_MA_PERIOD in moving_averages
            and TechnicalAnalysisService.LONG_MA_PERIOD in moving_averages
        ):
            short_ma = moving_averages[TechnicalAnalysisService.SHORT_MA_PERIOD]
            long_ma = moving_averages[TechnicalAnalysisService.LONG_MA_PERIOD]

            if short_ma is not None and long_ma is not None:
                if short_ma > long_ma:
                    signals["ma_crossover"] = "bullish"
                else:
                    signals["ma_crossover"] = "bearish"

        if (
            bollinger_bands
            and bollinger_bands["upper"] is not None
            and latest_price is not None
        ):
            if latest_price > bollinger_bands["upper"]:
                signals["bollinger"] = "overbought"
            elif (
                bollinger_bands["lower"] is not None
                and latest_price < bollinger_bands["lower"]
            ):
                signals["bollinger"] = "oversold"
            else:
                signals["bollinger"] = "neutral"

        return signals

    @staticmethod
    def get_price_analysis(
        close_prices: list[float],
    ) -> dict[str, any]:
        """Get comprehensive price analysis for trading decisions.

        Args:
            close_prices: List of closing prices (oldest to newest)

        Returns:
            Dictionary with various technical indicators and analysis results

        """
        if not close_prices:
            return {
                "has_data": False,
                "message": "No price data available for analysis",
            }

        latest_price: float = close_prices[-1]

        # Calculate technical indicators
        ma_periods: list[int] = [
            TechnicalAnalysisService.SHORT_MA_PERIOD,
            TechnicalAnalysisService.MEDIUM_MA_PERIOD,
            TechnicalAnalysisService.LONG_MA_PERIOD,
            TechnicalAnalysisService.EXTENDED_MA_PERIOD,
            TechnicalAnalysisService.MAX_MA_PERIOD,
        ]

        moving_averages: dict[int, float | None] = {
            period: TechnicalAnalysisService.calculate_simple_moving_average(
                close_prices,
                period,
            )
            for period in ma_periods
            if len(close_prices) >= period
        }

        rsi: float | None = (
            TechnicalAnalysisService.calculate_rsi(close_prices)
            if len(close_prices) >= TechnicalAnalysisService.RSI_MIN_PERIODS
            else None
        )

        bollinger_bands: dict[str, float | None] = (
            TechnicalAnalysisService.calculate_bollinger_bands(close_prices)
            if len(close_prices) >= TechnicalAnalysisService.DEFAULT_BB_PERIOD
            else {"upper": None, "middle": None, "lower": None}
        )

        # Compile analysis
        is_uptrend = None
        if (
            TechnicalAnalysisService.SHORT_MA_PERIOD in moving_averages
            and TechnicalAnalysisService.LONG_MA_PERIOD in moving_averages
        ):
            short_ma = moving_averages[TechnicalAnalysisService.SHORT_MA_PERIOD]
            long_ma = moving_averages[TechnicalAnalysisService.LONG_MA_PERIOD]
            if short_ma is not None and long_ma is not None:
                is_uptrend = short_ma > long_ma

        analysis: dict[str, any] = {
            "has_data": True,
            "latest_price": latest_price,
            "moving_averages": moving_averages,
            "rsi": rsi,
            "bollinger_bands": bollinger_bands,
            "is_uptrend": is_uptrend,
            "price_changes": TechnicalAnalysisService.calculate_price_changes(
                close_prices,
            ),
            "analysis_date": get_current_date().isoformat(),
            "signals": TechnicalAnalysisService.analyze_signals(
                rsi,
                moving_averages,
                bollinger_bands,
                latest_price,
            ),
        }

        return analysis
