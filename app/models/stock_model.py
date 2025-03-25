from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship, Mapped
from typing import List, Optional, TYPE_CHECKING

# Import the shared Base
from app.models import Base

# Forward references for type annotations to avoid circular imports
if TYPE_CHECKING:
    from app.models.daily_price_model import DailyPrice
    from app.models.intraday_price_model import IntradayPrice

class Stock(Base):
    """
    Model representing a stock entity.
    
    Stores basic information about stocks including symbol and name,
    with relationships to price history data.
    
    Attributes:
        id: Unique identifier for the stock
        symbol: The ticker symbol of the stock (unique)
        name: The company/entity name of the stock
        daily_prices: Relationship to daily price history
        intraday_prices: Relationship to intraday price history
    """
    __tablename__ = 'stocks'
    
    id: int = Column(Integer, primary_key=True)
    symbol: str = Column(String, unique=True, nullable=False)
    name: Optional[str] = Column(String)
    daily_prices: Mapped[List["DailyPrice"]] = relationship("DailyPrice", back_populates="stock")
    intraday_prices: Mapped[List["IntradayPrice"]] = relationship("IntradayPrice", back_populates="stock")

    def __repr__(self) -> str:
        """String representation of the Stock object."""
        return f"<Stock(id={self.id}, symbol='{self.symbol}', name='{self.name}')>"
