import logging
import time
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import desc

from app.apis.stock_buy_api import should_buy_stock
from app.apis.stock_purchase_api import purchase_stock
from app.apis.stock_sale_api import sell_stock
from app.apis.stock_sell_api import should_sell_stock
from app.database import get_session
from app.exceptions import ServiceError, InvalidStateError
from app.session_manager import SessionManager, with_session
from app.constants import (
    DECISION_YES, 
    STATE_ACTIVE, 
    STATE_INACTIVE,
    MODE_BUY,
    MODE_SELL,
    DEFAULT_POLLING_INTERVAL,
    DEMO_POLLING_INTERVAL
)
from app.models.stock_service_model import StockService
from app.models.stock_transaction_model import StockTransaction

logger = logging.getLogger(__name__)

class StockTradingService:
    """
    Manages the trading cycle for a specific stock, alternating between
    buy and sell modes based on API signals.
    """
    
    def __init__(self, service_id: Optional[int] = None, stock_symbol: str = "", 
                 starting_balance: Decimal = Decimal('0.00')):
        """
        Initialize the stock trading service.
        
        Args:
            service_id: ID of an existing service to load, or None to create a new one
            stock_symbol: The ticker symbol of the stock to trade
            starting_balance: Initial funds to allocate for trading
        
        Raises:
            ServiceError: If there's an error loading or creating the service
        """
        self.session = get_session()
        
        try:
            if service_id:
                # Load existing service
                self.service = self.session.query(StockService).filter_by(service_id=service_id).first()
                if not self.service:
                    raise InvalidStateError(f"No service found with ID {service_id}")
            else:
                # Create new service
                self.service = StockService(
                    stock_symbol=stock_symbol,
                    starting_balance=starting_balance,
                    fund_balance=starting_balance,
                    total_gain_loss=Decimal('0.00'),
                    current_number_of_shares=0,
                    service_state=STATE_ACTIVE,
                    service_mode=MODE_BUY,
                    start_date=datetime.utcnow(),
                    number_of_buy_transactions=0,
                    number_of_sell_transactions=0
                )
                self.session.add(self.service)
                self.session.commit()
                
            self.stock_symbol = self.service.stock_symbol
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error initializing service: {str(e)}")
            raise ServiceError(f"Failed to initialize trading service: {str(e)}")
            
    def start_trading_cycle(self, polling_interval: int = DEFAULT_POLLING_INTERVAL) -> None:
        """
        Start the trading cycle, alternating between buy and sell modes.
        
        This method runs a continuous loop that periodically checks if the service
        should buy or sell stocks based on market conditions and the current mode.
        The cycle continues until the service is explicitly stopped.
        
        Args:
            polling_interval: Time in seconds to wait between decision cycles
        """
        logger.info(f"Starting trading cycle for {self.stock_symbol} with service ID {self.service.service_id}")
        
        while self.service.service_state == STATE_ACTIVE:
            try:
                if self.service.service_mode == MODE_BUY:
                    self._execute_buy_cycle()
                else:  # sell mode
                    self._execute_sell_cycle()
                    
                # Save changes to service
                self.session.commit()
                
                # Wait before next cycle
                time.sleep(polling_interval)
                
            except Exception as e:
                logger.error(f"Error in trading cycle: {str(e)}")
                self.session.rollback()
                time.sleep(polling_interval)
    
    def _execute_buy_cycle(self) -> None:
        """
        Execute the buy cycle when in buy mode.
        
        This method checks if market conditions are favorable for buying,
        and if so, purchases shares using available funds. After a successful
        purchase, it updates the service state and switches to sell mode.
        """
        logger.info(f"Buy cycle for {self.stock_symbol}")
        
        # Call Buy API to determine if we should buy
        buy_decision = should_buy_stock(self.stock_symbol)
        
        if buy_decision == DECISION_YES:
            logger.info(f"Buy decision: YES for {self.stock_symbol}")
            
            # Call Stock Purchase API to buy shares
            try:
                number_of_shares, purchase_price, date_time_of_purchase = purchase_stock(
                    self.stock_symbol, 
                    self.service.fund_balance
                )
                
                # Create new transaction record
                transaction = StockTransaction(
                    service_id=self.service.service_id,
                    stock_symbol=self.stock_symbol,
                    number_of_shares=number_of_shares,
                    purchase_price=purchase_price,
                    date_time_of_purchase=date_time_of_purchase
                )
                self.session.add(transaction)
                
                # Update service record
                total_cost = Decimal(number_of_shares) * purchase_price
                self.service.fund_balance -= total_cost
                self.service.current_number_of_shares += number_of_shares
                self.service.number_of_buy_transactions += 1
                self.service.service_mode = MODE_SELL
                
                logger.info(f"Purchased {number_of_shares} shares of {self.stock_symbol} at {purchase_price} per share")
                
            except Exception as e:
                logger.error(f"Error purchasing stock: {str(e)}")
                # Don't change mode if purchase failed
        else:
            logger.info(f"Buy decision: NO for {self.stock_symbol}")
    
    def _execute_sell_cycle(self) -> None:
        """
        Execute the sell cycle when in sell mode.
        
        This method checks if the service has shares to sell and if market conditions
        are favorable for selling. If both conditions are met, it sells the shares,
        updates transaction records with sale details, and switches to buy mode.
        """
        logger.info(f"Sell cycle for {self.stock_symbol}")
        
        # Verify we have shares to sell
        if self.service.current_number_of_shares <= 0:
            logger.warning(f"No shares to sell for {self.stock_symbol}")
            self.service.service_mode = MODE_BUY
            return
        
        # Get the last open transaction (transaction with no sale_price)
        last_transaction = (
            self.session.query(StockTransaction)
            .filter_by(
                service_id=self.service.service_id,
                sale_price=None
            )
            .order_by(desc(StockTransaction.transaction_id))
            .first()
        )
        
        if not last_transaction:
            logger.warning(f"No open transaction found for {self.stock_symbol}")
            self.service.service_mode = MODE_BUY
            return
        
        # Call Sell API to determine if we should sell
        sell_decision = should_sell_stock(self.stock_symbol, last_transaction.purchase_price)
        
        if sell_decision == DECISION_YES:
            logger.info(f"Sell decision: YES for {self.stock_symbol}")
            
            # Call Stock Sale API to sell shares
            try:
                sale_price, date_time_of_sale = sell_stock(
                    self.stock_symbol,
                    self.service.current_number_of_shares
                )
                
                # Update the transaction record
                last_transaction.sale_price = sale_price
                last_transaction.date_time_of_sale = date_time_of_sale
                
                # Calculate gain/loss
                gain_loss = (sale_price - last_transaction.purchase_price) * Decimal(last_transaction.number_of_shares)
                last_transaction.gain_loss = gain_loss
                
                # Update service record
                total_proceeds = Decimal(self.service.current_number_of_shares) * sale_price
                self.service.fund_balance += total_proceeds
                self.service.total_gain_loss += gain_loss
                self.service.number_of_sell_transactions += 1
                self.service.current_number_of_shares = 0
                self.service.service_mode = MODE_BUY
                
                logger.info(f"Sold {last_transaction.number_of_shares} shares of {self.stock_symbol} at {sale_price} per share")
                logger.info(f"Gain/Loss: {gain_loss}")
                
            except Exception as e:
                logger.error(f"Error selling stock: {str(e)}")
                # Don't change mode if sale failed
        else:
            logger.info(f"Sell decision: NO for {self.stock_symbol}")
    
    def stop_trading(self) -> None:
        """
        Stop the trading service.
        
        This method updates the service state to inactive, preventing
        further trading cycles from executing.
        """
        self.service.service_state = STATE_INACTIVE
        self.session.commit()
        logger.info(f"Stopped trading service for {self.stock_symbol}")
        
    def __del__(self) -> None:
        """Ensure session is closed when object is destroyed."""
        self.session.close()

    @classmethod
    def restart_trading_cycle(cls, service_id, polling_interval=DEMO_POLLING_INTERVAL):
        """
        Restart the trading cycle for an existing service that was previously stopped.
        
        This method loads an existing service by ID and creates a new trading
        service instance to resume trading operations. It maintains the service's
        existing state (fund balance, shares owned, etc.) while reactivating the
        trading algorithm.
        
        Args:
            service_id: The ID of the existing service to restart
            polling_interval: Seconds to wait between decision cycles
            
        Raises:
            ServiceError: If the service cannot be found or restarted
        """
        logger.info(f"Restarting trading cycle for service {service_id}")
        
        with SessionManager() as session:
            service_model = session.query(StockService).filter_by(service_id=service_id).first()
            
            if not service_model:
                logger.error(f"Service {service_id} not found")
                raise InvalidStateError(f"Service {service_id} not found")
            
            # Create a service instance from the existing service model
            service = cls(
                service_id=service_id,
                stock_symbol=service_model.stock_symbol,
                starting_balance=service_model.starting_balance
            )
            
            # Start the trading cycle using the existing service data
            service.start_trading_cycle(polling_interval=polling_interval)
