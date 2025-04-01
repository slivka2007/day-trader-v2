"""
Models package for the Day Trader application.

This package contains all SQLAlchemy models used by the application.
"""

from app.models.base import Base
from app.models.enums import (
    AnalysisTimeframe,
    PriceSource,
    ServiceAction,
    ServiceState,
    TradingMode,
    TransactionState,
)

# Import all model classes for SQLAlchemy's metadata
from app.models.stock import Stock
from app.models.stock_daily_price import StockDailyPrice
from app.models.stock_intraday_price import StockIntradayPrice
from app.models.trading_service import TradingService
from app.models.trading_transaction import TradingTransaction
from app.models.user import User

# Exposed for easier imports
__all__: list[str] = [
    "Base",
    "Stock",
    "StockDailyPrice",
    "StockIntradayPrice",
    "TradingService",
    "TradingTransaction",
    "User",
    "ServiceState",
    "ServiceAction",
    "TradingMode",
    "TransactionState",
    "PriceSource",
    "AnalysisTimeframe",
]
