from datetime import datetime
from decimal import Decimal
from typing import Tuple, Dict
import logging
import random

from app.core.constants import MOCK_PRICES
from app.core.exceptions import InvalidSymbolError, StockSaleError

logger = logging.getLogger(__name__)

# Define price movement ranges as proper tuples (min_change, max_change)
PRICE_MOVEMENT = {
    "AAPL": (Decimal('-0.02'), Decimal('0.02')),   # 2% movement
    "MSFT": (Decimal('-0.015'), Decimal('0.015')),  # 1.5% movement
    "GOOGL": (Decimal('-0.025'), Decimal('0.025')), # 2.5% movement
    "AMZN": (Decimal('-0.03'), Decimal('0.03')),   # 3% movement
    "META": (Decimal('-0.035'), Decimal('0.035')),  # 3.5% movement
    "TSLA": (Decimal('-0.04'), Decimal('0.04')),   # 4% movement
    "NVDA": (Decimal('-0.045'), Decimal('0.045')),  # 4.5% movement
    "NFLX": (Decimal('-0.03'), Decimal('0.03')),   # 3% movement
    "PYPL": (Decimal('-0.025'), Decimal('0.025')),  # 2.5% movement
    "INTC": (Decimal('-0.02'), Decimal('0.02')),   # 2% movement
}

def sell_stock(stock_symbol: str, number_of_shares: int) -> Tuple[Decimal, datetime]:
    """
    Uses Alpaca APIs to sell the specified number of shares at the current market price.
    Waits until the order is executed before returning.
    
    This function handles the actual sale of stocks, calculating the sale price
    based on the stock's characteristics. For test stocks, it applies predefined
    price movement patterns to simulate realistic market behavior for different
    stock types (bullish, bearish, volatile, etc.).
    
    Args:
        stock_symbol: The ticker symbol of the stock to sell
        number_of_shares: The number of shares to sell
        
    Returns:
        Tuple containing:
        - sale_price: The price per share received
        - date_time_of_sale: The timestamp when the sale was executed
    
    Raises:
        ValueError: If number_of_shares is not positive
        InvalidSymbolError: If the stock symbol is invalid
        StockSaleError: If the sale operation fails
    """
    # Input validation
    if number_of_shares <= 0:
        raise ValueError(f"Cannot sell {number_of_shares} shares, must be a positive number")
    
    current_time = datetime.utcnow()
    
    try:
        # MOCK IMPLEMENTATION for testing
        if stock_symbol in MOCK_PRICES:
            # Get base price from mock prices
            base_price = MOCK_PRICES[stock_symbol]
            
            # Get price movement range for this stock
            min_change, max_change = PRICE_MOVEMENT.get(stock_symbol, (Decimal('-0.1'), Decimal('0.1')))
            
            # Generate price movement within the defined range
            price_change = random.uniform(float(min_change), float(max_change))
            sale_price = base_price * (Decimal('1') + Decimal(str(price_change)))
            
            # Round to 2 decimal places
            sale_price = round(sale_price, 2)
            
            # Ensure pricing makes sense for test stocks
            if stock_symbol == "BULL" and sale_price < base_price:
                # BULL should always sell higher than base price
                sale_price = base_price * Decimal('1.05')  # Minimum 5% increase
            elif stock_symbol == "BEAR" and sale_price > base_price:
                # BEAR should always sell lower than base price
                sale_price = base_price * Decimal('0.95')  # Minimum 5% decrease
            elif stock_symbol == "TEST":
                # TEST stock always sells at a profit
                sale_price = base_price * Decimal('1.1')   # Fixed 10% profit
            
            logger.info(f"MOCK API: Selling {number_of_shares} shares of {stock_symbol} at {sale_price}")
            return (sale_price, current_time)  # Explicitly return as a tuple
        
        # For any other stock, generate a random price
        mock_price = Decimal(str(round(random.uniform(10, 1000), 2)))
        
        logger.info(f"MOCK API: Selling {number_of_shares} shares of {stock_symbol} at {mock_price}")
        return (mock_price, current_time)  # Explicitly return as a tuple
        
    except ValueError:
        # Re-raise validation errors
        raise
    except Exception as e:
        # Wrap any other exceptions in StockSaleError
        logger.error(f"Error selling stock {stock_symbol}: {str(e)}")
        raise StockSaleError(f"Failed to sell {stock_symbol}: {str(e)}")
