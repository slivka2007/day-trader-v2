from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from app.models.stock_service_model import Base, StockService
from datetime import datetime

class StockTransaction(Base):
    __tablename__ = 'stock_transactions'
    
    transaction_id = Column(Integer, primary_key=True)
    service_id = Column(Integer, ForeignKey('stock_services.service_id'), nullable=False)
    stock_symbol = Column(String, nullable=False)
    number_of_shares = Column(Integer, nullable=False)
    purchase_price = Column(Numeric(precision=10, scale=2), nullable=False)
    sale_price = Column(Numeric(precision=10, scale=2), nullable=True)
    gain_loss = Column(Numeric(precision=10, scale=2), nullable=True)
    date_time_of_purchase = Column(DateTime, default=datetime.utcnow, nullable=False)
    date_time_of_sale = Column(DateTime, nullable=True)
    
    # Relationship with StockService
    service = relationship("StockService", back_populates="transactions")
    
    def __repr__(self):
        return f"<StockTransaction(transaction_id={self.transaction_id}, stock_symbol='{self.stock_symbol}', number_of_shares={self.number_of_shares})>"

# Add relationship to StockService model
StockService.transactions = relationship("StockTransaction", order_by=StockTransaction.transaction_id, back_populates="service")
