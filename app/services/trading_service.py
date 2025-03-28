"""
Trading Service service for managing TradingService model operations.

This service encapsulates all database interactions for the TradingService model,
providing a clean API for trading service management operations.
"""
import logging
from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.models.trading_service import TradingService
from app.models.enums import ServiceState, TradingMode
from app.models.stock import Stock
from app.utils.errors import ValidationError, ResourceNotFoundError, BusinessLogicError, AuthorizationError
from app.utils.current_datetime import get_current_datetime
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
        return TradingService.get_by_id(session, service_id)
    
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
        return TradingService.get_by_user(session, user_id)
    
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
        return TradingService.get_by_stock(session, stock_symbol)
    
    @staticmethod
    def get_all(session: Session) -> List[TradingService]:
        """
        Get all trading services.
        
        Args:
            session: Database session
            
        Returns:
            List of TradingService instances
        """
        return TradingService.get_all(session)
    
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
            
            # Set user_id
            data['user_id'] = user_id
            
            # Check if stock exists and update stock_id
            stock_symbol = data['stock_symbol'].upper()
            stock = session.query(Stock).filter(Stock.symbol == stock_symbol).first()
            if stock:
                data['stock_id'] = stock.id
            else:
                logger.warning(f"Stock with symbol {stock_symbol} not found in database")
            
            # Set current_balance to initial_balance when creating
            if 'initial_balance' in data and 'current_balance' not in data:
                data['current_balance'] = data['initial_balance']
            
            # Create the service
            service = TradingService.from_dict(data)
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
        except ValueError as e:
            # Convert ValueError to ValidationError for consistency
            logger.error(f"Validation error creating trading service: {str(e)}")
            session.rollback()
            raise ValidationError(str(e))
        except Exception as e:
            logger.error(f"Error creating trading service: {str(e)}")
            session.rollback()
            if isinstance(e, ValidationError):
                raise
            raise BusinessLogicError(f"Could not create trading service: {str(e)}")
    
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
            BusinessLogicError: For other business logic errors
        """
        from app.services.events import EventService
        
        try:
            # Define which fields can be updated
            allowed_fields = {
                'name', 'description', 'stock_symbol', 'is_active',
                'minimum_balance', 'allocation_percent', 'buy_threshold',
                'sell_threshold', 'stop_loss_percent', 'take_profit_percent'
            }
            
            # Use the update_from_dict method from Base
            updated = service.update_from_data(data, allowed_fields)
            
            # Only emit event if something was updated
            if updated:
                # Update stock_id if stock_symbol changed
                if 'stock_symbol' in data:
                    stock = session.query(Stock).filter(Stock.symbol == service.stock_symbol).first()
                    if stock:
                        service.stock_id = stock.id
                    else:
                        logger.warning(f"Stock with symbol {service.stock_symbol} not found in database")
                        service.stock_id = None
                
                session.commit()
                
                # Prepare response data
                service_data = service_schema.dump(service)
                
                # Emit WebSocket event
                EventService.emit_service_update(
                    action='updated',
                    service_data=service_data,
                    service_id=service.id
                )
            
            return service
        except ValueError as e:
            # Convert ValueError to ValidationError for consistency
            logger.error(f"Validation error updating trading service: {str(e)}")
            session.rollback()
            raise ValidationError(str(e))
        except Exception as e:
            logger.error(f"Error updating trading service: {str(e)}")
            session.rollback()
            if isinstance(e, ValidationError):
                raise
            raise BusinessLogicError(f"Could not update trading service: {str(e)}")
    
    @staticmethod
    def toggle_active(session: Session, service: TradingService) -> TradingService:
        """
        Toggle the active status of a trading service.
        
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
            
            # Emit WebSocket event
            EventService.emit_service_update(
                action='toggled',
                service_data=service_data,
                service_id=service.id
            )
            
            return service
        except Exception as e:
            logger.error(f"Error toggling trading service active status: {str(e)}")
            session.rollback()
            raise BusinessLogicError(f"Could not toggle trading service status: {str(e)}")
    
    @staticmethod
    def change_state(session: Session, service: TradingService, new_state: str) -> TradingService:
        """
        Change the state of a trading service.
        
        Args:
            session: Database session
            service: TradingService instance
            new_state: New state to set
            
        Returns:
            Updated TradingService instance
            
        Raises:
            ValidationError: If the state is invalid
            BusinessLogicError: For other business logic errors
        """
        from app.services.events import EventService
        
        try:
            # Validate state
            if not ServiceState.is_valid(new_state):
                valid_states = ServiceState.values()
                raise ValidationError(f"Invalid service state: {new_state}. Valid states are: {', '.join(valid_states)}")
            
            # Only update if state is changing
            if service.state != new_state:
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
        except ValueError as e:
            # Convert ValueError to ValidationError for consistency
            logger.error(f"Validation error changing trading service state: {str(e)}")
            session.rollback()
            raise ValidationError(str(e))
        except Exception as e:
            logger.error(f"Error changing trading service state: {str(e)}")
            session.rollback()
            if isinstance(e, ValidationError):
                raise
            raise BusinessLogicError(f"Could not change trading service state: {str(e)}")
    
    @staticmethod
    def change_mode(session: Session, service: TradingService, new_mode: str) -> TradingService:
        """
        Change the trading mode of a trading service.
        
        Args:
            session: Database session
            service: TradingService instance
            new_mode: New mode to set
            
        Returns:
            Updated TradingService instance
            
        Raises:
            ValidationError: If the mode is invalid
            BusinessLogicError: For other business logic errors
        """
        from app.services.events import EventService
        
        try:
            # Validate mode
            if not TradingMode.is_valid(new_mode):
                valid_modes = TradingMode.values()
                raise ValidationError(f"Invalid trading mode: {new_mode}. Valid modes are: {', '.join(valid_modes)}")
            
            # Check for constraints when changing mode
            if new_mode == TradingMode.SELL.value and service.current_shares <= 0:
                raise BusinessLogicError(f"Cannot change mode to SELL because the service has no shares to sell")
            
            # Only update if mode is changing
            if service.mode != new_mode:
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
        except ValueError as e:
            # Convert ValueError to ValidationError for consistency
            logger.error(f"Validation error changing trading service mode: {str(e)}")
            session.rollback()
            raise ValidationError(str(e))
        except Exception as e:
            logger.error(f"Error changing trading service mode: {str(e)}")
            session.rollback()
            if isinstance(e, ValidationError):
                raise
            raise BusinessLogicError(f"Could not change trading service mode: {str(e)}")
    
    @staticmethod
    def delete_service(session: Session, service: TradingService) -> bool:
        """
        Delete a trading service.
        
        Args:
            session: Database session
            service: TradingService to delete
            
        Returns:
            True if successful
            
        Raises:
            BusinessLogicError: If service cannot be deleted due to dependencies
        """
        from app.services.events import EventService
        
        try:
            # Check for dependencies using the model's method
            if service.has_dependencies():
                transaction_count = len(service.transactions) if service.transactions else 0
                raise BusinessLogicError(f"Cannot delete trading service with ID {service.id} because it has {transaction_count} associated transactions")
            
            service_id = service.id
            session.delete(service)
            session.commit()
            
            # Emit WebSocket event
            EventService.emit_service_update(
                action='deleted',
                service_data={'id': service_id},
                service_id=service_id
            )
            
            return True
        except Exception as e:
            logger.error(f"Error deleting trading service: {str(e)}")
            session.rollback()
            if isinstance(e, BusinessLogicError):
                raise
            raise BusinessLogicError(f"Could not delete trading service: {str(e)}")
    
    # Trading logic operations
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
            # Ensure we have historical prices for analysis
            if not historical_prices:
                # In a real app, we would fetch historical prices from a price service
                # For now, just create a dummy array with the current price repeated
                historical_prices = [current_price, current_price * 1.05]  # Dummy data for testing
            
            # Use the model's check_buy_condition method
            buy_decision = service.check_buy_condition(current_price, historical_prices)
            
            # Add service context to the decision
            if 'details' not in buy_decision:
                buy_decision['details'] = {}
                
            buy_decision['details'].update({
                'service_id': service.id,
                'stock_symbol': service.stock_symbol,
                'is_active': service.is_active,
                'state': service.state,
                'mode': service.mode,
                'current_price': current_price,
                'historical_prices': historical_prices[-5:] if len(historical_prices) > 5 else historical_prices,
                'current_balance': float(service.current_balance),
                'buy_threshold': float(service.buy_threshold)
            })
            
            return {
                'should_proceed': buy_decision.get('should_buy', False),
                'reason': buy_decision.get('reason', 'No reason provided'),
                'timestamp': get_current_datetime().isoformat(),
                'details': buy_decision,
                'service_id': service.id,
                'next_action': 'BUY' if buy_decision.get('should_buy', False) else 'WAIT'
            }
        except Exception as e:
            logger.error(f"Error checking buy condition: {str(e)}")
            raise BusinessLogicError(f"Could not check buy condition: {str(e)}")
    
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
            # Ensure we have historical prices for analysis
            if not historical_prices:
                # In a real app, we would fetch historical prices from a price service
                # For now, just create a dummy array with the current price repeated
                historical_prices = [current_price, current_price * 0.95]  # Dummy data for testing
            
            # Use the model's check_sell_condition method
            sell_decision = service.check_sell_condition(current_price, historical_prices)
            
            # Add service context to the decision
            if 'details' not in sell_decision:
                sell_decision['details'] = {}
                
            sell_decision['details'].update({
                'service_id': service.id,
                'stock_symbol': service.stock_symbol,
                'is_active': service.is_active,
                'state': service.state,
                'mode': service.mode,
                'current_price': current_price,
                'historical_prices': historical_prices[-5:] if len(historical_prices) > 5 else historical_prices,
                'current_shares': service.current_shares,
                'sell_threshold': float(service.sell_threshold)
            })
            
            return {
                'should_proceed': sell_decision.get('should_sell', False),
                'reason': sell_decision.get('reason', 'No reason provided'),
                'timestamp': get_current_datetime().isoformat(),
                'details': sell_decision,
                'service_id': service.id,
                'next_action': 'SELL' if sell_decision.get('should_sell', False) else 'WAIT'
            }
        except Exception as e:
            logger.error(f"Error checking sell condition: {str(e)}")
            raise BusinessLogicError(f"Could not check sell condition: {str(e)}")
    
    @staticmethod
    def get_current_price(session: Session, stock_symbol: str) -> float:
        """
        Get the current price for a stock.
        
        Args:
            session: Database session
            stock_symbol: Stock symbol
            
        Returns:
            Current price of the stock
        """
        try:
            # In a real app, this would get the latest price from a price service
            # For now, look it up from the stock model
            stock = session.query(Stock).filter(Stock.symbol == stock_symbol.upper()).first()
            if not stock:
                logger.warning(f"Stock with symbol {stock_symbol} not found in database")
                return 100.0  # Fallback dummy value
                
            latest_price = stock.get_latest_price()
            if latest_price is not None:
                return latest_price
            
            # Fallback to a dummy value if no price is available
            logger.warning(f"No price available for stock {stock_symbol}")
            return 100.0
        except Exception as e:
            logger.error(f"Error getting current price for stock {stock_symbol}: {str(e)}")
            return 100.0  # Fallback to a dummy value
