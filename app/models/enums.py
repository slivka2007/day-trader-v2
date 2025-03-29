"""
Enumeration types for database models.

This module defines enumerations that represent constrained values in models,
ensuring type safety and consistency when working with state fields. These
enumerations are used throughout the application to represent various states,
modes, and categories with predefined sets of valid values.

All enumerations extend the EnumBase class which provides consistent string
serialization and additional helper methods.
"""
import logging
from enum import auto
from typing import Dict, Set

from app.models.base import EnumBase

# Set up logging
logger = logging.getLogger(__name__)

class ServiceState(EnumBase):
    """
    Service operational states.
    
    Represents the possible operational states of a trading service:
    
    - ACTIVE: Service is running and can process transactions
    - INACTIVE: Service is not running (either never started or explicitly stopped)
    - PAUSED: Service is temporarily suspended but can be resumed
    - ERROR: Service encountered an error and needs attention
    """
    ACTIVE = auto()
    INACTIVE = auto()
    PAUSED = auto()
    ERROR = auto()
    
    @classmethod
    def active_states(cls) -> Set[str]:
        """Get the set of states where the service is considered operational."""
        return {cls.ACTIVE.value}
    
    @classmethod
    def is_active(cls, state: str) -> bool:
        """Check if the given state is considered active/operational."""
        return state in cls.active_states()

class TradingMode(EnumBase):
    """
    Trading mode for services.
    
    Represents the current trading strategy mode:
    
    - BUY: Service is looking for opportunities to buy
    - SELL: Service is looking for opportunities to sell
    - HOLD: Service is holding current positions without buying or selling
    """
    BUY = auto()
    SELL = auto()
    HOLD = auto()
    
    @classmethod
    def can_execute_transactions(cls, mode: str) -> bool:
        """Check if transactions can be executed in this mode."""
        return mode in {cls.BUY.value, cls.SELL.value}
    
    @classmethod
    def opposite_mode(cls, mode: str) -> str:
        """Get the opposite trading mode (BUY -> SELL, SELL -> BUY, HOLD -> HOLD)."""
        try:
            if mode == cls.BUY.value:
                return cls.SELL.value
            elif mode == cls.SELL.value:
                return cls.BUY.value
            else:
                return mode
        except Exception as e:
            logger.error(f"Error getting opposite mode for {mode}: {str(e)}")
            return mode

class TransactionState(EnumBase):
    """
    Transaction states.
    
    Represents the possible states of a trading transaction:
    
    - OPEN: Purchase executed, not yet sold
    - CLOSED: Fully executed (purchased and sold)
    - CANCELLED: Transaction cancelled before completion
    """
    OPEN = auto()     # Purchase executed, not yet sold
    CLOSED = auto()   # Fully executed (purchased and sold)
    CANCELLED = auto() # Transaction cancelled
    
    @classmethod
    def terminal_states(cls) -> Set[str]:
        """Get the set of states where the transaction is considered complete."""
        return {cls.CLOSED.value, cls.CANCELLED.value}
    
    @classmethod
    def is_terminal(cls, state: str) -> bool:
        """Check if the transaction is in a terminal state (cannot be changed further)."""
        return state in cls.terminal_states()
    
    @classmethod
    def can_be_cancelled(cls, state: str) -> bool:
        """Check if a transaction in this state can be cancelled."""
        return state == cls.OPEN.value

class PriceSource(EnumBase):
    """
    Source of price data.
    
    Represents the origin of price data:
    
    - REAL_TIME: Live price data from exchanges
    - DELAYED: Delayed price data (typically 15-20 minutes)
    - SIMULATED: Simulated or generated price data for testing
    - HISTORICAL: Historical price data from past periods
    """
    REAL_TIME = auto()
    DELAYED = auto()
    SIMULATED = auto()
    HISTORICAL = auto()
    
    @classmethod
    def is_real(cls, source: str) -> bool:
        """Check if the price source provides real market data (not simulated)."""
        return source in {cls.REAL_TIME.value, cls.DELAYED.value, cls.HISTORICAL.value}
    
    @classmethod
    def for_display(cls) -> Dict[str, str]:
        """Get a dictionary of sources with display-friendly names."""
        return {
            cls.REAL_TIME.value: "Real-Time",
            cls.DELAYED.value: "Delayed (15min)",
            cls.SIMULATED.value: "Simulated",
            cls.HISTORICAL.value: "Historical"
        }

# Additional enumerations can be added here as needed
class AnalysisTimeframe(EnumBase):
    """
    Timeframes for analysis.
    
    Represents standard time periods for financial analysis:
    
    - INTRADAY: Within a single trading day
    - DAILY: Day-to-day analysis
    - WEEKLY: Week-to-week analysis
    - MONTHLY: Month-to-month analysis
    - QUARTERLY: Quarter-to-quarter analysis
    - YEARLY: Year-to-year analysis
    """
    INTRADAY = auto()
    DAILY = auto()
    WEEKLY = auto()
    MONTHLY = auto()
    QUARTERLY = auto()
    YEARLY = auto()
    
    @classmethod
    def get_days(cls, timeframe: str) -> int:
        """Get the approximate number of days in this timeframe."""
        days_map = {
            cls.INTRADAY.value: 1,
            cls.DAILY.value: 1,
            cls.WEEKLY.value: 7,
            cls.MONTHLY.value: 30,
            cls.QUARTERLY.value: 90,
            cls.YEARLY.value: 365
        }
        return days_map.get(timeframe, 1) 