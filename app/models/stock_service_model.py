from datetime import datetime
from typing import Optional, List

from sqlalchemy import Column, Integer, String, Numeric, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, relationship

from app.constants import STATE_ACTIVE, STATE_INACTIVE, MODE_BUY, MODE_SELL

Base = declarative_base()

class StockService(Base):
    """
    Model representing a stock trading service instance.
    
    Stores information about each trading service, including its current state,
    balances, transaction counts, and relationship to transactions. This is the
    core model that tracks the lifecycle of a trading service from creation to
    termination.
    
    Attributes:
        service_id: Unique identifier for the service
        stock_symbol: The ticker symbol of the stock being traded
        starting_balance: The initial funds allocated to the service
        fund_balance: The current available funds (decreases on buy, increases on sell)
        total_gain_loss: The cumulative profit or loss from completed transactions
        current_number_of_shares: The number of shares currently held
        service_state: Whether the service is active or inactive
        service_mode: Current operational mode (buy or sell)
        start_date: When the service was created
        number_of_buy_transactions: Count of completed buy transactions
        number_of_sell_transactions: Count of completed sell transactions
    """
    __tablename__ = 'stock_services'
    
    # Primary key and identification fields
    service_id: int = Column(Integer, primary_key=True)
    stock_symbol: str = Column(String, nullable=False)
    
    # Balance fields
    starting_balance: Numeric = Column(Numeric(precision=10, scale=2), nullable=False)
    fund_balance: Numeric = Column(Numeric(precision=10, scale=2), nullable=False)
    total_gain_loss: Numeric = Column(Numeric(precision=10, scale=2), default=0)
    
    # Current position
    current_number_of_shares: int = Column(Integer, default=0)
    
    # Service state tracking
    service_state: str = Column(String, default=STATE_ACTIVE)  # 'active' or 'inactive'
    service_mode: str = Column(String, default=MODE_BUY)  # 'buy' or 'sell'
    start_date: datetime = Column(DateTime, default=datetime.utcnow)
    
    # Transaction counts
    number_of_buy_transactions: int = Column(Integer, default=0)
    number_of_sell_transactions: int = Column(Integer, default=0)
    
    # transactions relationship will be added by StockTransaction model
    
    def __repr__(self) -> str:
        """String representation of the StockService object."""
        return f"<StockService(service_id={self.service_id}, stock_symbol='{self.stock_symbol}', service_state='{self.service_state}')>"
