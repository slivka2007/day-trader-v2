from sqlalchemy import Column, Integer, String, Numeric, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class StockService(Base):
    __tablename__ = 'stock_services'
    
    service_id = Column(Integer, primary_key=True)
    stock_symbol = Column(String, nullable=False)
    starting_balance = Column(Numeric(precision=10, scale=2), nullable=False)
    fund_balance = Column(Numeric(precision=10, scale=2), nullable=False)
    total_gain_loss = Column(Numeric(precision=10, scale=2), default=0)
    current_number_of_shares = Column(Integer, default=0)
    service_state = Column(String, default='active')
    service_mode = Column(String, default='buy')
    start_date = Column(DateTime, default=datetime.utcnow)
    number_of_buy_transactions = Column(Integer, default=0)
    number_of_sell_transactions = Column(Integer, default=0)
    
    def __repr__(self):
        return f"<StockService(service_id={self.service_id}, stock_symbol='{self.stock_symbol}', service_state='{self.service_state}')>"
