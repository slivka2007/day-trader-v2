"""
Trading Service service for managing TradingService model operations.

This service encapsulates all database interactions for the TradingService model,
providing a clean API for trading service management operations.
"""
import logging
from typing import Optional, List, Dict, Any, Set
from sqlalchemy.orm import Session, object_session
from sqlalchemy import or_, and_
from datetime import timedelta

from app.models.trading_service import TradingService
from app.models.trading_transaction import TradingTransaction
from app.models.stock import Stock
from app.models.stock_daily_price import StockDailyPrice
from app.models.enums import ServiceState, TradingMode, TransactionState
from app.utils.errors import ValidationError, ResourceNotFoundError, BusinessLogicError, AuthorizationError
from app.utils.current_datetime import get_current_datetime, get_current_date
from app.api.schemas.trading_service import service_schema, services_schema

# Set up logging
logger = logging.getLogger(__name__)

class TradingServiceService:
    """Service for TradingService model operations."""
    
    # Read operations
    @staticmethod
    def get_by_id(session: Session, service_id: int) -> Optional[TradingService]:
        """
        Get a trading service by ID.
        
        Args:
            session: Database session
            service_id: Trading service ID to retrieve
            
        Returns:
            TradingService instance if found, None otherwise
        """
        return session.query(TradingService).get(service_id)
    
    @staticmethod
    def get_or_404(session: Session, service_id: int) -> TradingService:
        """
        Get a trading service by ID or raise ResourceNotFoundError.
        
        Args:
            session: Database session
            service_id: Trading service ID to retrieve
            
        Returns:
            TradingService instance
            
        Raises:
            ResourceNotFoundError: If trading service not found
        """
        service = TradingServiceService.get_by_id(session, service_id)
        if not service:
            raise ResourceNotFoundError(f"TradingService with ID {service_id} not found")
        return service
    
    @staticmethod
    def get_by_user(session: Session, user_id: int) -> List[TradingService]:
        """
        Get all trading services for a user.
        
        Args:
            session: Database session
            user_id: User ID
            
        Returns:
            List of trading services
        """
        return session.query(TradingService).filter(TradingService.user_id == user_id).all()
    
    @staticmethod
    def get_by_stock(session: Session, stock_symbol: str) -> List[TradingService]:
        """
        Get all trading services for a stock.
        
        Args:
            session: Database session
            stock_symbol: Stock symbol
            
        Returns:
            List of trading services
        """
        return session.query(TradingService).filter(TradingService.stock_symbol == stock_symbol.upper()).all()
    
    @staticmethod
    def get_all(session: Session) -> List[TradingService]:
        """
        Get all trading services.
        
        Args:
            session: Database session
            
        Returns:
            List of TradingService instances
        """
        return session.query(TradingService).all()
    
    @staticmethod
    def check_ownership(session: Session, service_id: int, user_id: int) -> bool:
        """
        Check if a user owns a trading service.
        
        Args:
            session: Database session
            service_id: Trading service ID
            user_id: User ID
            
        Returns:
            True if the user owns the service, False otherwise
        """
        service = TradingServiceService.get_by_id(session, service_id)
        if not service:
            return False
        
        return service.user_id == user_id
    
    @staticmethod
    def verify_ownership(session: Session, service_id: int, user_id: int) -> TradingService:
        """
        Verify a user owns a trading service, and return the service if they do.
        
        Args:
            session: Database session
            service_id: Trading service ID
            user_id: User ID
            
        Returns:
            TradingService instance
            
        Raises:
            ResourceNotFoundError: If trading service not found
            AuthorizationError: If user does not own the service
        """
        service = TradingServiceService.get_or_404(session, service_id)
        
        if service.user_id != user_id:
            raise AuthorizationError(f"User {user_id} does not own TradingService {service_id}")
        
        return service
    
    @staticmethod
    def search_services(session: Session, user_id: int, query: str) -> List[TradingService]:
        """
        Search trading services by name or stock symbol.
        
        Args:
            session: Database session
            user_id: User ID
            query: Search query
            
        Returns:
            List of matching TradingService instances
        """
        if not query:
            return TradingServiceService.get_by_user(session, user_id)
        
        # Convert query to uppercase for case-insensitive matching on symbol
        query_upper = query.upper()
        
        # Search for services matching the query by name or stock symbol
        services = session.query(TradingService).filter(
            TradingService.user_id == user_id,
            or_(
                TradingService.name.ilike(f"%{query}%"),
                TradingService.stock_symbol == query_upper
            )
        ).all()
        
        return services
    
    @staticmethod
    def get_current_price_for_service(session: Session, service: TradingService) -> float:
        """
        Get the current price of the stock for a trading service.
        
        Args:
            session: Database session
            service: TradingService instance
            
        Returns:
            Current price of the stock
        """
        # Check if the service has a stock relationship
        if service.stock and service.stock.id:
            # Use StockService to get latest price
            from app.services.stock_service import StockService
            return StockService.get_latest_price(session, service.stock) or 0.0
        
        # If no stock relationship, try to find by symbol
        return TradingServiceService.get_current_price(session, service.stock_symbol) or 0.0
    
    @staticmethod
    def calculate_performance_pct(session: Session, service: TradingService) -> float:
        """
        Calculate the performance of a trading service as a percentage of initial balance.
        
        Args:
            session: Database session
            service: TradingService instance
            
        Returns:
            Performance percentage
        """
        if not service.initial_balance:
            return 0.0
            
        # Get current price of the stock
        current_price = TradingServiceService.get_current_price_for_service(session, service)
        
        # Calculate total value (balance + shares)
        total_value = service.current_balance + (service.current_shares * current_price)
        
        # Calculate performance as percentage
        return ((total_value - service.initial_balance) / service.initial_balance) * 100
    
    @staticmethod
    def update_service_attributes(service: TradingService, data: Dict[str, Any], allowed_fields: Optional[Set[str]] = None) -> bool:
        """
        Update service attributes from data dictionary.
        
        Args:
            service: TradingService instance
            data: Dictionary of attribute key/value pairs
            allowed_fields: Set of field names that are allowed to be updated
            
        Returns:
            True if any fields were updated, False otherwise
        """
        if allowed_fields is None:
            allowed_fields = {
                'name', 'description', 'is_active', 'minimum_balance', 
                'allocation_percent', 'buy_threshold', 'sell_threshold', 
                'stop_loss_percent', 'take_profit_percent'
            }
        
        updated = False
        for key, value in data.items():
            if key in allowed_fields and hasattr(service, key):
                if getattr(service, key) != value:
                    setattr(service, key, value)
                    updated = True
                    
        return updated
    
    # Write operations
    @staticmethod
    def create_service(session: Session, user_id: int, data: Dict[str, Any]) -> TradingService:
        """
        Create a new trading service.
        
        Args:
            session: Database session
            user_id: User ID
            data: Trading service data dictionary
            
        Returns:
            Created TradingService instance
            
        Raises:
            ValidationError: If required fields are missing or invalid
            BusinessLogicError: For other business logic errors
        """
        from app.services.events import EventService
        
        try:
            # Validate required fields
            required_fields = ['name', 'stock_symbol', 'initial_balance']
            for field in required_fields:
                if field not in data or not data[field]:
                    raise ValidationError(f"Field '{field}' is required")
            
            # Validate initial balance
            initial_balance = float(data['initial_balance'])
            if initial_balance <= 0:
                raise ValidationError("Initial balance must be greater than zero")
                
            # Find stock if it exists
            stock_symbol = data['stock_symbol'].upper()
            stock = session.query(Stock).filter(Stock.symbol == stock_symbol).first()
            stock_id = stock.id if stock else None
            
            # Set up service data
            service_data = {
                'user_id': user_id,
                'stock_id': stock_id,
                'stock_symbol': stock_symbol,
                'name': data['name'],
                'description': data.get('description', ''),
                'initial_balance': initial_balance,
                'current_balance': initial_balance,
                'minimum_balance': data.get('minimum_balance', 0),
                'allocation_percent': data.get('allocation_percent', 50),
                'buy_threshold': data.get('buy_threshold', 3.0),
                'sell_threshold': data.get('sell_threshold', 2.0),
                'stop_loss_percent': data.get('stop_loss_percent', 5.0),
                'take_profit_percent': data.get('take_profit_percent', 10.0),
                'state': ServiceState.INACTIVE.value,
                'mode': TradingMode.BUY.value,
                'is_active': True
            }
            
            # Create service
            service = TradingService(**service_data)
            session.add(service)
            session.commit()
            
            # Prepare response data
            service_data = service_schema.dump(service)
            
            # Emit WebSocket event
            EventService.emit_service_update(
                action='created',
                service_data=service_data,
                service_id=service.id
            )
            
            return service
        except Exception as e:
            logger.error(f"Error creating trading service: {str(e)}")
            session.rollback()
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Could not create trading service: {str(e)}")
    
    @staticmethod
    def update_service(session: Session, service: TradingService, data: Dict[str, Any]) -> TradingService:
        """
        Update trading service attributes.
        
        Args:
            session: Database session
            service: TradingService instance to update
            data: Dictionary of attributes to update
            
        Returns:
            Updated TradingService instance
            
        Raises:
            ValidationError: If invalid data is provided
        """
        from app.services.events import EventService
        
        try:
            # Define which fields can be updated
            allowed_fields = {
                'name', 'description', 'is_active', 'minimum_balance', 
                'allocation_percent', 'buy_threshold', 'sell_threshold', 
                'stop_loss_percent', 'take_profit_percent'
            }
            
            # Don't allow critical fields to be updated
            for field in ['user_id', 'stock_id', 'stock_symbol', 'initial_balance', 'current_balance']:
                if field in data:
                    del data[field]
            
            # Update the service attributes
            updated = TradingServiceService.update_service_attributes(service, data, allowed_fields)
            
            # Only commit if something was updated
            if updated:
                service.updated_at = get_current_datetime()
                session.commit()
                
                # Prepare response data
                service_data = service_schema.dump(service)
                
                # Emit WebSocket event
                EventService.emit_service_update(
                    action='updated',
                    service_data=service_data,
                    service_id=service.id,
                    user_id=service.user_id
                )
            
            return service
        except Exception as e:
            logger.error(f"Error updating trading service: {str(e)}")
            session.rollback()
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Could not update trading service: {str(e)}")
    
    @staticmethod
    def toggle_active(session: Session, service: TradingService) -> TradingService:
        """
        Toggle service active status.
        
        Args:
            session: Database session
            service: TradingService instance
            
        Returns:
            Updated TradingService instance
        """
        from app.services.events import EventService
        
        try:
            # Toggle active status
            service.is_active = not service.is_active
            service.updated_at = get_current_datetime()
            session.commit()
            
            # Prepare response data
            service_data = service_schema.dump(service)
            action = 'activated' if service.is_active else 'deactivated'
            
            # Emit WebSocket event
            EventService.emit_service_update(
                action=action,
                service_data=service_data,
                service_id=service.id
            )
            
            return service
        except Exception as e:
            logger.error(f"Error toggling trading service active status: {str(e)}")
            session.rollback()
            raise ValidationError(f"Could not toggle trading service active status: {str(e)}")
    
    @staticmethod
    def change_state(session: Session, service: TradingService, new_state: str) -> TradingService:
        """
        Change service state.
        
        Args:
            session: Database session
            service: TradingService instance
            new_state: New state value
            
        Returns:
            Updated TradingService instance
            
        Raises:
            ValidationError: If new state is invalid
        """
        from app.services.events import EventService
        
        try:
            # Validate state
            if not ServiceState.is_valid(new_state):
                valid_states = ServiceState.values()
                raise ValidationError(f"Invalid service state: {new_state}. Valid states are: {', '.join(valid_states)}")
                
            # Check if state is changing
            if service.state == new_state:
                return service
                
            # Update state
            service.state = new_state
            service.updated_at = get_current_datetime()
            session.commit()
            
            # Prepare response data
            service_data = service_schema.dump(service)
            
            # Emit WebSocket event
            EventService.emit_service_update(
                action='state_changed',
                service_data=service_data,
                service_id=service.id
            )
            
            return service
        except Exception as e:
            logger.error(f"Error changing trading service state: {str(e)}")
            session.rollback()
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Could not change trading service state: {str(e)}")
    
    @staticmethod
    def change_mode(session: Session, service: TradingService, new_mode: str) -> TradingService:
        """
        Change service trading mode.
        
        Args:
            session: Database session
            service: TradingService instance
            new_mode: New mode value
            
        Returns:
            Updated TradingService instance
            
        Raises:
            ValidationError: If new mode is invalid
            BusinessLogicError: If service cannot operate in the requested mode
        """
        from app.services.events import EventService
        
        try:
            # Validate mode
            if not TradingMode.is_valid(new_mode):
                valid_modes = TradingMode.values()
                raise ValidationError(f"Invalid trading mode: {new_mode}. Valid modes are: {', '.join(valid_modes)}")
                
            # Check if mode is changing
            if service.mode == new_mode:
                return service
                
            # Validate mode transitions
            if new_mode == TradingMode.SELL.value and service.current_shares <= 0:
                raise BusinessLogicError("Cannot set mode to SELL when no shares are held")
                
            if new_mode == TradingMode.BUY.value and service.current_balance <= service.minimum_balance:
                raise BusinessLogicError("Cannot set mode to BUY when balance is at or below minimum")
                
            # Update mode
            service.mode = new_mode
            service.updated_at = get_current_datetime()
            session.commit()
            
            # Prepare response data
            service_data = service_schema.dump(service)
            
            # Emit WebSocket event
            EventService.emit_service_update(
                action='mode_changed',
                service_data=service_data,
                service_id=service.id
            )
            
            return service
        except Exception as e:
            logger.error(f"Error changing trading service mode: {str(e)}")
            session.rollback()
            if isinstance(e, (ValidationError, BusinessLogicError)):
                raise
            raise ValidationError(f"Could not change trading service mode: {str(e)}")
    
    @staticmethod
    def delete_service(session: Session, service: TradingService) -> bool:
        """
        Delete a trading service.
        
        Args:
            session: Database session
            service: TradingService instance
            
        Returns:
            True if successful
            
        Raises:
            BusinessLogicError: If service has dependencies that prevent deletion
        """
        from app.services.events import EventService
        
        try:
            # Check if service has dependencies
            if service.has_dependencies():
                raise BusinessLogicError("Cannot delete trading service with active transactions. Cancel or complete them first.")
            
            # Store service ID for event emission
            service_id = service.id
            user_id = service.user_id
            
            # Delete service
            session.delete(service)
            session.commit()
            
            # Emit WebSocket event
            EventService.emit_service_update(
                action='deleted',
                service_data={'id': service_id},
                service_id=service_id,
                user_id=user_id
            )
            
            return True
        except Exception as e:
            logger.error(f"Error deleting trading service: {str(e)}")
            session.rollback()
            if isinstance(e, BusinessLogicError):
                raise
            raise BusinessLogicError(f"Could not delete trading service: {str(e)}")
    
    @staticmethod
    def check_buy_condition(session: Session, service: TradingService, current_price: float, historical_prices: List[float] = None) -> Dict[str, Any]:
        """
        Check if the conditions for buying are met.
        
        Args:
            session: Database session
            service: TradingService instance
            current_price: Current stock price
            historical_prices: List of historical prices for analysis
            
        Returns:
            Dictionary with buy decision information
        """
        try:
            # Use the model's business logic
            return service.check_buy_condition(current_price, historical_prices)
        except Exception as e:
            logger.error(f"Error checking buy condition: {str(e)}")
            return {
                'should_buy': False,
                'can_buy': False,
                'reason': f'Error checking buy condition: {str(e)}'
            }
    
    @staticmethod
    def check_sell_condition(session: Session, service: TradingService, current_price: float, historical_prices: List[float] = None) -> Dict[str, Any]:
        """
        Check if the conditions for selling are met.
        
        Args:
            session: Database session
            service: TradingService instance
            current_price: Current stock price
            historical_prices: List of historical prices for analysis
            
        Returns:
            Dictionary with sell decision information
        """
        try:
            # Use the model's business logic
            return service.check_sell_condition(current_price, historical_prices)
        except Exception as e:
            logger.error(f"Error checking sell condition: {str(e)}")
            return {
                'should_sell': False,
                'can_sell': False,
                'reason': f'Error checking sell condition: {str(e)}'
            }
    
    @staticmethod
    def get_current_price(session: Session, stock_symbol: str) -> float:
        """
        Get the current price for a stock.
        
        Args:
            session: Database session
            stock_symbol: Stock symbol
            
        Returns:
            Current price or 0.0 if not available
        """
        from app.services.price_service import PriceService
        
        try:
            # Get the stock
            stock = session.query(Stock).filter(Stock.symbol == stock_symbol.upper()).first()
            
            if not stock:
                return 0.0
                
            # Use the stock's latest price
            return stock.get_latest_price() or 0.0
        except Exception as e:
            logger.error(f"Error getting current price for {stock_symbol}: {str(e)}")
            return 0.0

    @staticmethod
    def execute_trading_strategy(session: Session, service_id: int) -> Dict[str, Any]:
        """
        Execute trading strategy for a service based on current market conditions and service settings.
        
        This method coordinates the decision-making process for buying or selling stocks based on:
        1. Current price trends (using PriceService for analysis)
        2. Service configuration (thresholds, modes, etc.)
        3. Available funds and current positions
        
        Args:
            session: Database session
            service_id: Trading service ID
            
        Returns:
            Dictionary with trading decision information and any actions taken
            
        Raises:
            ResourceNotFoundError: If service not found
            BusinessLogicError: If service is not active or other business rule violations
        """
        from app.services.price_service import PriceService
        from app.services.transaction_service import TransactionService
        
        # Get the service
        service = TradingServiceService.get_or_404(session, service_id)
        
        # Check if service is active
        if not service.is_active or service.state != ServiceState.ACTIVE.value:
            return {
                'success': False,
                'message': f"Service is not active (state: {service.state}, is_active: {service.is_active})",
                'action': 'none'
            }
        
        # Get price analysis for the stock
        price_analysis = PriceService.get_price_analysis(session, service.stock_id)
        
        if not price_analysis.get('has_data', False):
            return {
                'success': False,
                'message': "Insufficient price data for analysis",
                'action': 'none'
            }
        
        # Get current price
        current_price = price_analysis.get('latest_price')
        if not current_price:
            return {
                'success': False,
                'message': "Could not determine current price",
                'action': 'none'
            }
        
        # Trading decision
        result = {
            'success': True,
            'service_id': service_id,
            'stock_symbol': service.stock_symbol,
            'current_price': current_price,
            'current_balance': float(service.current_balance),
            'current_shares': service.current_shares,
            'mode': service.mode,
            'signals': price_analysis.get('signals', {})
        }
        
        # Execute strategy based on mode
        if service.mode == TradingMode.BUY.value:
            # Check buy conditions using technical analysis
            should_buy = TradingServiceService._should_buy(service, price_analysis, current_price)
            result['should_buy'] = should_buy
            
            if should_buy:
                # Calculate how many shares to buy
                max_shares_affordable = int(service.current_balance / current_price) if current_price > 0 else 0
                allocation_amount = (service.current_balance * service.allocation_percent) / 100
                shares_to_buy = int(allocation_amount / current_price)
                shares_to_buy = max(1, min(shares_to_buy, max_shares_affordable))  # At least 1, at most affordable
                
                if shares_to_buy > 0:
                    try:
                        # Execute buy transaction
                        transaction = TransactionService.create_buy_transaction(
                            session=session,
                            service_id=service_id,
                            stock_symbol=service.stock_symbol,
                            shares=shares_to_buy,
                            purchase_price=current_price
                        )
                        
                        result['action'] = 'buy'
                        result['shares_bought'] = shares_to_buy
                        result['transaction_id'] = transaction.id
                        result['total_cost'] = float(shares_to_buy * current_price)
                        result['message'] = f"Bought {shares_to_buy} shares at ${current_price:.2f}"
                        
                        # Update service statistics
                        service.buy_count += 1
                        service.current_shares += shares_to_buy
                        service.updated_at = get_current_datetime()
                        session.commit()
                    except Exception as e:
                        logger.error(f"Error executing buy transaction: {str(e)}")
                        result['success'] = False
                        result['action'] = 'none'
                        result['message'] = f"Error executing buy transaction: {str(e)}"
                else:
                    result['action'] = 'none'
                    result['message'] = "Not enough funds to buy shares"
            else:
                result['action'] = 'none'
                result['message'] = "Buy conditions not met"
                
        elif service.mode == TradingMode.SELL.value:
            # Check sell conditions using technical analysis
            should_sell = TradingServiceService._should_sell(service, price_analysis, current_price)
            result['should_sell'] = should_sell
            
            if should_sell:
                # Get open transactions to sell
                open_transactions = TransactionService.get_open_transactions(session, service_id)
                
                if open_transactions:
                    completed_transactions = []
                    
                    # Sell all open transactions
                    for transaction in open_transactions:
                        try:
                            completed = TransactionService.complete_transaction(
                                session=session,
                                transaction_id=transaction.id,
                                sale_price=current_price
                            )
                            completed_transactions.append(completed)
                        except Exception as e:
                            logger.error(f"Error completing transaction {transaction.id}: {str(e)}")
                    
                    if completed_transactions:
                        total_shares_sold = sum(float(tx.shares) for tx in completed_transactions)
                        total_revenue = total_shares_sold * current_price
                        
                        result['action'] = 'sell'
                        result['transactions_completed'] = len(completed_transactions)
                        result['shares_sold'] = total_shares_sold
                        result['total_revenue'] = float(total_revenue)
                        result['message'] = f"Sold {total_shares_sold} shares at ${current_price:.2f}"
                        
                        # Update service statistics
                        service.sell_count += len(completed_transactions)
                        service.current_shares -= int(total_shares_sold)
                        
                        # Update gain/loss
                        total_gain_loss = sum(float(tx.gain_loss) for tx in completed_transactions if tx.gain_loss)
                        service.total_gain_loss += total_gain_loss
                        
                        service.updated_at = get_current_datetime()
                        session.commit()
                    else:
                        result['action'] = 'none'
                        result['message'] = "Failed to complete any sell transactions"
                else:
                    result['action'] = 'none'
                    result['message'] = "No open transactions to sell"
            else:
                result['action'] = 'none'
                result['message'] = "Sell conditions not met"
                
        elif service.mode == TradingMode.HOLD.value:
            result['action'] = 'none'
            result['message'] = "Service is in HOLD mode, no actions taken"
            
        else:
            result['action'] = 'none'
            result['message'] = f"Unsupported trading mode: {service.mode}"
        
        return result
    
    @staticmethod
    def _should_buy(service: TradingService, price_analysis: Dict[str, Any], current_price: float) -> bool:
        """
        Determine if conditions for buying are met based on technical analysis.
        
        Args:
            service: Trading service instance
            price_analysis: Price analysis dictionary from PriceService
            current_price: Current stock price
            
        Returns:
            True if buy conditions are met, False otherwise
        """
        if not service.can_buy:
            return False
            
        signals = price_analysis.get('signals', {})
        
        # Check available funds
        max_shares_affordable = int(service.current_balance / current_price) if current_price > 0 else 0
        if max_shares_affordable <= 0:
            return False
            
        # Default to a conservative strategy that looks for oversold conditions
        # and bullish trends
        
        # RSI oversold signal (strongest buy indicator)
        if signals.get('rsi') == 'oversold':
            return True
            
        # Bullish MA crossover
        if signals.get('ma_crossover') == 'bullish':
            return True
            
        # Price near lower Bollinger Band (potential reversal)
        if signals.get('bollinger') == 'oversold':
            return True
            
        # Check price trends
        is_uptrend = price_analysis.get('is_uptrend')
        if is_uptrend and signals.get('rsi') == 'neutral':
            # Price is trending up with neutral RSI
            return True
            
        # Check recent price changes
        price_changes = price_analysis.get('price_changes', {})
        # Buy after a recent dip followed by recovery
        if (price_changes.get('1_day', 0) > 0 and 
            price_changes.get('5_day', 0) < -service.buy_threshold):
            return True
            
        return False
    
    @staticmethod
    def _should_sell(service: TradingService, price_analysis: Dict[str, Any], current_price: float) -> bool:
        """
        Determine if conditions for selling are met based on technical analysis.
        
        Args:
            service: Trading service instance
            price_analysis: Price analysis dictionary from PriceService
            current_price: Current stock price
            
        Returns:
            True if sell conditions are met, False otherwise
        """
        if not service.can_sell:
            return False
        
        signals = price_analysis.get('signals', {})
        
        # No shares to sell
        if service.current_shares <= 0:
            return False
            
        # Default to a strategy that looks for overbought conditions
        # and bearish trends
        
        # RSI overbought signal (strongest sell indicator)
        if signals.get('rsi') == 'overbought':
            return True
            
        # Bearish MA crossover
        if signals.get('ma_crossover') == 'bearish':
            return True
            
        # Price near upper Bollinger Band (potential reversal)
        if signals.get('bollinger') == 'overbought':
            return True
            
        # Check price trends
        is_uptrend = price_analysis.get('is_uptrend')
        if not is_uptrend and signals.get('rsi', '') != 'oversold':
            # Price is trending down and not oversold
            return True
            
        # Check for take profit or stop loss
        # Get average purchase price from open transactions
        session = object_session(service)
        if session:
            open_transactions = session.query(TradingTransaction).filter(
                and_(
                    TradingTransaction.service_id == service.id,
                    TradingTransaction.state == TransactionState.OPEN.value
                )
            ).all()
            
            if open_transactions:
                # Calculate average purchase price
                total_shares = sum(float(tx.shares) for tx in open_transactions)
                total_cost = sum(float(tx.purchase_price) * float(tx.shares) for tx in open_transactions)
                avg_purchase_price = total_cost / total_shares if total_shares > 0 else 0
                
                if avg_purchase_price > 0:
                    # Calculate percent gain/loss
                    price_change_pct = ((current_price - avg_purchase_price) / avg_purchase_price) * 100
                    
                    # Take profit
                    if price_change_pct >= float(service.take_profit_percent):
                        return True
                        
                    # Stop loss
                    if price_change_pct <= -float(service.stop_loss_percent):
                        return True
        
        return False
    
    @staticmethod
    def backtest_strategy(session: Session, service_id: int, days: int = 90) -> Dict[str, Any]:
        """
        Backtest a trading strategy using historical price data.
        
        Args:
            session: Database session
            service_id: Trading service ID
            days: Number of days to backtest
            
        Returns:
            Dictionary with backtest results
            
        Raises:
            ResourceNotFoundError: If service not found
            BusinessLogicError: If backtest cannot be performed
        """
        from app.services.events import EventService
        from app.services.price_service import PriceService
        
        try:
            # Get the service
            service = session.query(TradingService).get(service_id)
            if not service:
                raise ResourceNotFoundError(f"Trading service with ID {service_id} not found")
            
            # Get the stock
            stock = session.query(Stock).filter_by(symbol=service.stock_symbol).first()
            if not stock:
                raise ResourceNotFoundError(f"Stock with symbol {service.stock_symbol} not found")
            
            # Create a backtest event for tracking
            EventService.emit_system_notification(
                notification_type='backtest',
                message=f"Starting backtest for service {service_id} ({service.name}) on {service.stock_symbol}",
                severity='info',
                details={'service_id': service_id, 'days': days}
            )
            
            # Get historical price data
            end_date = get_current_date()
            start_date = end_date - timedelta(days=days)
            
            # Get daily prices
            prices = session.query(StockDailyPrice).filter(
                and_(
                    StockDailyPrice.stock_id == stock.id,
                    StockDailyPrice.price_date >= start_date,
                    StockDailyPrice.price_date <= end_date
                )
            ).order_by(StockDailyPrice.price_date).all()
            
            if not prices:
                raise BusinessLogicError(f"Not enough price data for stock {service.stock_symbol} to backtest")
                
            # Initialize backtest variables
            initial_balance = 10000.0  # Start with $10k
            current_balance = initial_balance
            shares_held = 0
            transactions = []
            buy_threshold = service.buy_threshold
            sell_threshold = service.sell_threshold
            allocation_percent = service.allocation_percent
            
            # Backtest parameters
            price_history = []
            portfolio_values = []
            last_buy_price = None
            
            # Run through the historical data
            for i, price in enumerate(prices):
                # Skip first 20 days to allow for SMA calculations
                if i < 20:
                    price_history.append(float(price.close_price))
                    portfolio_values.append(current_balance)
                    continue
                
                # Add price to history
                price_history.append(float(price.close_price))
                current_price = float(price.close_price)
                
                # Calculate metrics for this day
                if i >= 20:
                    # Get price history for analysis
                    recent_prices = price_history[max(0, i-50):i+1]
                    
                    # Calculate basic price analysis
                    price_analysis = {
                        'close_price': current_price,
                        'sma_5': sum(price_history[i-4:i+1]) / 5,
                        'sma_10': sum(price_history[i-9:i+1]) / 10,
                        'sma_20': sum(price_history[i-19:i+1]) / 20,
                    }
                    
                    # Check if we should buy
                    if shares_held == 0:
                        should_buy = TradingServiceService._should_buy_backtest(
                            price_analysis, current_price, current_balance, 
                            buy_threshold, allocation_percent
                        )
                        
                        if should_buy:
                            # Calculate shares to buy
                            amount_to_spend = current_balance * (allocation_percent / 100.0)
                            shares_to_buy = amount_to_spend / current_price
                            shares_to_buy = int(shares_to_buy * 100) / 100.0  # Round to 2 decimal places
                            
                            # Execute buy
                            if shares_to_buy > 0:
                                cost = shares_to_buy * current_price
                                if cost <= current_balance:
                                    current_balance -= cost
                                    shares_held = shares_to_buy
                                    last_buy_price = current_price
                                    
                                    # Log transaction
                                    transactions.append({
                                        'type': 'buy',
                                        'date': price.price_date.isoformat(),
                                        'price': current_price,
                                        'shares': shares_held,
                                        'cost': cost,
                                        'balance': current_balance
                                    })
                    
                    # Check if we should sell
                    elif shares_held > 0 and last_buy_price is not None:
                        # Add position gain/loss to price analysis
                        if last_buy_price > 0:
                            price_analysis['percent_gain'] = ((current_price - last_buy_price) / last_buy_price) * 100
                        
                        should_sell = TradingServiceService._should_sell_backtest(price_analysis)
                        
                        if should_sell:
                            # Execute sell
                            revenue = shares_held * current_price
                            gain_loss = revenue - (shares_held * last_buy_price)
                            current_balance += revenue
                            
                            # Log transaction
                            transactions.append({
                                'type': 'sell',
                                'date': price.price_date.isoformat(),
                                'price': current_price,
                                'shares': shares_held,
                                'revenue': revenue,
                                'gain_loss': gain_loss,
                                'percent_gain': (gain_loss / (shares_held * last_buy_price)) * 100 if last_buy_price > 0 else 0,
                                'balance': current_balance
                            })
                            
                            # Reset position
                            shares_held = 0
                            last_buy_price = None
                
                # Calculate portfolio value for this day
                portfolio_value = current_balance + (shares_held * current_price)
                portfolio_values.append(portfolio_value)
            
            # Calculate backtest results
            start_value = initial_balance
            end_value = portfolio_values[-1] if portfolio_values else initial_balance
            
            total_return = end_value - start_value
            percent_return = (total_return / start_value) * 100 if start_value > 0 else 0
            
            # Calculate annualized return
            days_elapsed = min(days, len(portfolio_values))
            if days_elapsed > 0:
                annualized_return = ((1 + (percent_return / 100)) ** (365 / days_elapsed) - 1) * 100
            else:
                annualized_return = 0
                
            # Calculate drawdown
            max_drawdown = 0
            peak = portfolio_values[0] if portfolio_values else 0
            
            for value in portfolio_values:
                if value > peak:
                    peak = value
                else:
                    drawdown = (peak - value) / peak * 100 if peak > 0 else 0
                    max_drawdown = max(max_drawdown, drawdown)
            
            # Calculate sharpe ratio (simplified)
            if len(portfolio_values) > 1:
                # Calculate daily returns
                daily_returns = [(portfolio_values[i] / portfolio_values[i-1]) - 1 for i in range(1, len(portfolio_values))]
                
                # Calculate mean and standard deviation
                mean_return = sum(daily_returns) / len(daily_returns)
                std_dev = (sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)) ** 0.5
                
                # Annualize
                sharpe_ratio = (mean_return * 252) / (std_dev * (252 ** 0.5)) if std_dev > 0 else 0
            else:
                sharpe_ratio = 0
            
            # Compile results
            results = {
                'service_id': service_id,
                'service_name': service.name,
                'stock_symbol': service.stock_symbol,
                'backtest_days': days,
                'initial_balance': initial_balance,
                'final_balance': current_balance,
                'final_portfolio_value': end_value,
                'total_return': total_return,
                'percent_return': percent_return,
                'annualized_return': annualized_return,
                'max_drawdown': max_drawdown,
                'sharpe_ratio': sharpe_ratio,
                'transactions': transactions,
                'transaction_count': len(transactions),
                'portfolio_values': portfolio_values[:10],  # Just return a sample for the API
                'price_history': price_history[:10],  # Just return a sample for the API
            }
            
            # Emit metrics event with backtest results
            EventService.emit_metrics_update(
                metric_type='backtest_results',
                metric_data=results,
                resource_id=service_id,
                resource_type='service'
            )
            
            # Emit completion notification
            EventService.emit_system_notification(
                notification_type='backtest',
                message=f"Backtest completed for service {service_id} with {percent_return:.2f}% return",
                severity='info',
                details={
                    'service_id': service_id,
                    'percent_return': percent_return,
                    'transactions': len(transactions)
                }
            )
            
            return results
        except Exception as e:
            logger.error(f"Error in backtest: {str(e)}")
            
            # Emit error notification
            EventService.emit_system_notification(
                notification_type='backtest',
                message=f"Backtest failed for service {service_id}: {str(e)}",
                severity='error',
                details={'service_id': service_id, 'error': str(e)}
            )
            
            if isinstance(e, (ResourceNotFoundError, BusinessLogicError)):
                raise
            raise BusinessLogicError(f"Backtest failed: {str(e)}")

    @staticmethod
    def _should_buy_backtest(price_analysis: Dict[str, Any], current_price: float,
                           current_balance: float, buy_threshold: float,
                           allocation_percent: float) -> bool:
        """
        Simplified version of _should_buy for backtesting.
        
        Args:
            price_analysis: Price analysis dictionary
            current_price: Current stock price
            current_balance: Available balance
            buy_threshold: Buy threshold percentage
            allocation_percent: Allocation percentage
            
        Returns:
            True if buy conditions are met, False otherwise
        """
        signals = price_analysis.get('signals', {})
        
        # Check available funds
        max_shares_affordable = int(current_balance / current_price) if current_price > 0 else 0
        if max_shares_affordable <= 0:
            return False
            
        # RSI oversold signal (strongest buy indicator)
        if signals.get('rsi') == 'oversold':
            return True
            
        # Bullish MA crossover
        if signals.get('ma_crossover') == 'bullish':
            return True
            
        # Price near lower Bollinger Band (potential reversal)
        if signals.get('bollinger') == 'oversold':
            return True
            
        # Check price trends
        is_uptrend = price_analysis.get('is_uptrend')
        if is_uptrend and signals.get('rsi') == 'neutral':
            # Price is trending up with neutral RSI
            return True
            
        return False
    
    @staticmethod
    def _should_sell_backtest(price_analysis: Dict[str, Any]) -> bool:
        """
        Simplified version of _should_sell for backtesting.
        
        Args:
            price_analysis: Price analysis dictionary
            
        Returns:
            True if sell conditions are met, False otherwise
        """
        signals = price_analysis.get('signals', {})
        
        # RSI overbought signal (strongest sell indicator)
        if signals.get('rsi') == 'overbought':
            return True
            
        # Bearish MA crossover
        if signals.get('ma_crossover') == 'bearish':
            return True
            
        # Price near upper Bollinger Band (potential reversal)
        if signals.get('bollinger') == 'overbought':
            return True
            
        # Check price trends
        is_uptrend = price_analysis.get('is_uptrend')
        if not is_uptrend and signals.get('rsi', '') != 'oversold':
            # Price is trending down and not oversold
            return True
            
        return False
