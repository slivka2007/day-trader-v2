"""
Stock Sell API for making sell decisions.

This module provides the interface for determining whether to sell
a specific stock based on market conditions and price history.
"""

import logging
import random
from decimal import Decimal
from typing import Literal

from app.constants import DECISION_YES, DECISION_NO, SUPPORTED_SYMBOLS
from app.exceptions import InvalidSymbolError, APIError

logger = logging.getLogger(__name__)


def should_sell_stock(stock_symbol: str, purchase_price: Decimal) -> Literal['YES', 'NO']:
    """
    Determine whether to sell a specific stock based on market analysis.
    
    This function evaluates whether to sell a stock based on the purchase price,
    historical market data, real-time market data, and news sentiment. For testing 
    purposes, it uses a simplified mock implementation that makes randomized decisions.
    
    Args:
        stock_symbol: Symbol of the stock to evaluate
        purchase_price: Original purchase price per share
    
    Returns:
        'YES' if the stock should be sold, 'NO' otherwise
    
    Raises:
        InvalidSymbolError: If the stock symbol is not supported
        APIError: If the decision algorithm fails
    """
    logger.info(f"Evaluating whether to sell {stock_symbol} bought at ${purchase_price}")
    
    # Validate stock symbol
    stock_symbol = stock_symbol.upper()
    if stock_symbol not in SUPPORTED_SYMBOLS:
        logger.error(f"Invalid stock symbol: {stock_symbol}")
        raise InvalidSymbolError(f"Stock symbol {stock_symbol} is not supported")
    
    try:
        # MOCK IMPLEMENTATION FOR TESTING
        # In a real implementation, this would analyze:
        # - Current profit/loss percentage
        # - Historical price data
        # - Current market conditions
        # - Technical indicators
        # - News sentiment
        # - Company fundamentals
        
        # Simplified mock logic - 60% chance to sell for test demo purposes
        sell_probability = 0.6
        if random.random() < sell_probability:
            logger.info(f"Decision: SELL {stock_symbol}")
            return DECISION_YES
        else:
            logger.info(f"Decision: HOLD {stock_symbol}")
            return DECISION_NO
            
    except Exception as e:
        if isinstance(e, InvalidSymbolError):
            # Re-raise validation errors
            raise
        # Wrap other exceptions
        logger.error(f"Error in sell decision algorithm for {stock_symbol}: {str(e)}")
        raise APIError(f"Sell decision algorithm failed for {stock_symbol}: {str(e)}")
