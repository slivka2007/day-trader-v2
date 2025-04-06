"""
Stock Buy API for making buy decisions.

This module provides the interface for determining whether to buy
a specific stock based on market conditions and analysis.
"""

import logging
from typing import Literal

from app.deprecated.exceptions.exceptions import APIError, InvalidSymbolError
from app.deprecated.services.stock_buy_logic import should_buy

logger = logging.getLogger(__name__)


def should_buy_stock(stock_symbol: str) -> Literal["YES", "NO"]:
    """
    Determine whether to buy a specific stock based on market analysis.

    This function serves as an API layer that delegates the actual decision-making
    logic to the algorithm layer. It handles API-specific error wrapping and logging.

    Args:
        stock_symbol: Symbol of the stock to evaluate

    Returns:
        'YES' if the stock should be purchased, 'NO' otherwise

    Raises:
        InvalidSymbolError: If the stock symbol is not supported
        APIError: If the decision algorithm fails
    """
    logger.info(f"API: Evaluating whether to buy {stock_symbol}")

    try:
        # Delegate to the algorithm layer
        decision = should_buy(stock_symbol)

        logger.info(f"API: Buy decision for {stock_symbol}: {decision}")
        return decision

    except InvalidSymbolError:
        # Re-raise validation errors
        logger.error(f"API: Invalid stock symbol: {stock_symbol}")
        raise
    except Exception as e:
        # Wrap other exceptions in APIError
        logger.error(
            f"API: Error in buy decision algorithm for {stock_symbol}: {str(e)}"
        )
        raise APIError(f"Buy decision algorithm failed for {stock_symbol}: {str(e)}")
