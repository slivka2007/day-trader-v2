"""Stock Market Data API for fetching real-time stock data from Yahoo Finance.

This module provides functionality to retrieve current and historical stock data
from the Yahoo Finance API and map it to the application's database models.
"""

import logging
from json.decoder import JSONDecodeError
from urllib.error import HTTPError, URLError

import pandas as pd
import yfinance as yf

from app.utils.errors import APIError, StockError
from app.utils.validators import validate_stock_symbol

logger: logging.Logger = logging.getLogger(__name__)


def _raise_api_error(
    error_type: str,
    symbol: str,
    exception: Exception,
    message: str,
) -> None:
    """Raise an API error with consistent formatting and logging.

    Args:
        error_type: Error type constant from APIError class
        symbol: Stock symbol related to the error
        exception: Original exception being handled
        message: Log message to use

    Raises:
        APIError: With appropriate payload and exception chaining

    """
    logger.exception(message, symbol)
    raise APIError(
        error_type,
        payload={"symbol": symbol, "error": str(exception)},
    ) from exception


def get_stock_info(symbol: str) -> dict[str, any]:
    """Get basic information about a stock from Yahoo Finance.

    Args:
        symbol: The ticker symbol of the stock

    Returns:
        Dictionary containing stock information

    Raises:
        StockError: If the symbol is invalid or not found
        APIError: If there's an error fetching data from Yahoo Finance

    """
    logger.info("Fetching stock info for %s", symbol)

    try:
        # Validate and normalize symbol
        symbol = validate_stock_symbol(symbol, StockError)

        # Get stock info from Yahoo Finance
        ticker: yf.Ticker = yf.Ticker(symbol)
        info: dict[str, any] = ticker.info

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
    except StockError:
        # Re-raise stock validation errors
        raise
    except (HTTPError, URLError, ConnectionError) as e:
        _raise_api_error(
            APIError.FETCH_STOCK_INFO_ERROR,
            symbol,
            e,
            "Network error fetching stock info for %s",
        )
    except (ValueError, KeyError, JSONDecodeError, AttributeError) as e:
        _raise_api_error(
            APIError.PROCESS_STOCK_DATA_ERROR,
            symbol,
            e,
            "Data processing error for %s",
        )


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
                Options: '1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y',
                'ytd', 'max'

    Returns:
        List of dictionaries containing intraday price data

    Raises:
        StockError: If the symbol is invalid or not found
        APIError: If there's an error fetching data from Yahoo Finance

    """
    logger.info(
        "Fetching intraday data for %s with interval %s for period %s",
        symbol,
        interval,
        period,
    )

    try:
        # Validate and normalize symbol
        symbol = validate_stock_symbol(symbol, StockError)

        # Get intraday data from Yahoo Finance
        ticker: yf.Ticker = yf.Ticker(symbol)
        hist: pd.DataFrame = ticker.history(period=period, interval=interval)

        # Convert to list of dictionaries
        result: list[dict[str, any]] = []
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

    except StockError:
        # Re-raise stock validation errors
        raise
    except (HTTPError, URLError, ConnectionError) as e:
        _raise_api_error(
            APIError.FETCH_INTRADAY_DATA_ERROR,
            symbol,
            e,
            "Network error fetching intraday data for %s",
        )
    except (ValueError, KeyError, AttributeError, TypeError) as e:
        _raise_api_error(
            APIError.PROCESS_INTRADAY_DATA_ERROR,
            symbol,
            e,
            "Data processing error for %s",
        )
    return result


def get_latest_price(symbol: str) -> dict[str, any]:
    """Get the latest (most recent) price data for a stock.

    Args:
        symbol: The ticker symbol of the stock

    Returns:
        Dictionary containing the latest price data

    Raises:
        StockError: If the symbol is invalid or not found
        APIError: If there's an error fetching data

    """
    logger.info("Getting latest price for %s", symbol)

    try:
        # Get intraday data (most recent 1 minute)
        intraday_data: list[dict[str, any]] = get_intraday_data(
            symbol,
            interval="1m",
            period="1d",
        )

        # Return the most recent data point
        if intraday_data:
            return intraday_data[-1]
        raise _raise_api_error(
            APIError.NO_PRICE_DATA_ERROR,
            symbol,
            None,
            "No price data available for %s",
        )

    except StockError:
        # Re-raise stock validation errors
        raise
    except APIError:
        # Re-raise API errors
        raise
    except (IndexError, KeyError, TypeError) as e:
        _raise_api_error(
            APIError.LATEST_PRICE_ERROR,
            symbol,
            e,
            "Data processing error for %s",
        )


def get_daily_data(symbol: str, period: str = "1y") -> list[dict[str, any]]:
    """Get daily price data for a stock from Yahoo Finance.

    Args:
        symbol: The ticker symbol of the stock
        period: The time period to fetch data for (default: '1y')
                Options: '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max'

    Returns:
        List of dictionaries containing daily price data

    Raises:
        StockError: If the symbol is invalid or not found
        APIError: If there's an error fetching data from Yahoo Finance

    """
    logger.info("Fetching daily data for %s for period %s", symbol, period)

    try:
        # Validate and normalize symbol
        symbol = validate_stock_symbol(symbol, StockError)

        # Get daily data from Yahoo Finance
        ticker: yf.Ticker = yf.Ticker(symbol)
        hist: pd.DataFrame = ticker.history(period=period, interval="1d")

        # Convert to list of dictionaries
        result: list[dict[str, any]] = []
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

    except StockError:
        # Re-raise stock validation errors
        raise
    except (HTTPError, URLError, ConnectionError) as e:
        _raise_api_error(
            APIError.FETCH_DAILY_DATA_ERROR,
            symbol,
            e,
            "Network error fetching daily data for %s",
        )
    except (ValueError, KeyError, AttributeError, TypeError) as e:
        _raise_api_error(
            APIError.PROCESS_DAILY_DATA_ERROR,
            symbol,
            e,
            "Data processing error for %s",
        )
    return result


def get_latest_daily_price(symbol: str) -> dict[str, any]:
    """Get the latest (most recent) daily price data for a stock.

    Args:
        symbol: The ticker symbol of the stock

    Returns:
        Dictionary containing the latest daily price data

    Raises:
        StockError: If the symbol is invalid or not found
        APIError: If there's an error fetching data

    """
    logger.info("Getting latest daily price for %s", symbol)

    try:
        # Get daily data (most recent)
        daily_data: list[dict[str, any]] = get_daily_data(symbol, period="5d")

        # Return the most recent data point
        if daily_data:
            return daily_data[-1]
        raise _raise_api_error(
            APIError.NO_DAILY_PRICE_DATA_ERROR,
            symbol,
            None,
            "No daily price data available for %s",
        )

    except StockError:
        # Re-raise stock validation errors
        raise
    except APIError:
        # Re-raise API errors
        raise
    except (IndexError, KeyError, TypeError) as e:
        _raise_api_error(
            APIError.LATEST_DAILY_PRICE_ERROR,
            symbol,
            e,
            "Data processing error for %s",
        )
