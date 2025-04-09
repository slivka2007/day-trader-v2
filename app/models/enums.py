"""Enumeration types for database models.

This module defines enumerations that represent constrained values in models,
ensuring type safety and consistency when working with state fields. These
enumerations are used throughout the application to represent various states,
modes, and categories with predefined sets of valid values.

Each enumeration provides consistent string serialization and additional helper
methods for common operations.
"""

import logging
from enum import Enum

from app.utils.errors import EnumError

# Set up logging
logger: logging.Logger = logging.getLogger(__name__)


class ServiceState(str, Enum):
    """Service operational states.

    Represents the possible operational states of a trading service:

    - ACTIVE: Service is running and can process transactions
    - INACTIVE: Service is not running (either never started or explicitly stopped)
    - PAUSED: Service is temporarily suspended but can be resumed
    - ERROR: Service encountered an error and needs attention
    """

    #
    # Enum values
    #
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    PAUSED = "PAUSED"
    ERROR = "ERROR"

    #
    # Helper methods
    #
    @classmethod
    def active_states(cls) -> set[str]:
        """Get the set of states where the service is considered operational."""
        return {cls.ACTIVE.value}

    @classmethod
    def is_active(cls, state: str) -> bool:
        """Check if the given state is considered active/operational."""
        return state == cls.ACTIVE.value

    @classmethod
    def is_paused(cls, state: str) -> bool:
        """Check if the given state is considered paused."""
        return state == cls.PAUSED.value

    @classmethod
    def is_inactive(cls, state: str) -> bool:
        """Check if the given state is considered inactive."""
        return state == cls.INACTIVE.value

    @classmethod
    def is_error(cls, state: str) -> bool:
        """Check if the given state is considered in an error state."""
        return state == cls.ERROR.value

    @classmethod
    def from_string(cls, value: str) -> "ServiceState":
        """Convert a string to the corresponding enum value."""
        for member in cls:
            if member.value.upper() == value.upper():
                return member
        raise ValueError(
            EnumError.INVALID_VALUE.format(value=value, class_name=cls.__name__),
        )

    @classmethod
    def values(cls) -> list[str]:
        """Get a list of all valid values for this enum."""
        return [member.value for member in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a string is a valid value for this enum."""
        try:
            cls.from_string(value)
        except ValueError:
            return False
        return True


class ServiceAction(str, Enum):
    """Actions that can be taken on a service.

    Represents the possible actions that can be taken on a service:

    - CHECK_BUY: Check for a buy opportunity
    - CHECK_SELL: Check for a sell opportunity
    """

    #
    # Enum values
    #
    CHECK_BUY = "CHECK_BUY"
    CHECK_SELL = "CHECK_SELL"

    #
    # Helper methods
    #
    @classmethod
    def is_check_buy(cls, action: str) -> bool:
        """Check if the given action is a check for a buy opportunity."""
        return action == cls.CHECK_BUY.value

    @classmethod
    def is_check_sell(cls, action: str) -> bool:
        """Check if the given action is a check for a sell opportunity."""
        return action == cls.CHECK_SELL.value

    @classmethod
    def from_string(cls, value: str) -> "ServiceAction":
        """Convert a string to the corresponding enum value."""
        for member in cls:
            if member.value.upper() == value.upper():
                return member
        raise ValueError(
            EnumError.INVALID_VALUE.format(value=value, class_name=cls.__name__),
        )

    @classmethod
    def values(cls) -> list[str]:
        """Get a list of all valid values for this enum."""
        return [member.value for member in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a string is a valid value for this enum."""
        try:
            cls.from_string(value)
        except ValueError:
            return False
        return True


class TradingMode(str, Enum):
    """Trading mode for services.

    Represents the current trading strategy mode:

    - BUY: Service is looking for opportunities to buy
    - SELL: Service is looking for opportunities to sell
    - HOLD: Service is holding current positions without buying or selling
    """

    #
    # Enum values
    #
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

    #
    # Helper methods
    #
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
        return cls.HOLD.value

    @classmethod
    def from_string(cls, value: str) -> "TradingMode":
        """Convert a string to the corresponding enum value."""
        for member in cls:
            if member.value.upper() == value.upper():
                return member
        raise ValueError(
            EnumError.INVALID_VALUE.format(value=value, class_name=cls.__name__),
        )

    @classmethod
    def values(cls) -> list[str]:
        """Get a list of all valid values for this enum."""
        return [member.value for member in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a string is a valid value for this enum."""
        try:
            cls.from_string(value)
        except ValueError:
            return False
        return True


class TransactionState(str, Enum):
    """Transaction states.

    Represents the possible states of a trading transaction:

    - OPEN: Purchase executed, not yet sold
    - CLOSED: Fully executed (purchased and sold)
    - CANCELLED: Transaction cancelled before completion
    """

    #
    # Enum values
    #
    OPEN = "OPEN"  # Purchase executed, not yet sold
    CLOSED = "CLOSED"  # Fully executed (purchased and sold)
    CANCELLED = "CANCELLED"  # Transaction cancelled

    #
    # Helper methods
    #
    @classmethod
    def is_open(cls, state: str) -> bool:
        """Check if the given state is open (transaction in progress)."""
        return state == cls.OPEN.value

    @classmethod
    def is_closed(cls, state: str) -> bool:
        """Check if the given state is closed (transaction completed)."""
        return state == cls.CLOSED.value

    @classmethod
    def is_cancelled(cls, state: str) -> bool:
        """Check if the given state is cancelled."""
        return state == cls.CANCELLED.value

    @classmethod
    def terminal_states(cls) -> set[str]:
        """Get the set of states that are terminal (no further changes)."""
        return {cls.CLOSED.value, cls.CANCELLED.value}

    @classmethod
    def is_terminal(cls, state: str) -> bool:
        """Check if the given state is terminal (no further state changes)."""
        return state in cls.terminal_states()

    @classmethod
    def can_be_cancelled(cls, state: str) -> bool:
        """Check if a transaction in the given state can be cancelled."""
        return state == cls.OPEN.value

    @classmethod
    def from_string(cls, value: str) -> "TransactionState":
        """Convert a string to the corresponding enum value."""
        for member in cls:
            if member.value.upper() == value.upper():
                return member
        raise ValueError(
            EnumError.INVALID_VALUE.format(value=value, class_name=cls.__name__),
        )

    @classmethod
    def values(cls) -> list[str]:
        """Get a list of all valid values for this enum."""
        return [member.value for member in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a string is a valid value for this enum."""
        try:
            cls.from_string(value)
        except ValueError:
            return False
        return True


class PriceSource(str, Enum):
    """Source of price data.

    Represents the origin of price data:

    - REAL_TIME: Live price data from exchanges
    - DELAYED: Delayed price data (typically 15-20 minutes)
    - SIMULATED: Simulated or generated price data for testing
    - HISTORICAL: Historical price data from past periods
    - TEST: Test data for development and testing purposes
    """

    #
    # Enum values
    #
    REAL_TIME = "REAL_TIME"
    DELAYED = "DELAYED"
    SIMULATED = "SIMULATED"
    HISTORICAL = "HISTORICAL"
    TEST = "TEST"

    #
    # Helper methods
    #
    @classmethod
    def is_delayed(cls, source: str) -> bool:
        """Check if the given source is delayed data."""
        return source == cls.DELAYED.value

    @classmethod
    def is_simulated(cls, source: str) -> bool:
        """Check if the given source is simulated data."""
        return source == cls.SIMULATED.value

    @classmethod
    def is_historical(cls, source: str) -> bool:
        """Check if the given source is historical data."""
        return source == cls.HISTORICAL.value

    @classmethod
    def is_real_time(cls, source: str) -> bool:
        """Check if the given source is real-time data."""
        return source == cls.REAL_TIME.value

    @classmethod
    def is_test(cls, source: str) -> bool:
        """Check if the given source is test data."""
        return source == cls.TEST.value

    @classmethod
    def is_real(cls, source: str) -> bool:
        """Check if the given source is real data (not simulated or test)."""
        return source in {cls.REAL_TIME.value, cls.DELAYED.value, cls.HISTORICAL.value}

    @classmethod
    def for_display(cls) -> dict[str, str]:
        """Get a mapping of enum values to display-friendly names."""
        return {
            cls.REAL_TIME.value: "Real-time",
            cls.DELAYED.value: "Delayed",
            cls.SIMULATED.value: "Simulated",
            cls.HISTORICAL.value: "Historical",
            cls.TEST.value: "Test",
        }

    @classmethod
    def from_string(cls, value: str) -> "PriceSource":
        """Convert a string to the corresponding enum value."""
        for member in cls:
            if member.value.upper() == value.upper():
                return member
        raise ValueError(
            EnumError.INVALID_VALUE.format(value=value, class_name=cls.__name__),
        )

    @classmethod
    def values(cls) -> list[str]:
        """Get a list of all valid values for this enum."""
        return [member.value for member in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a string is a valid value for this enum."""
        try:
            cls.from_string(value)
        except ValueError:
            return False
        return True


class IntradayInterval(int, Enum):
    """Valid intervals for intraday price data.

    Represents the allowed time intervals for intraday price data:

    - ONE_MINUTE: 1-minute interval
    - FIVE_MINUTES: 5-minute interval
    - FIFTEEN_MINUTES: 15-minute interval
    - THIRTY_MINUTES: 30-minute interval
    - ONE_HOUR: 60-minute (1-hour) interval
    """

    #
    # Enum values
    #
    ONE_MINUTE: int = 1
    FIVE_MINUTES: int = 5
    FIFTEEN_MINUTES: int = 15
    THIRTY_MINUTES: int = 30
    ONE_HOUR: int = 60

    @classmethod
    def invalid_value_message(cls, value: int) -> str:
        """Generate an error message for an invalid interval value.

        Args:
            value: The invalid value

        Returns:
            Formatted error message for the invalid value

        """
        valid_intervals = ", ".join(map(str, cls.valid_values()))
        return EnumError.INVALID_INTERVAL.format(
            value=value,
            valid_intervals=valid_intervals,
        )

    @classmethod
    def valid_values(cls) -> list[int]:
        """Get a list of valid interval values.

        Returns:
            List of integer values that are valid intervals

        """
        return [
            cls.ONE_MINUTE.value,
            cls.FIVE_MINUTES.value,
            cls.FIFTEEN_MINUTES.value,
            cls.THIRTY_MINUTES.value,
            cls.ONE_HOUR.value,
        ]

    @classmethod
    def is_valid_interval(cls, interval: int) -> bool:
        """Check if an interval value is valid."""
        return interval in cls.valid_values()

    @classmethod
    def get_name(cls, interval: int) -> str:
        """Get a display-friendly name for an interval.

        Args:
            interval: Interval value to get the name for

        Returns:
            Human-readable name for the interval

        """
        if interval == cls.ONE_MINUTE.value:
            return "1 Minute"
        if interval == cls.FIVE_MINUTES.value:
            return "5 Minutes"
        if interval == cls.FIFTEEN_MINUTES.value:
            return "15 Minutes"
        if interval == cls.THIRTY_MINUTES.value:
            return "30 Minutes"
        if interval == cls.ONE_HOUR.value:
            return "1 Hour"
        raise ValueError(
            EnumError.INVALID_VALUE.format(value=interval, class_name=cls.__name__),
        )

    @classmethod
    def from_int(cls, value: int) -> "IntradayInterval":
        """Convert an integer to the corresponding enum value.

        Args:
            value: Integer value to convert

        Returns:
            Enum member corresponding to the integer value

        """
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(
            EnumError.INVALID_VALUE.format(value=value, class_name=cls.__name__),
        )

    @classmethod
    def values(cls) -> list[int]:
        """Get a list of all valid values for this enum."""
        return [member.value for member in cls]

    @classmethod
    def is_valid(cls, value: int) -> bool:
        """Check if an integer is a valid value for this enum."""
        try:
            cls.from_int(value)
        except ValueError:
            return False
        return True


class AnalysisTimeframe(str, Enum):
    """Timeframes for analysis.

    Represents standard time periods for financial analysis:

    - INTRADAY: Within a single trading day
    - DAILY: Day-to-day analysis
    - WEEKLY: Week-to-week analysis
    - MONTHLY: Month-to-month analysis
    - QUARTERLY: Quarter-to-quarter analysis
    - YEARLY: Year-to-year analysis
    """

    #
    # Enum values
    #
    INTRADAY = "INTRADAY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    YEARLY = "YEARLY"

    #
    # Helper methods
    #
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
        """Get the approximate number of calendar days for the timeframe.

        Args:
            timeframe: The timeframe to get days for

        Returns:
            Number of calendar days

        """
        if timeframe == cls.INTRADAY.value:
            return 1  # Same day
        if timeframe == cls.DAILY.value:
            return 1  # 1 day
        if timeframe == cls.WEEKLY.value:
            return 7  # 7 days
        if timeframe == cls.MONTHLY.value:
            return 30  # 30 days (average)
        if timeframe == cls.QUARTERLY.value:
            return 90  # 90 days (3 months)
        if timeframe == cls.YEARLY.value:
            return 365  # 365 days
        raise ValueError(
            EnumError.INVALID_VALUE.format(value=timeframe, class_name=cls.__name__),
        )

    @classmethod
    def from_string(cls, value: str) -> "AnalysisTimeframe":
        """Convert a string to the corresponding enum value."""
        for member in cls:
            if member.value.upper() == value.upper():
                return member
        raise ValueError(
            EnumError.INVALID_VALUE.format(value=value, class_name=cls.__name__),
        )

    @classmethod
    def values(cls) -> list[str]:
        """Get a list of all valid values for this enum."""
        return [member.value for member in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a string is a valid value for this enum."""
        try:
            cls.from_string(value)
        except ValueError:
            return False
        return True
