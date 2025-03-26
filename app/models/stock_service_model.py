from datetime import datetime, UTC
from typing import List, TYPE_CHECKING
from sqlalchemy import Column, Integer, String, Numeric, DateTime
from sqlalchemy.orm import relationship, Mapped

# Import the shared Base
from app.models import Base

from app.config.constants import STATE_ACTIVE, MODE_BUY

if TYPE_CHECKING:
    from app.models.stock_transaction_model import StockTransaction

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
        transactions: List of transactions associated with this service
    """
    __tablename__ = 'stock_services'
    
    # Primary key and identification fields
    service_id: int = Column(Integer, primary_key=True, nullable=False)
    stock_symbol: str = Column(String, nullable=False)
    
    # Balance fields
    starting_balance: Numeric = Column(Numeric(precision=10, scale=2), nullable=False)
    fund_balance: Numeric = Column(Numeric(precision=10, scale=2), nullable=False)
    total_gain_loss: Numeric = Column(Numeric(precision=10, scale=2), default=0, nullable=False)
    
    # Current position
    current_number_of_shares: int = Column(Integer, default=0)
    
    # Transaction counts
    number_of_buy_transactions: int = Column(Integer, default=0, nullable=False)
    number_of_sell_transactions: int = Column(Integer, default=0, nullable=False)

    # Timestamps
    creation_date: datetime = Column(DateTime, default=datetime.now(UTC), nullable=False)
    last_start_date: datetime = Column(DateTime, default=datetime.now(UTC), nullable=False)
    last_stop_date: datetime = Column(DateTime, nullable=True)
    
    # Service state tracking
    service_mode: str = Column(String, default=MODE_BUY, nullable=False)  # 'Buy' or 'Sell'
    service_state: str = Column(String, default=STATE_ACTIVE, nullable=False)  # 'Active' or 'Inactive'   
    
    # Relationship with transactions
    transactions: Mapped[List["StockTransaction"]] = relationship(
        "StockTransaction", 
        order_by="StockTransaction.transaction_id", 
        back_populates="service"
    )
    
    def __repr__(self) -> str:
        """String representation of the StockService object."""
        return f"<StockService(service_id={self.service_id}, stock_symbol='{self.stock_symbol}', service_state='{self.service_state}')>"
