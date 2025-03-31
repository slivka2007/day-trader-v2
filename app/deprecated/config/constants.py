"""
Centralized constants for the Day Trader application.

This module contains constants used throughout the application,
including service states, decision values, mode settings, and
default configuration values.
"""

from decimal import Decimal
from typing import Dict, Final, List

# Service states
STATE_ACTIVE: Final[str] = "ACTIVE"
STATE_INACTIVE: Final[str] = "INACTIVE"

# Transaction states
STATE_OPEN: Final[str] = "OPEN"
STATE_CLOSED: Final[str] = "CLOSED"

# Trading modes
MODE_BUY: Final[str] = "BUY"
MODE_SELL: Final[str] = "SELL"

# Decision values
DECISION_YES: Final[str] = "YES"
DECISION_NO: Final[str] = "NO"

# Polling intervals (in seconds)
DEFAULT_POLLING_INTERVAL: Final[int] = 300  # 5 minutes
DEMO_POLLING_INTERVAL: Final[int] = 10  # 10 seconds

# Mock data for testing
MOCK_PRICES: Final[Dict[str, Decimal]] = {
    "AAPL": Decimal("175.00"),
    "MSFT": Decimal("390.00"),
    "GOOGL": Decimal("150.00"),
    "AMZN": Decimal("178.00"),
    "META": Decimal("478.00"),
    "TSLA": Decimal("175.00"),
    "NVDA": Decimal("950.00"),
    "NFLX": Decimal("625.00"),
    "PYPL": Decimal("62.00"),
    "INTC": Decimal("31.00"),
}

# Price movement factors for mock implementations
PRICE_MOVEMENT: Final[Dict[str, Decimal]] = {
    "AAPL": Decimal("0.02"),  # 2% movement
    "MSFT": Decimal("0.015"),  # 1.5% movement
    "GOOGL": Decimal("0.025"),  # 2.5% movement
    "AMZN": Decimal("0.03"),  # 3% movement
    "META": Decimal("0.035"),  # 3.5% movement
    "TSLA": Decimal("0.04"),  # 4% movement
    "NVDA": Decimal("0.045"),  # 4.5% movement
    "NFLX": Decimal("0.03"),  # 3% movement
    "PYPL": Decimal("0.025"),  # 2.5% movement
    "INTC": Decimal("0.02"),  # 2% movement
}

# List of supported stock symbols
SUPPORTED_SYMBOLS: Final[List[str]] = list(MOCK_PRICES.keys())

# Default database configuration
DEFAULT_DB_URI: Final[str] = "sqlite:///app.db"
DEFAULT_ECHO_SQL: Final[bool] = False

# API rate limits
API_RATE_LIMIT: Final[int] = 60  # requests per minute
