"""Backtest service for simulating trading strategies.

This service provides functionality to test trading strategies using
historical price data and simulated trades.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.stock import Stock
    from app.models.stock_daily_price import StockDailyPrice
    from app.models.trading_service import TradingService

from app.services.stock_service import StockService
from app.services.technical_analysis_service import TechnicalAnalysisService
from app.services.trading_service import TradingServiceService
from app.utils.constants import TradingServiceConstants
from app.utils.current_datetime import get_current_date
from app.utils.errors import ResourceNotFoundError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# Set up logging
logger: logging.Logger = logging.getLogger(__name__)


class BacktestService:
    """Service for backtesting trading strategies.

    This class provides methods for simulating trading strategies
    using historical price data.
    """

    # Constants
    MIN_DAYS_FOR_SMA: int = TradingServiceConstants.MIN_DAYS_FOR_SMA

    @dataclass
    class BacktestDayParams:
        """Parameters for processing a backtest day."""

        price: StockDailyPrice
        price_history: list[float]
        current_balance: float
        shares_held: int
        last_buy_price: float | None
        buy_threshold: float
        sell_threshold: float
        allocation_percent: float
        day_index: int

    @staticmethod
    def _process_backtest_day(
        params: BacktestDayParams,
    ) -> tuple[float, int, float | None, dict[str, any] | None]:
        """Process a single day in the backtest simulation.

        Args:
            params: BacktestDayParams instance with simulation parameters

        Returns:
            Tuple of (updated_balance, updated_shares, last_buy_price, transaction_data)

        """
        # Get the price for this day
        current_price: float = float(params.price.close_price)

        # Add price to history
        price_history: list[float] = params.price_history.copy()
        price_history.append(current_price)

        # If we don't have enough price history yet, just return updated values
        if len(price_history) < BacktestService.MIN_DAYS_FOR_SMA:
            return (
                params.current_balance,
                params.shares_held,
                params.last_buy_price,
                None,
            )

        # Get price analysis
        price_analysis: dict[str, any] = TechnicalAnalysisService.get_price_analysis(
            price_history,
        )

        transaction = None

        # If we don't have shares, check buy conditions
        if params.shares_held == 0:
            should_buy: bool = BacktestService._should_buy_backtest(
                price_analysis,
                current_price,
                params.current_balance,
                params.buy_threshold,
                params.allocation_percent,
            )
            if should_buy:
                amount_to_spend: float = params.current_balance * (
                    params.allocation_percent / 100.0
                )
                shares_to_buy: float = (
                    int((amount_to_spend / current_price) * 100) / 100.0
                )
                if shares_to_buy > 0:
                    cost: float = shares_to_buy * current_price
                    if cost <= params.current_balance:
                        params.current_balance -= cost
                        params.shares_held = shares_to_buy
                        params.last_buy_price = current_price
                        transaction: dict[str, any] = {
                            "type": "buy",
                            "date": params.price.price_date.isoformat(),
                            "price": current_price,
                            "shares": params.shares_held,
                            "cost": cost,
                            "balance": params.current_balance,
                        }
        # If we have shares, check sell conditions
        elif params.shares_held > 0:
            should_sell: bool = BacktestService._should_sell_backtest(
                price_analysis,
                params.sell_threshold,
            )
            if should_sell:
                revenue: float = params.shares_held * current_price
                params.current_balance += revenue
                gain_loss: float = (
                    revenue - (params.shares_held * params.last_buy_price)
                    if params.last_buy_price
                    else 0
                )
                params.shares_held = 0
                params.last_buy_price = None
                transaction: dict[str, any] = {
                    "type": "sell",
                    "date": params.price.price_date.isoformat(),
                    "price": current_price,
                    "revenue": revenue,
                    "gain_loss": gain_loss,
                    "balance": params.current_balance,
                }

        return (
            params.current_balance,
            params.shares_held,
            params.last_buy_price,
            transaction,
        )

    @staticmethod
    def _calculate_backtest_metrics(
        portfolio_values: list[float],
        initial_balance: float,
        days: int,
    ) -> dict[str, any]:
        """Calculate performance metrics for a backtest.

        Args:
            portfolio_values: List of portfolio values over time
            initial_balance: Initial account balance
            days: Number of days in the simulation

        Returns:
            Dictionary with performance metrics

        """
        if not portfolio_values:
            return {
                "total_return_pct": 0,
                "annualized_return_pct": 0,
                "max_drawdown_pct": 0,
                "volatility": 0,
                "sharpe_ratio": 0,
            }

        # Calculate returns
        final_value: float = portfolio_values[-1]
        total_return: float = (final_value - initial_balance) / initial_balance

        # Annualized return (assuming 252 trading days per year)
        if days > 0:
            years: float = days / 252
            annualized_return: float = (
                (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
            )
        else:
            annualized_return: float = 0

        # Max drawdown calculation
        max_value: float = portfolio_values[0]
        max_drawdown: float = 0

        for value in portfolio_values:
            max_value = max(max_value, value)
            drawdown: float = (max_value - value) / max_value if max_value > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)

        # Volatility (standard deviation of daily returns)
        daily_returns: list[float] = [
            (portfolio_values[i] / portfolio_values[i - 1]) - 1
            for i in range(1, len(portfolio_values))
        ]

        if daily_returns:
            avg_return: float = sum(daily_returns) / len(daily_returns)
            squared_diffs: list[float] = [(r - avg_return) ** 2 for r in daily_returns]
            variance: float = (
                sum(squared_diffs) / len(squared_diffs) if squared_diffs else 0
            )
            volatility: float = variance**0.5

            # Annualized volatility
            volatility_annualized: float = volatility * (252**0.5)

            # Sharpe ratio (assuming 0% risk-free rate)
            sharpe_ratio: float = (
                annualized_return / volatility_annualized
                if volatility_annualized > 0
                else 0
            )
        else:
            volatility: float = 0
            sharpe_ratio: float = 0

        return {
            "total_return_pct": total_return * 100,
            "annualized_return_pct": annualized_return * 100,
            "max_drawdown_pct": max_drawdown * 100,
            "volatility": volatility * 100,
            "sharpe_ratio": sharpe_ratio,
        }

    @staticmethod
    def _should_buy_backtest(
        price_analysis: dict[str, any],
        current_price: float,
        current_balance: float,
        buy_threshold: float,
    ) -> bool:
        """Determine if a buy decision should be made during backtesting.

        Args:
            price_analysis: Price analysis data
            current_price: Current stock price
            current_balance: Current account balance
            buy_threshold: Buy threshold percentage
            allocation_percent: Allocation percentage

        Returns:
            True if buy conditions are met, False otherwise

        """
        # Check if we have sufficient price data and funds
        if not price_analysis.get("has_data", False) or current_balance <= 0:
            return False

        # Get signals from technical analysis
        signals: dict[str, any] = price_analysis.get("signals", {})
        rsi_signal: str = signals.get("rsi", "neutral")
        bollinger_signal: str = signals.get("bollinger", "neutral")

        # Buy conditions:
        # 1. RSI indicates oversold
        # 2. Price is below lower Bollinger band (oversold)
        # 3. Is in uptrend and price dropped below buy threshold
        is_uptrend: bool = price_analysis.get("is_uptrend", False)

        # Condition 1: RSI oversold condition
        rsi_buy_signal: bool = rsi_signal == "oversold"

        # Condition 2: Bollinger oversold condition
        bollinger_buy_signal: bool = bollinger_signal == "oversold"

        # Condition 3: Price dropped but in uptrend
        moving_averages: dict[str, any] = price_analysis.get("moving_averages", {})
        short_ma: float | None = moving_averages.get(
            TradingServiceConstants.SHORT_MA_PERIOD,
        )
        if short_ma:
            percent_below_ma: float = ((short_ma - current_price) / short_ma) * 100
            ma_buy_signal: bool = is_uptrend and percent_below_ma >= buy_threshold
        else:
            ma_buy_signal = False

        # Final decision: Any of the buy signals is True
        return rsi_buy_signal or bollinger_buy_signal or ma_buy_signal

    @staticmethod
    def _should_sell_backtest(
        price_analysis: dict[str, any],
    ) -> bool:
        """Determine if a sell decision should be made during backtesting.

        Args:
            price_analysis: Price analysis data
            sell_threshold: Sell threshold percentage

        Returns:
            True if sell conditions are met, False otherwise

        """
        # Check if we have sufficient price data
        if not price_analysis.get("has_data", False):
            return False

        # Get signals from technical analysis
        signals: dict[str, any] = price_analysis.get("signals", {})
        rsi_signal: str = signals.get("rsi", "neutral")
        bollinger_signal: str = signals.get("bollinger", "neutral")

        # Sell conditions:
        # 1. RSI indicates overbought
        # 2. Price is above upper Bollinger band (overbought)
        # 3. MA crossover is bearish

        # Condition 1: RSI overbought condition
        rsi_sell_signal: bool = rsi_signal == "overbought"

        # Condition 2: Bollinger overbought condition
        bollinger_sell_signal: bool = bollinger_signal == "overbought"

        # Condition 3: MA crossover is bearish
        ma_crossover_sell_signal: bool = signals.get("ma_crossover") == "bearish"

        # Final decision: Any of the sell signals is True
        return rsi_sell_signal or bollinger_sell_signal or ma_crossover_sell_signal

    @staticmethod
    def backtest_strategy(
        session: Session,
        service_id: int,
        days: int = 90,
    ) -> dict[str, any]:
        """Backtest a trading strategy using historical price data.

        Args:
            session: Database session
            service_id: Trading service ID
            days: Number of days to backtest (default: 90)

        Returns:
            Dictionary with backtest results

        Raises:
            ResourceNotFoundError: If service or stock not found
            ValueError: If insufficient price data available

        """
        # Get service
        service: TradingService = TradingServiceService.get_or_404(
            session,
            service_id,
        )

        # Get stock
        stock: Stock | None = StockService.find_by_symbol(
            session,
            service.stock_symbol,
        )

        if not stock:
            raise ResourceNotFoundError(
                TradingServiceConstants.RESOURCE_STOCK,
                service.stock_symbol,
            )

        # Define date range for historical data
        end_date: date = get_current_date()
        start_date: date = end_date - timedelta(days=days)

        # Get historical daily prices
        price_data: list[StockDailyPrice] | None = StockService.get_price_range(
            session,
            stock.id,
            start_date,
            end_date,
        )

        if not price_data or len(price_data) < BacktestService.MIN_DAYS_FOR_SMA:
            return {
                "success": False,
                "message": (
                    f"Insufficient price data for backtest. "
                    f"Need at least {BacktestService.MIN_DAYS_FOR_SMA} days."
                ),
                "days_available": len(price_data) if price_data else 0,
            }

        # Initialize backtest parameters
        initial_balance: float = service.initial_balance
        current_balance: float = initial_balance
        shares_held: int = 0
        last_buy_price: float | None = None
        price_history: list[float] = []
        portfolio_values: list[float] = []
        transactions: list[dict[str, any]] = []
        transaction: dict[str, any] | None = None

        # Process each day
        for i, price in enumerate(price_data):
            # Process this day's activity
            params = BacktestService.BacktestDayParams(
                price=price,
                price_history=price_history.copy(),
                current_balance=current_balance,
                shares_held=shares_held,
                last_buy_price=last_buy_price,
                buy_threshold=service.buy_threshold,
                sell_threshold=service.sell_threshold,
                allocation_percent=service.allocation_percent,
                day_index=i,
            )

            # Execute strategy for this day
            (
                current_balance,
                shares_held,
                last_buy_price,
                transaction,
            ) = BacktestService._process_backtest_day(params)

            # Record transaction if any
            if transaction:
                transactions.append(transaction)

            # Update price history
            price_history.append(float(price.close_price))

            # Calculate portfolio value for this day
            portfolio_value: float = current_balance
            if shares_held > 0:
                portfolio_value += shares_held * float(price.close_price)

            # Record portfolio value
            portfolio_values.append(portfolio_value)

        # Calculate final metrics
        final_portfolio_value: float = current_balance + (
            shares_held * float(price_data[-1].close_price) if shares_held > 0 else 0
        )

        gain_loss: float = final_portfolio_value - initial_balance
        gain_loss_pct: float = (
            (gain_loss / initial_balance) * 100 if initial_balance > 0 else 0
        )

        # Calculate performance metrics
        metrics: dict[str, any] = BacktestService._calculate_backtest_metrics(
            portfolio_values,
            initial_balance,
            len(price_data),
        )

        # Prepare result
        result: dict[str, any] = {
            "success": True,
            "service_id": service_id,
            "stock_symbol": service.stock_symbol,
            "initial_balance": initial_balance,
            "final_balance": current_balance,
            "final_shares": shares_held,
            "final_portfolio_value": final_portfolio_value,
            "gain_loss": gain_loss,
            "gain_loss_pct": gain_loss_pct,
            "days_simulated": len(price_data),
            "transactions": transactions,
            "portfolio_values": portfolio_values,
            "price_history": [float(price.close_price) for price in price_data],
            "dates": [price.price_date.isoformat() for price in price_data],
            "metrics": metrics,
        }

        return result
