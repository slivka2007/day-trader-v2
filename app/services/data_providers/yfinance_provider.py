"""Stock Market Data API for fetching real-time stock data from Yahoo Finance.

This module provides functionality to retrieve current and historical stock data
from the Yahoo Finance API and map it to the application's database models.
"""

import logging

import pandas as pd
import yfinance as yf

from app.deprecated.config.constants import SUPPORTED_SYMBOLS
from app.deprecated.exceptions.exceptions import DataFetchError, InvalidSymbolError

logger = logging.getLogger(__name__)


def get_stock_info(symbol: str) -> dict[str, any]:
    """Get basic information about a stock from Yahoo Finance.

    Args:
        symbol: The ticker symbol of the stock

    Returns:
        Dictionary containing stock information

    Raises:
        InvalidSymbolError: If the symbol is invalid or not found
        DataFetchError: If there's an error fetching data from Yahoo Finance

    """
    logger.info(f"Fetching stock info for {symbol}")

    try:
        # Normalize symbol
        symbol = symbol.upper()

        # Validate symbol against supported symbols
        if symbol not in SUPPORTED_SYMBOLS:
            logger.error(f"Invalid stock symbol: {symbol}")
            raise InvalidSymbolError(f"Stock symbol {symbol} is not supported")

        # Get stock info from Yahoo Finance
        ticker = yf.Ticker(symbol)
        info = ticker.info

        # Return relevant information
        return {
            "symbol": symbol,
            "name": info.get("shortName", ""),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "current_price": info.get("currentPrice", 0.0),
            "market_cap": info.get("marketCap", 0),
            "beta": info.get("beta", 0.0),
            "pe_ratio": info.get("trailingPE", 0.0),
            "dividend_yield": (
                info.get("dividendYield", 0.0) * 100
                if info.get("dividendYield")
                else 0.0
            ),
        }
    except Exception as e:
        logger.error(f"Error fetching stock info for {symbol}: {e!s}")
        raise DataFetchError(f"Failed to fetch stock info for {symbol}: {e!s}")


def get_intraday_data(
    symbol: str,
    interval: str = "1m",
    period: str = "1d",
) -> list[dict[str, any]]:
    """Get intraday price data for a stock from Yahoo Finance.

    Args:
        symbol: The ticker symbol of the stock
        interval: The time interval between data points (default: '1m')
                 Options: '1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h'
        period: The time period to fetch data for (default: '1d')
                Options: '1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max'

    Returns:
        List of dictionaries containing intraday price data

    Raises:
        InvalidSymbolError: If the symbol is invalid or not found
        DataFetchError: If there's an error fetching data from Yahoo Finance

    """
    logger.info(
        f"Fetching intraday data for {symbol} with interval {interval} for period {period}",
    )

    try:
        # Normalize symbol
        symbol = symbol.upper()

        # Validate symbol against supported symbols
        if symbol not in SUPPORTED_SYMBOLS:
            logger.error(f"Invalid stock symbol: {symbol}")
            raise InvalidSymbolError(f"Stock symbol {symbol} is not supported")

        # Get intraday data from Yahoo Finance
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval)

        # Convert to list of dictionaries
        result = []
        for timestamp, row in hist.iterrows():
            result.append(
                {
                    "timestamp": timestamp.to_pydatetime(),
                    "open": float(row["Open"]) if not pd.isna(row["Open"]) else None,
                    "high": float(row["High"]) if not pd.isna(row["High"]) else None,
                    "low": float(row["Low"]) if not pd.isna(row["Low"]) else None,
                    "close": float(row["Close"]) if not pd.isna(row["Close"]) else None,
                    "volume": (
                        int(row["Volume"]) if not pd.isna(row["Volume"]) else None
                    ),
                },
            )

        return result
    except Exception as e:
        logger.error(f"Error fetching intraday data for {symbol}: {e!s}")
        raise DataFetchError(f"Failed to fetch intraday data for {symbol}: {e!s}")


def get_latest_price(symbol: str) -> dict[str, any]:
    """Get the latest (most recent) price data for a stock.

    Args:
        symbol: The ticker symbol of the stock

    Returns:
        Dictionary containing the latest price data

    Raises:
        InvalidSymbolError: If the symbol is invalid or not found
        DataFetchError: If there's an error fetching data

    """
    logger.info(f"Getting latest price for {symbol}")

    try:
        # Get intraday data (most recent 1 minute)
        intraday_data = get_intraday_data(symbol, interval="1m", period="1d")

        # Return the most recent data point
        if intraday_data:
            return intraday_data[-1]
        raise DataFetchError(f"No price data available for {symbol}")

    except Exception as e:
        logger.error(f"Error getting latest price for {symbol}: {e!s}")
        raise DataFetchError(f"Failed to get latest price for {symbol}: {e!s}")


def get_daily_data(symbol: str, period: str = "1y") -> list[dict[str, any]]:
    """Get daily price data for a stock from Yahoo Finance.

    Args:
        symbol: The ticker symbol of the stock
        period: The time period to fetch data for (default: '1y')
                Options: '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max'

    Returns:
        List of dictionaries containing daily price data

    Raises:
        InvalidSymbolError: If the symbol is invalid or not found
        DataFetchError: If there's an error fetching data from Yahoo Finance

    """
    logger.info(f"Fetching daily data for {symbol} for period {period}")

    try:
        # Normalize symbol
        symbol = symbol.upper()

        # Validate symbol against supported symbols
        if symbol not in SUPPORTED_SYMBOLS:
            logger.error(f"Invalid stock symbol: {symbol}")
            raise InvalidSymbolError(f"Stock symbol {symbol} is not supported")

        # Get daily data from Yahoo Finance
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval="1d")

        # Convert to list of dictionaries
        result = []
        for timestamp, row in hist.iterrows():
            result.append(
                {
                    "date": timestamp.date(),
                    "open": float(row["Open"]) if not pd.isna(row["Open"]) else None,
                    "high": float(row["High"]) if not pd.isna(row["High"]) else None,
                    "low": float(row["Low"]) if not pd.isna(row["Low"]) else None,
                    "close": float(row["Close"]) if not pd.isna(row["Close"]) else None,
                    "volume": (
                        int(row["Volume"]) if not pd.isna(row["Volume"]) else None
                    ),
                    "adjusted_close": (
                        float(row["Close"]) if not pd.isna(row["Close"]) else None
                    ),
                },
            )

        return result
    except Exception as e:
        logger.error(f"Error fetching daily data for {symbol}: {e!s}")
        raise DataFetchError(f"Failed to fetch daily data for {symbol}: {e!s}")


def get_latest_daily_price(symbol: str) -> dict[str, any]:
    """Get the latest (most recent) daily price data for a stock.

    Args:
        symbol: The ticker symbol of the stock

    Returns:
        Dictionary containing the latest daily price data

    Raises:
        InvalidSymbolError: If the symbol is invalid or not found
        DataFetchError: If there's an error fetching data

    """
    logger.info(f"Getting latest daily price for {symbol}")

    try:
        # Get daily data (most recent)
        daily_data = get_daily_data(symbol, period="5d")

        # Return the most recent data point
        if daily_data:
            return daily_data[-1]
        raise DataFetchError(f"No daily price data available for {symbol}")

    except Exception as e:
        logger.error(f"Error getting latest daily price for {symbol}: {e!s}")
        raise DataFetchError(f"Failed to get latest daily price for {symbol}: {e!s}")


def update_stock_model(symbol: str) -> tuple[Stock, bool]:
    """Update or create a Stock model with the latest information.

    Args:
        symbol: The ticker symbol of the stock

    Returns:
        Tuple of (Stock model, is_created flag)

    Raises:
        DataFetchError: If there's an error fetching data

    """
    logger.info(f"Updating stock model for {symbol}")

    try:
        # Get stock info
        stock_info = get_stock_info(symbol)

        # Create or update stock in the database
        session = get_session()
        stock = session.query(Stock).filter(Stock.symbol == symbol).first()

        is_created = False
        if not stock:
            logger.info(f"Creating new stock entry for {symbol}")
            stock = Stock(
                symbol=stock_info["symbol"],
                name=stock_info["name"],
                sector=stock_info["sector"],
                description=stock_info.get("industry", ""),
            )
            session.add(stock)
            is_created = True
        else:
            logger.info(f"Updating existing stock entry for {symbol}")
            stock.name = stock_info["name"]
            stock.sector = stock_info["sector"]
            stock.description = stock_info.get("industry", "")

        try:
            session.commit()
            return stock, is_created
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error updating stock {symbol}: {e!s}")
            raise DataFetchError(
                f"Failed to update stock {symbol} in database: {e!s}",
            )

    except Exception as e:
        logger.error(f"Error updating stock model for {symbol}: {e!s}")
        raise DataFetchError(f"Failed to update stock model for {symbol}: {e!s}")
