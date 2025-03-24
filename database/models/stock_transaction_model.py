from datetime import datetime
from typing import Optional, List
from decimal import Decimal

from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Mapped

# Import the shared Base and StockService
from database.models import Base
from database.models.stock_service_model import StockService

class StockTransaction(Base):
    """
    Model representing a stock purchase/sale transaction.
    
    Tracks individual buy and sell actions for each service, including
    purchase details, sale details, and gain/loss calculations. Each transaction
    represents a complete buy-sell cycle or an in-progress cycle where the sale
    has not yet occurred.
    
    Attributes:
        transaction_id: Unique identifier for the transaction
        service_id: Foreign key to the associated StockService
        stock_symbol: The ticker symbol of the stock traded
        number_of_shares: Quantity of shares bought/sold in this transaction
        purchase_price: Price per share when purchased
        sale_price: Price per share when sold (null until sold)
        gain_loss: Total profit/loss from this transaction (null until sold)
        date_time_of_purchase: When the purchase occurred
        date_time_of_sale: When the sale occurred (null until sold)
        service: Relationship to the parent StockService
    """
    __tablename__ = 'stock_transactions'
    
    # Primary key and relationship fields
    transaction_id: int = Column(Integer, primary_key=True)
    service_id: int = Column(Integer, ForeignKey('stock_services.service_id'), nullable=False)
    
    # Transaction details
    stock_symbol: str = Column(String, nullable=False)
    number_of_shares: int = Column(Integer, nullable=False)
    
    # Price information
    purchase_price: Decimal = Column(Numeric(precision=10, scale=2), nullable=False)
    sale_price: Optional[Decimal] = Column(Numeric(precision=10, scale=2), nullable=True)
    gain_loss: Optional[Decimal] = Column(Numeric(precision=10, scale=2), nullable=True)
    
    # Timestamps
    date_time_of_purchase: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)
    date_time_of_sale: Optional[datetime] = Column(DateTime, nullable=True)
    
    # Relationship with StockService
    service: Mapped["StockService"] = relationship("StockService", back_populates="transactions")
    
    def __repr__(self) -> str:
        """String representation of the StockTransaction object."""
        return f"<StockTransaction(transaction_id={self.transaction_id}, stock_symbol='{self.stock_symbol}', number_of_shares={self.number_of_shares})>"

# Add relationship to StockService model
StockService.transactions: Mapped[List["StockTransaction"]] = relationship(
    "StockTransaction", 
    order_by=StockTransaction.transaction_id, 
    back_populates="service"
)
