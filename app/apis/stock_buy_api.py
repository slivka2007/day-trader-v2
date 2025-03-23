"""
Stock Buy API for making buy decisions.

This module provides the interface for determining whether to buy
a specific stock based on market conditions and analysis.
"""

import logging
import random
from typing import Literal

from app.constants import DECISION_YES, DECISION_NO, SUPPORTED_SYMBOLS
from app.exceptions import InvalidSymbolError, APIError

logger = logging.getLogger(__name__)


def should_buy_stock(stock_symbol: str) -> Literal['YES', 'NO']:
    """
    Determine whether to buy a specific stock based on market analysis.
    
    This function evaluates whether to buy a stock based on historical market data,
    real-time market data, and news sentiment. For testing purposes, it uses
    a simplified mock implementation that makes randomized decisions.
    
    Args:
        stock_symbol: Symbol of the stock to evaluate
    
    Returns:
        'YES' if the stock should be purchased, 'NO' otherwise
    
    Raises:
        InvalidSymbolError: If the stock symbol is not supported
        APIError: If the decision algorithm fails
    """
    logger.info(f"Evaluating whether to buy {stock_symbol}")
    
    # Validate stock symbol
    stock_symbol = stock_symbol.upper()
    if stock_symbol not in SUPPORTED_SYMBOLS:
        logger.error(f"Invalid stock symbol: {stock_symbol}")
        raise InvalidSymbolError(f"Stock symbol {stock_symbol} is not supported")
    
    try:
        # MOCK IMPLEMENTATION FOR TESTING
        # In a real implementation, this would analyze:
        # - Historical price data
        # - Current market conditions
        # - Technical indicators
        # - News sentiment
        # - Company fundamentals
        
        # Simplified mock logic - 70% chance to buy for test demo purposes
        buy_probability = 0.7
        if random.random() < buy_probability:
            logger.info(f"Decision: BUY {stock_symbol}")
            return DECISION_YES
        else:
            logger.info(f"Decision: DO NOT BUY {stock_symbol}")
            return DECISION_NO
            
    except Exception as e:
        if isinstance(e, InvalidSymbolError):
            # Re-raise validation errors
            raise
        # Wrap other exceptions
        logger.error(f"Error in buy decision algorithm for {stock_symbol}: {str(e)}")
        raise APIError(f"Buy decision algorithm failed for {stock_symbol}: {str(e)}")
