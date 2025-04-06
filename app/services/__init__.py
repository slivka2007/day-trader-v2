"""Services package for the Day Trader application.

This package contains service modules that provide application-wide functionality
that is not tied to a specific model or resource.
"""

from app.services.daily_price_service import DailyPriceService
from app.services.database import get_session, setup_database
from app.services.events import EventService
from app.services.intraday_price_service import IntradayPriceService
from app.services.session_manager import SessionManager
from app.services.stock_service import StockService
from app.services.technical_analysis_service import TechnicalAnalysisService
from app.services.trading_service import TradingServiceService
from app.services.transaction_service import TransactionService
from app.services.user_service import UserService

__all__: list[str] = [
    "DailyPriceService",
    "EventService",
    "IntradayPriceService",
    "SessionManager",
    "StockService",
    "TechnicalAnalysisService",
    "TradingServiceService",
    "TransactionService",
    "UserService",
    "get_session",
    "setup_database",
]
