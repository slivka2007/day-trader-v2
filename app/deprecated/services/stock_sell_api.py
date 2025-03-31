"""
Stock Sell API for making sell decisions.

This module provides the interface for determining whether to sell
a specific stock based on market conditions and price history.
"""

import logging
from decimal import Decimal
from typing import Literal

from app.deprecated.exceptions.exceptions import APIError, InvalidSymbolError
from app.deprecated.services.stock_sell_logic import should_sell

logger = logging.getLogger(__name__)


def should_sell_stock(
    stock_symbol: str, purchase_price: Decimal
) -> Literal["YES", "NO"]:
    """
    Determine whether to sell a specific stock based on market analysis.

    This function serves as an API layer that delegates the actual decision-making
    logic to the algorithm layer. It handles API-specific error wrapping and logging.

    Args:
        stock_symbol: Symbol of the stock to evaluate
        purchase_price: Original purchase price per share

    Returns:
        'YES' if the stock should be sold, 'NO' otherwise

    Raises:
        InvalidSymbolError: If the stock symbol is not supported
        APIError: If the decision algorithm fails
    """
    logger.info(
        f"API: Evaluating whether to sell {stock_symbol} bought at ${purchase_price}"
    )

    try:
        # Delegate to the algorithm layer
        decision = should_sell(stock_symbol, purchase_price)

        logger.info(f"API: Sell decision for {stock_symbol}: {decision}")
        return decision

    except InvalidSymbolError:
        # Re-raise validation errors
        logger.error(f"API: Invalid stock symbol: {stock_symbol}")
        raise
    except Exception as e:
        # Wrap other exceptions in APIError
        logger.error(
            f"API: Error in sell decision algorithm for {stock_symbol}: {str(e)}"
        )
        raise APIError(f"Sell decision algorithm failed for {stock_symbol}: {str(e)}")
