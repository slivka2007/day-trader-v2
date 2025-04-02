"""Enumeration types for database models.

This module defines enumerations that represent constrained values in models,
ensuring type safety and consistency when working with state fields. These
enumerations are used throughout the application to represent various states,
modes, and categories with predefined sets of valid values.

All enumerations extend the EnumBase class which provides consistent string
serialization and additional helper methods.
"""

import logging
from enum import auto

from app.models.base import EnumBase

# Set up logging
logger: logging.Logger = logging.getLogger(__name__)


class ServiceState(EnumBase):
    """Service operational states.

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
    def active_states(cls) -> set[str]:
        """Get the set of states where the service is considered operational."""
        return cls.ACTIVE.value

    @classmethod
    def is_active(cls, state: str) -> bool:
        """Check if the given state is considered active/operational."""
        return state in cls.active_states()

    @classmethod
    def is_paused(cls, state: str) -> bool:
        """Check if the given state is considered paused."""
        return state in cls.PAUSED.value

    @classmethod
    def is_inactive(cls, state: str) -> bool:
        """Check if the given state is considered inactive."""
        return state in cls.INACTIVE.value

    @classmethod
    def is_error(cls, state: str) -> bool:
        """Check if the given state is considered in an error state."""
        return state in cls.ERROR.value


class ServiceAction(EnumBase):
    """Actions that can be taken on a service.

    Represents the possible actions that can be taken on a service:

    - CHECK_BUY: Check for a buy opportunity
    - CHECK_SELL: Check for a sell opportunity
    """

    CHECK_BUY = auto()
    CHECK_SELL = auto()

    @classmethod
    def is_check_buy(cls, action: str) -> bool:
        """Check if the given action is a check for a buy opportunity."""
        return action == cls.CHECK_BUY.value

    @classmethod
    def is_check_sell(cls, action: str) -> bool:
        """Check if the given action is a check for a sell opportunity."""
        return action == cls.CHECK_SELL.value


class TradingMode(EnumBase):
    """Trading mode for services.

    Represents the current trading strategy mode:

    - BUY: Service is looking for opportunities to buy
    - SELL: Service is looking for opportunities to sell
    - HOLD: Service is holding current positions without buying or selling
    """

    BUY = auto()
    SELL = auto()
    HOLD = auto()

    @classmethod
    def is_buy(cls, mode: str) -> bool:
        """Check if the given mode is a buy mode."""
        return mode == cls.BUY.value

    @classmethod
    def is_sell(cls, mode: str) -> bool:
        """Check if the given mode is a sell mode."""
        return mode == cls.SELL.value

    @classmethod
    def is_hold(cls, mode: str) -> bool:
        """Check if the given mode is a hold mode."""
        return mode == cls.HOLD.value

    @classmethod
    def can_execute_transactions(cls, mode: str) -> bool:
        """Check if transactions can be executed in this mode."""
        return mode in {cls.BUY.value, cls.SELL.value}

    @classmethod
    def opposite_mode(cls, mode: str) -> str:
        """Get the opposite trading mode (BUY -> SELL, SELL -> BUY, HOLD -> HOLD)."""
        if mode == cls.BUY.value:
            return cls.SELL.value
        if mode == cls.SELL.value:
            return cls.BUY.value
        return mode


class TransactionState(EnumBase):
    """Transaction states.

    Represents the possible states of a trading transaction:

    - OPEN: Purchase executed, not yet sold
    - CLOSED: Fully executed (purchased and sold)
    - CANCELLED: Transaction cancelled before completion
    """

    OPEN = auto()  # Purchase executed, not yet sold
    CLOSED = auto()  # Fully executed (purchased and sold)
    CANCELLED = auto()  # Transaction cancelled

    @classmethod
    def is_open(cls, state: str) -> bool:
        """Check if the given state is an open transaction."""
        return state == cls.OPEN.value

    @classmethod
    def is_closed(cls, state: str) -> bool:
        """Check if the given state is a closed transaction."""
        return state == cls.CLOSED.value

    @classmethod
    def is_cancelled(cls, state: str) -> bool:
        """Check if the given state is a cancelled transaction."""
        return state == cls.CANCELLED.value

    @classmethod
    def terminal_states(cls) -> set[str]:
        """Get the set of states where the transaction is considered complete."""
        return {cls.CLOSED.value, cls.CANCELLED.value}

    @classmethod
    def is_terminal(cls, state: str) -> bool:
        """Check if the transaction is in a terminal state.

        (cannot be changed further).
        """
        return state in cls.terminal_states()

    @classmethod
    def can_be_cancelled(cls, state: str) -> bool:
        """Check if a transaction in this state can be cancelled."""
        return state == cls.OPEN.value


class PriceSource(EnumBase):
    """Source of price data.

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
    def is_delayed(cls, source: str) -> bool:
        """Check if the price source is delayed."""
        return source == cls.DELAYED.value

    @classmethod
    def is_simulated(cls, source: str) -> bool:
        """Check if the price source is simulated."""
        return source == cls.SIMULATED.value

    @classmethod
    def is_historical(cls, source: str) -> bool:
        """Check if the price source is historical."""
        return source == cls.HISTORICAL.value

    @classmethod
    def is_real_time(cls, source: str) -> bool:
        """Check if the price source provides real market data (not simulated)."""
        return source == cls.REAL_TIME.value

    @classmethod
    def is_real(cls, source: str) -> bool:
        """Check if the price source provides real market data (not simulated)."""
        return source in {cls.REAL_TIME.value, cls.DELAYED.value, cls.HISTORICAL.value}

    @classmethod
    def for_display(cls) -> dict[str, str]:
        """Get a dictionary of sources with display-friendly names."""
        return {
            cls.REAL_TIME.value: "Real-Time",
            cls.DELAYED.value: "Delayed (15min)",
            cls.SIMULATED.value: "Simulated",
            cls.HISTORICAL.value: "Historical",
        }


# Additional enumerations can be added here as needed
class AnalysisTimeframe(EnumBase):
    """Timeframes for analysis.

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
    def is_intraday(cls, timeframe: str) -> bool:
        """Check if the given timeframe is intraday."""
        return timeframe == cls.INTRADAY.value

    @classmethod
    def is_daily(cls, timeframe: str) -> bool:
        """Check if the given timeframe is daily."""
        return timeframe == cls.DAILY.value

    @classmethod
    def is_weekly(cls, timeframe: str) -> bool:
        """Check if the given timeframe is weekly."""
        return timeframe == cls.WEEKLY.value

    @classmethod
    def is_monthly(cls, timeframe: str) -> bool:
        """Check if the given timeframe is monthly."""
        return timeframe == cls.MONTHLY.value

    @classmethod
    def is_quarterly(cls, timeframe: str) -> bool:
        """Check if the given timeframe is quarterly."""
        return timeframe == cls.QUARTERLY.value

    @classmethod
    def is_yearly(cls, timeframe: str) -> bool:
        """Check if the given timeframe is yearly."""
        return timeframe == cls.YEARLY.value

    @classmethod
    def get_days(cls, timeframe: str) -> int:
        """Get the approximate number of days in this timeframe."""
        days_map: dict[str, int] = {
            cls.INTRADAY.value: 1,
            cls.DAILY.value: 1,
            cls.WEEKLY.value: 7,
            cls.MONTHLY.value: 30,
            cls.QUARTERLY.value: 90,
            cls.YEARLY.value: 365,
        }
        return days_map.get(timeframe, 1)
