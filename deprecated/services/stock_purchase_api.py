"""
Stock Purchase API for buying stocks.

This module provides the interface for purchasing stocks through
either a real trading platform or a mock implementation for testing.
"""

import logging
import random
from datetime import datetime
from decimal import Decimal
from typing import Tuple

from app.config.constants import MOCK_PRICES, PRICE_MOVEMENT, SUPPORTED_SYMBOLS
from app.exceptions.exceptions import InvalidSymbolError, StockPurchaseError

logger = logging.getLogger(__name__)


def purchase_stock(
    stock_symbol: str, available_funds: Decimal
) -> Tuple[int, Decimal, datetime]:
    """
    Purchase a stock with the given symbol using available funds.

    This function handles stock purchases by determining the current price
    of the stock and calculating how many shares can be purchased with the
    available funds. For testing purposes, it uses a mock implementation
    that simulates price variations based on predefined movement factors.

    Args:
        stock_symbol: Symbol of the stock to purchase
        available_funds: Amount of funds available for the purchase

    Returns:
        A tuple containing (number_of_shares, purchase_price, date_time_of_purchase)

    Raises:
        InvalidSymbolError: If the stock symbol is not supported
        StockPurchaseError: If the purchase operation fails
    """
    logger.info(
        f"Purchasing stock {stock_symbol} with available funds: ${available_funds}"
    )

    # Validate stock symbol
    stock_symbol = stock_symbol.upper()
    if stock_symbol not in SUPPORTED_SYMBOLS:
        logger.error(f"Invalid stock symbol: {stock_symbol}")
        raise InvalidSymbolError(f"Stock symbol {stock_symbol} is not supported")

    try:
        # Get base price for the stock
        base_price = MOCK_PRICES[stock_symbol]

        # Calculate a random price movement (up to the movement factor)
        movement_factor = PRICE_MOVEMENT[stock_symbol]
        price_movement = random.uniform(-float(movement_factor), float(movement_factor))

        # Calculate current price with movement
        current_price = base_price * (1 + Decimal(str(price_movement)))
        current_price = current_price.quantize(
            Decimal("0.01")
        )  # Round to 2 decimal places

        # Calculate how many shares we can buy with available funds
        # Leave a small buffer to account for rounding
        max_shares = int(available_funds / current_price * Decimal("0.99"))

        # Ensure we purchase at least 1 share if funds allow
        if max_shares <= 0:
            logger.warning(
                f"Insufficient funds (${available_funds}) to purchase {stock_symbol} at ${current_price}"
            )
            raise StockPurchaseError(
                f"Insufficient funds (${available_funds}) to purchase {stock_symbol} at ${current_price}"
            )

        # Record purchase time
        purchase_time = datetime.utcnow()

        logger.info(
            f"Purchased {max_shares} shares of {stock_symbol} at ${current_price} per share"
        )
        return max_shares, current_price, purchase_time

    except Exception as e:
        if isinstance(e, (InvalidSymbolError, StockPurchaseError)):
            # Re-raise known exceptions
            raise
        # Wrap unknown exceptions
        logger.error(f"Error purchasing stock {stock_symbol}: {str(e)}")
        raise StockPurchaseError(f"Failed to purchase stock {stock_symbol}: {str(e)}")
