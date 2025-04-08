"""Trading Strategy service for managing trading decisions.

This service encapsulates the decision-making logic for trading operations,
providing methods for analyzing market data and generating buy/sell decisions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.stock import Stock
    from app.models.trading_service import TradingService

from app.models.enums import TradingMode
from app.services.stock_service import StockService
from app.services.technical_analysis_service import TechnicalAnalysisService
from app.services.trading_service import TradingServiceService
from app.services.transaction_service import TransactionService
from app.utils.constants import PriceAnalysisConstants, TradingServiceConstants
from app.utils.current_datetime import get_current_datetime

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models.trading_transaction import TradingTransaction

# Set up logging
logger: logging.Logger = logging.getLogger(__name__)


class TradingStrategyService:
    """Service for trading strategy operations.

    This class provides methods for making trading decisions based on
    technical analysis and executing buy/sell operations.
    """

    # Constants
    MIN_PRICE_DATA_POINTS: int = PriceAnalysisConstants.MIN_DATA_POINTS

    @staticmethod
    def check_buy_condition(
        service: TradingService,
        current_price: float,
        historical_prices: list[float] | None = None,
    ) -> dict[str, any]:
        """Check if buy conditions are met for a trading service.

        Args:
            session: Database session
            service: TradingService instance
            current_price: Current stock price
            historical_prices: Optional list of historical prices

        Returns:
            Dictionary with decision information

        """
        if not historical_prices:
            # Use price data from technical analysis service if not provided
            price_analysis: dict[str, any] = (
                TechnicalAnalysisService.get_price_analysis(
                    historical_prices or [],
                )
            )
        else:
            price_analysis: dict[str, any] = (
                TechnicalAnalysisService.get_price_analysis(
                    historical_prices,
                )
            )

        should_buy: bool = TradingStrategyService._should_buy(
            service,
            price_analysis,
            current_price,
        )

        return {
            "should_proceed": should_buy,
            "reason": "Buy conditions met" if should_buy else "Buy conditions not met",
            "timestamp": get_current_datetime().isoformat(),
            "details": {
                "price_analysis": price_analysis,
                "service_id": service.id,
                "stock_symbol": service.stock_symbol,
                "current_price": current_price,
            },
            "service_id": service.id,
            "next_action": "buy" if should_buy else "wait",
        }

    @staticmethod
    def check_sell_condition(
        service: TradingService,
        current_price: float,
        historical_prices: list[float] | None = None,
    ) -> dict[str, any]:
        """Check if sell conditions are met for a trading service.

        Args:
            service: TradingService instance
            current_price: Current stock price
            historical_prices: Optional list of historical prices

        Returns:
            Dictionary with decision information

        """
        # Get price analysis
        price_analysis: dict[str, any] = TechnicalAnalysisService.get_price_analysis(
            historical_prices or [],
        )

        should_sell: bool = TradingStrategyService._should_sell(
            service,
            price_analysis,
        )

        return {
            "should_proceed": should_sell,
            "reason": "Sell conditions met"
            if should_sell
            else "Sell conditions not met",
            "timestamp": get_current_datetime().isoformat(),
            "details": {
                "price_analysis": price_analysis,
                "service_id": service.id,
                "stock_symbol": service.stock_symbol,
                "current_price": current_price,
            },
            "service_id": service.id,
            "next_action": "sell" if should_sell else "wait",
        }

    @staticmethod
    def _should_buy(
        service: TradingService,
        price_analysis: dict[str, any],
        current_price: float,
    ) -> bool:
        """Determine if a buy decision should be made.

        Args:
            service: TradingService instance
            price_analysis: Price analysis data
            current_price: Current stock price

        Returns:
            True if buy conditions are met, False otherwise

        """
        # First check if service can buy (has enough funds, correct state and mode)
        if not service.can_buy:
            return False

        # Check if we have sufficient price data
        if not price_analysis.get("has_data", False):
            return False

        # Get signals from technical analysis
        signals = price_analysis.get("signals", {})
        rsi_signal = signals.get("rsi", "neutral")
        bollinger_signal = signals.get("bollinger", "neutral")

        # Buy conditions:
        # 1. RSI indicates oversold
        # 2. Price is below lower Bollinger band (oversold)
        # 3. Is in uptrend and price dropped below buy threshold
        is_uptrend = price_analysis.get("is_uptrend", False)

        # Condition 1: RSI oversold condition
        rsi_buy_signal = rsi_signal == "oversold"

        # Condition 2: Bollinger oversold condition
        bollinger_buy_signal = bollinger_signal == "oversold"

        # Condition 3: Price dropped but in uptrend
        moving_averages = price_analysis.get("moving_averages", {})
        short_ma = moving_averages.get(TradingServiceConstants.SHORT_MA_PERIOD)
        if short_ma:
            percent_below_ma = ((short_ma - current_price) / short_ma) * 100
            ma_buy_signal = is_uptrend and percent_below_ma >= service.buy_threshold
        else:
            ma_buy_signal = False

        # Final decision: Any of the buy signals is True
        return rsi_buy_signal or bollinger_buy_signal or ma_buy_signal

    @staticmethod
    def _should_sell(
        service: TradingService,
        price_analysis: dict[str, any],
    ) -> bool:
        """Determine if a sell decision should be made.

        Args:
            service: TradingService instance
            price_analysis: Price analysis data

        Returns:
            True if sell conditions are met, False otherwise

        """
        # First check if service can sell (has shares, correct state and mode)
        if not service.can_sell:
            return False

        # Check if we have sufficient price data
        if not price_analysis.get("has_data", False):
            return False

        # Get signals from technical analysis
        signals = price_analysis.get("signals", {})
        rsi_signal = signals.get("rsi", "neutral")
        bollinger_signal = signals.get("bollinger", "neutral")

        # Sell conditions:
        # 1. RSI indicates overbought
        # 2. Price is above upper Bollinger band (overbought)
        # 3. MA crossover is bearish

        # Condition 1: RSI overbought condition
        rsi_sell_signal = rsi_signal == "overbought"

        # Condition 2: Bollinger overbought condition
        bollinger_sell_signal = bollinger_signal == "overbought"

        # Condition 3: MA crossover is bearish
        ma_crossover_sell_signal = signals.get("ma_crossover") == "bearish"

        # Final decision: Any of the sell signals is True
        return rsi_sell_signal or bollinger_sell_signal or ma_crossover_sell_signal

    @staticmethod
    def execute_buy_strategy(
        session: Session,
        service: TradingService,
        price_analysis: dict[str, any],
        current_price: float,
        result: dict[str, any],
    ) -> dict[str, any]:
        """Execute buy strategy for a trading service.

        Args:
            session: Database session
            service: TradingService instance
            price_analysis: Price analysis data
            current_price: Current stock price
            result: Base result dictionary to build upon

        Returns:
            Updated result dictionary with buy action information

        """
        # Check buy conditions using technical analysis
        should_buy: bool = TradingStrategyService._should_buy(
            service,
            price_analysis,
            current_price,
        )
        result["should_buy"] = should_buy

        if not should_buy:
            result["action"] = "none"
            result["message"] = "Buy conditions not met"
            return result

        # Calculate how many shares to buy
        max_shares_affordable: int = (
            int(service.current_balance / current_price) if current_price > 0 else 0
        )
        allocation_amount: float = (
            service.current_balance * service.allocation_percent
        ) / 100
        shares_to_buy: int = int(allocation_amount / current_price)
        shares_to_buy = max(1, min(shares_to_buy, max_shares_affordable))

        if shares_to_buy <= 0:
            result["action"] = "none"
            result["message"] = "Not enough funds to buy shares"
            return result

        try:
            # Execute buy transaction
            transaction: TradingTransaction = TransactionService.create_buy_transaction(
                session=session,
                service_id=service.id,
                stock_symbol=service.stock_symbol,
                shares=shares_to_buy,
                purchase_price=current_price,
            )

            result["action"] = "buy"
            result["shares_bought"] = shares_to_buy
            result["transaction_id"] = transaction.id
            result["total_cost"] = shares_to_buy * current_price
            result["message"] = f"Bought {shares_to_buy} shares at ${current_price:.2f}"

            # Update service statistics
            service.buy_count = service.buy_count + 1
            service.current_shares = service.current_shares + shares_to_buy
            service.updated_at = get_current_datetime()
            session.commit()
        except Exception as e:
            logger.exception("Error executing buy transaction")
            result["success"] = False
            result["action"] = "none"
            result["message"] = f"Error executing buy transaction: {e!s}"

        return result

    @staticmethod
    def execute_sell_strategy(
        session: Session,
        service: TradingService,
        price_analysis: dict[str, any],
        current_price: float,
        result: dict[str, any],
    ) -> dict[str, any]:
        """Execute sell strategy for a trading service.

        Args:
            session: Database session
            service: TradingService instance
            price_analysis: Price analysis data
            current_price: Current stock price
            result: Base result dictionary to build upon

        Returns:
            Updated result dictionary with sell action information

        """
        # Check sell conditions using technical analysis
        should_sell: bool = TradingStrategyService._should_sell(
            service,
            price_analysis,
        )
        result["should_sell"] = should_sell

        if not should_sell:
            result["action"] = "none"
            result["message"] = "Sell conditions not met"
            return result

        # Check if we have shares to sell
        if service.current_shares <= 0:
            result["action"] = "none"
            result["message"] = "No shares available to sell"
            return result

        try:
            # Execute sell transaction
            transaction: TradingTransaction = (
                TransactionService.create_sell_transaction(
                    session=session,
                    service_id=service.id,
                    stock_symbol=service.stock_symbol,
                    shares=service.current_shares,
                    sale_price=current_price,
                )
            )

            # Calculate total revenue
            total_revenue = service.current_shares * current_price

            result["action"] = "sell"
            result["shares_sold"] = service.current_shares
            result["transaction_id"] = transaction.id
            result["total_revenue"] = total_revenue
            result["message"] = (
                f"Sold {service.current_shares} shares at ${current_price:.2f}"
            )

            # Update service statistics
            service.sell_count = service.sell_count + 1
            service.current_shares = 0
            service.updated_at = get_current_datetime()
            session.commit()
        except Exception as e:
            logger.exception("Error executing sell transaction")
            result["success"] = False
            result["action"] = "none"
            result["message"] = f"Error executing sell transaction: {e!s}"

        return result

    @staticmethod
    def _validate_trading_strategy(
        session: Session,
        service: TradingService,
    ) -> tuple[bool, dict[str, any], list[float] | None, float | None]:
        """Validate conditions for trading strategy execution.

        Returns:
            Tuple containing:
            - Success flag
            - Result dict with error message if validation failed
            - Close prices list if validation passed
            - Current price if validation passed

        """
        result = {"success": False, "action": "none"}
        close_prices = None
        current_price = None

        # Service state validation
        if not bool(service.is_active) or not bool(service.state == "ACTIVE"):
            result["message"] = (
                f"Service is not active (state: {service.state}, "
                f"is_active: {service.is_active})"
            )
        # Stock validation
        elif not (stock := StockService.find_by_symbol(session, service.stock_symbol)):
            result["message"] = f"Stock {service.stock_symbol} not found"
        # Price history validation
        elif (
            not (price_history := StockService.get_recent_prices(session, stock.id, 90))
            or len(price_history) < TradingStrategyService.MIN_PRICE_DATA_POINTS
        ):
            result["message"] = "Insufficient price data for analysis"
        else:
            # Convert price history to list of float values
            close_prices = [float(price.close_price) for price in price_history]

            # Get price analysis
            price_analysis = TechnicalAnalysisService.get_price_analysis(close_prices)

            if not bool(price_analysis.get("has_data", False)):
                result["message"] = "Insufficient price data for analysis"
                return False, result, None, None

            # Get current price
            current_price = price_analysis.get("latest_price")
            if not current_price:
                result["message"] = "Could not determine current price"
                return False, result, None, None

            # All validations passed
            return True, result, close_prices, current_price

        # If we reach here, validation failed
        return False, result, None, None

    @staticmethod
    def execute_trading_strategy(session: Session, service_id: int) -> dict[str, any]:
        """Execute trading strategy for a service.

        This method coordinates the decision-making process for buying or selling
        stocks based on:
        1. Current price trends (using TechnicalAnalysisService for analysis)
        2. Service configuration (thresholds, modes, etc.)
        3. Available funds and current positions

        Args:
            session: Database session
            service_id: Trading service ID

        Returns:
            Dictionary with trading decision information and any actions taken

        Raises:
            ResourceNotFoundError: If service not found
            BusinessLogicError: If service is not active or other business rule
            violations

        """
        # Get the service
        service: TradingService = TradingServiceService.get_or_404(session, service_id)

        # Validate strategy conditions
        valid: bool
        result: dict[str, any]
        close_prices: list[float] | None
        current_price: float | None
        valid, result, close_prices, current_price = (
            TradingStrategyService._validate_trading_strategy(
                session,
                service,
            )
        )

        if not valid:
            return result

        # Get price analysis for actual strategy
        price_analysis: dict[str, any] = TechnicalAnalysisService.get_price_analysis(
            close_prices,
        )

        # Trading decision
        result = {
            "success": True,
            "service_id": service_id,
            "stock_symbol": service.stock_symbol,
            "current_price": current_price,
            "current_balance": service.current_balance,
            "current_shares": service.current_shares,
            "mode": service.mode,
            "signals": price_analysis.get("signals", {}),
        }

        # Execute strategy based on mode
        if bool(service.mode == TradingMode.BUY.value):
            return TradingStrategyService.execute_buy_strategy(
                session,
                service,
                price_analysis,
                current_price,
                result,
            )
        if bool(service.mode == TradingMode.SELL.value):
            return TradingStrategyService.execute_sell_strategy(
                session,
                service,
                price_analysis,
                current_price,
                result,
            )
        # Handle HOLD mode or any other mode
        if bool(service.mode == TradingMode.HOLD.value):
            result["action"] = "none"
            result["message"] = "Service is in HOLD mode, no actions taken"
        else:
            result["action"] = "none"
            result["message"] = f"Unsupported trading mode: {service.mode}"

        return result

    @staticmethod
    def check_price_conditions(
        session: Session,
        service: TradingService,
        action: str,
    ) -> dict[str, any]:
        """Check price conditions for a trading service.

        Args:
            session: Database session
            service: TradingService instance
            action: Action to check (buy/sell)

        Returns:
            Dictionary with analysis result

        """
        # Initial result with failure assumed
        result: dict[str, any] = {
            "success": False,
            "message": "Price conditions could not be checked",
            "action": "none",
        }

        # Get stock
        stock: Stock | None = StockService.find_by_symbol(session, service.stock_symbol)

        # Combined validation checks
        if not stock:
            result["message"] = f"Stock {service.stock_symbol} not found"
        elif (
            not (
                price_history := StockService.get_recent_prices(
                    session,
                    stock.id,
                    90,
                )
            )
            or len(price_history) < TradingStrategyService.MIN_PRICE_DATA_POINTS
        ):
            result["message"] = "Insufficient price history for analysis"
        else:
            # Convert price history to list of float values
            close_prices: list[float] = [
                float(price.close_price) for price in price_history
            ]

            # Get price analysis
            price_analysis: dict[str, any] = (
                TechnicalAnalysisService.get_price_analysis(
                    close_prices,
                )
            )

            if not price_analysis.get("has_data", False):
                result["message"] = "Insufficient price data for analysis"
            elif not (current_price := price_analysis.get("latest_price")):
                result["message"] = "Could not determine current price"
            else:
                # Trading decision - now we're in success state
                result = {
                    "success": True,
                    "service_id": service.id,
                    "stock_symbol": service.stock_symbol,
                    "current_price": current_price,
                    "current_balance": service.current_balance,
                    "current_shares": service.current_shares,
                    "mode": service.mode,
                    "signals": price_analysis.get("signals", {}),
                }

                # Execute strategy based on mode and requested action
                if action == "buy" and bool(service.mode == TradingMode.BUY.value):
                    return TradingStrategyService.execute_buy_strategy(
                        session,
                        service,
                        price_analysis,
                        current_price,
                        result,
                    )
                if action == "sell" and bool(service.mode == TradingMode.SELL.value):
                    return TradingStrategyService.execute_sell_strategy(
                        session,
                        service,
                        price_analysis,
                        current_price,
                        result,
                    )
                result["action"] = "none"
                result["message"] = (
                    f"No action taken for {action} with mode {service.mode}"
                )

        return result
