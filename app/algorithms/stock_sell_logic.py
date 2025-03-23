"""
Stock Sell Logic Algorithm

This module implements the decision-making logic for determining
whether to sell a specific stock based on market analysis and purchase price.
"""

import logging
import random
from decimal import Decimal

from app.constants import DECISION_YES, DECISION_NO, MOCK_PRICES, SUPPORTED_SYMBOLS
from app.exceptions import InvalidSymbolError

logger = logging.getLogger(__name__)


def should_sell(stock_symbol: str, purchase_price: Decimal) -> str:
    """
    Determine whether to sell a stock based on market analysis and purchase price.
    
    This algorithm evaluates whether to sell a stock based on technical analysis,
    fundamental analysis, market sentiment, and the difference between current
    price and purchase price. In this implementation, it uses a probability-based
    mock system for demonstration purposes.
    
    Args:
        stock_symbol: Symbol of the stock to evaluate
        purchase_price: The price at which the stock was purchased
        
    Returns:
        DECISION_YES if the stock should be sold, DECISION_NO otherwise
        
    Raises:
        InvalidSymbolError: If the stock symbol is not supported
    """
    logger.debug(f"Running sell decision algorithm for {stock_symbol} purchased at {purchase_price}")
    
    # Validate stock symbol
    stock_symbol = stock_symbol.upper()
    if stock_symbol not in SUPPORTED_SYMBOLS:
        logger.error(f"Invalid stock symbol: {stock_symbol}")
        raise InvalidSymbolError(f"Stock symbol {stock_symbol} is not supported")
    
    # Get current mock price
    current_price = MOCK_PRICES[stock_symbol]
    
    # Calculate price difference percentage
    price_diff_percent = (current_price - purchase_price) / purchase_price * 100
    
    # Adjust sell probability based on price difference
    # Base probability starts at 50%
    base_probability = 0.5
    
    # Profit scenario - higher probability to sell as profit increases
    if price_diff_percent > 0:
        # Scale up probability with profit (max 90% at 20% profit)
        sell_probability = min(0.9, base_probability + (price_diff_percent / 100))
    # Loss scenario - higher probability to hold as loss increases (except for deep losses)
    else:
        # For small losses (<5%), hold with higher probability
        if price_diff_percent > -5:
            sell_probability = max(0.1, base_probability + (price_diff_percent / 100))
        # For moderate losses (5-15%), still mostly hold but increasing sell probability
        elif price_diff_percent > -15:
            sell_probability = max(0.2, base_probability + (price_diff_percent / 200))
        # For severe losses (>15%), higher probability to sell (cut losses)
        else:
            sell_probability = min(0.8, base_probability - (price_diff_percent / 50))
    
    # Stock-specific adjustments to make testing more interesting
    stock_adjustments = {
        "AAPL": -0.1,  # More likely to hold Apple longer
        "MSFT": -0.1,  # More likely to hold Microsoft longer
        "GOOGL": -0.05, # Slightly more likely to hold Google
        "AMZN": 0,     # No adjustment for Amazon
        "META": 0.05,  # Slightly more likely to sell Meta
        "TSLA": 0.1,   # More likely to sell Tesla (volatile)
        "NVDA": -0.15, # Much more likely to hold Nvidia longer
        "NFLX": 0,     # No adjustment for Netflix
        "PYPL": 0.1,   # More likely to sell PayPal
        "INTC": 0.05,  # Slightly more likely to sell Intel
    }
    
    # Apply stock-specific adjustment
    sell_probability += stock_adjustments.get(stock_symbol, 0)
    
    # Ensure probability is within bounds
    sell_probability = max(0.1, min(0.9, sell_probability))
    
    # Make the decision
    if random.random() < sell_probability:
        logger.info(f"Sell algorithm recommends selling {stock_symbol} (bought: ${purchase_price}, current: ${current_price}, diff: {price_diff_percent:.2f}%)")
        return DECISION_YES
    else:
        logger.info(f"Sell algorithm recommends holding {stock_symbol} (bought: ${purchase_price}, current: ${current_price}, diff: {price_diff_percent:.2f}%)")
        return DECISION_NO
