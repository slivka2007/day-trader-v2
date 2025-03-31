"""
Stock Buy Logic Algorithm

This module implements the decision-making logic for determining
whether to buy a specific stock based on market analysis.
"""

import logging
import random

from app.config.constants import DECISION_NO, DECISION_YES, SUPPORTED_SYMBOLS
from app.exceptions.exceptions import InvalidSymbolError

logger = logging.getLogger(__name__)


def should_buy(stock_symbol: str) -> str:
    """
    Determine whether to buy a stock based on market analysis.

    This algorithm evaluates whether to buy a stock based on technical analysis,
    fundamental analysis, and market sentiment. In this implementation, it uses
    a probability-based mock system for demonstration purposes.

    Args:
        stock_symbol: Symbol of the stock to evaluate

    Returns:
        DECISION_YES if the stock should be purchased, DECISION_NO otherwise

    Raises:
        InvalidSymbolError: If the stock symbol is not supported
    """
    logger.debug(f"Running buy decision algorithm for {stock_symbol}")

    # Validate stock symbol
    stock_symbol = stock_symbol.upper()
    if stock_symbol not in SUPPORTED_SYMBOLS:
        logger.error(f"Invalid stock symbol: {stock_symbol}")
        raise InvalidSymbolError(f"Stock symbol {stock_symbol} is not supported")

    # Different stocks have different buy probabilities to make testing more interesting
    probabilities = {
        "AAPL": 0.75,  # Apple - higher probability to buy
        "MSFT": 0.70,  # Microsoft - higher probability to buy
        "GOOGL": 0.65,  # Google - moderate-high probability
        "AMZN": 0.60,  # Amazon - moderate probability
        "META": 0.55,  # Meta - moderate probability
        "TSLA": 0.50,  # Tesla - even probability (volatile)
        "NVDA": 0.75,  # Nvidia - higher probability to buy
        "NFLX": 0.55,  # Netflix - moderate probability
        "PYPL": 0.45,  # PayPal - moderate-low probability
        "INTC": 0.40,  # Intel - lower probability to buy
    }

    # Get the probability for this stock or use a default
    buy_probability = probabilities.get(stock_symbol, 0.5)

    # Make the decision
    if random.random() < buy_probability:
        logger.info(f"Buy algorithm recommends buying {stock_symbol}")
        return DECISION_YES
    else:
        logger.info(f"Buy algorithm recommends not buying {stock_symbol}")
        return DECISION_NO
