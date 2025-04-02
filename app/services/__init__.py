"""Services package for the Day Trader application.

This package contains service modules that provide application-wide functionality
that is not tied to a specific model or resource.
"""

from app.services.database import get_session, setup_database
from app.services.events import EventService
from app.services.price_service import PriceService
from app.services.session_manager import SessionManager
from app.services.stock_service import StockService
from app.services.trading_service import TradingServiceService
from app.services.transaction_service import TransactionService
from app.services.user_service import UserService

__all__: list[str] = [
    "EventService",
    "PriceService",
    "SessionManager",
    "StockService",
    "TradingServiceService",
    "TransactionService",
    "UserService",
    "get_session",
    "setup_database",
]
