# Stock API Modules

This directory contains API modules for interacting with stock market data and executing trades.

## Stock Market Data API

The `stock_market_data_api.py` module provides functionality to retrieve real-time and historical stock data from Yahoo Finance.

### Usage Examples

```python
from app.apis.stock_market_data_api import (
    get_stock_info, 
    get_intraday_data, 
    save_intraday_data,
    get_latest_price,
    get_daily_data,
    save_daily_data,
    get_latest_daily_price
)

# Get basic information about a stock
stock_info = get_stock_info("AAPL")
print(f"Stock Info: {stock_info}")

# Get intraday price data (default is 1-minute intervals for the past day)
intraday_data = get_intraday_data("AAPL")
print(f"Number of intraday data points: {len(intraday_data)}")
print(f"First intraday data point: {intraday_data[0]}")

# Customize the interval and period
intraday_data = get_intraday_data("MSFT", interval="5m", period="5d")
print(f"5-minute intervals for 5 days: {len(intraday_data)} data points")

# Fetch and save intraday data to the database
stock_id, records_saved = save_intraday_data("GOOGL")
print(f"Saved {records_saved} intraday records for stock ID {stock_id}")

# Get the latest intraday price
latest_price = get_latest_price("AMZN")
print(f"Latest intraday price for AMZN: {latest_price}")

# Get daily price data (default is past year)
daily_data = get_daily_data("AAPL")
print(f"Number of daily data points: {len(daily_data)}")
print(f"First daily data point: {daily_data[0]}")

# Fetch and save daily data to the database
stock_id, records_saved = save_daily_data("GOOGL", period="2y")
print(f"Saved {records_saved} daily records for stock ID {stock_id}")

# Get the latest daily price
latest_daily = get_latest_daily_price("AMZN")
print(f"Latest daily price for AMZN: {latest_daily}")
```

## Supported Intervals and Periods

When using the data retrieval functions, the following options are available:

### Intraday Intervals
- `1m`: 1 minute
- `2m`: 2 minutes
- `5m`: 5 minutes
- `15m`: 15 minutes
- `30m`: 30 minutes
- `60m`: 60 minutes
- `90m`: 90 minutes
- `1h`: 1 hour

### Periods
- `1d`: 1 day
- `5d`: 5 days
- `1mo`: 1 month
- `3mo`: 3 months
- `6mo`: 6 months
- `1y`: 1 year
- `2y`: 2 years
- `5y`: 5 years
- `10y`: 10 years
- `ytd`: Year to date
- `max`: Maximum available

Note that not all combinations of interval and period are valid. For example, 1-minute data is only available for a few days. 