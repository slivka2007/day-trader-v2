"""
Enumeration types for database models.

This module defines enumerations that represent constrained values in models,
ensuring type safety and consistency when working with state fields.
"""
from enum import auto
from app.models.base import EnumBase

class ServiceState(EnumBase):
    """Service operational states."""
    ACTIVE = auto()
    INACTIVE = auto()
    PAUSED = auto()
    ERROR = auto()

class TradingMode(EnumBase):
    """Trading mode for services."""
    BUY = auto()
    SELL = auto()
    HOLD = auto()

class TransactionState(EnumBase):
    """Transaction states."""
    OPEN = auto()     # Purchase executed, not yet sold
    CLOSED = auto()   # Fully executed (purchased and sold)
    CANCELLED = auto() # Transaction cancelled

class PriceSource(EnumBase):
    """Source of price data."""
    REAL_TIME = auto()
    DELAYED = auto()
    SIMULATED = auto()
    HISTORICAL = auto() 