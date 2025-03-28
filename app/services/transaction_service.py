"""
Transaction service for managing TradingTransaction model operations.

This service encapsulates all database interactions for the TradingTransaction model,
providing a clean API for trading transaction management operations.
"""
import logging
from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.models.trading_transaction import TradingTransaction
from app.models.trading_service import TradingService
from app.models.stock import Stock
from app.models.enums import TransactionState, TradingMode
from app.utils.errors import ValidationError, ResourceNotFoundError, BusinessLogicError, AuthorizationError
from app.utils.current_datetime import get_current_datetime
from app.api.schemas.trading_transaction import transaction_schema, transactions_schema
from app.api.schemas.trading_service import service_schema

# Set up logging
logger = logging.getLogger(__name__)

class TransactionService:
    """Service for TradingTransaction model operations."""
    
    # Read operations
    @staticmethod
    def get_by_id(session: Session, transaction_id: int) -> Optional[TradingTransaction]:
        """
        Get a transaction by ID.
        
        Args:
            session: Database session
            transaction_id: Transaction ID to retrieve
            
        Returns:
            TradingTransaction instance if found, None otherwise
        """
        return TradingTransaction.get_by_id(session, transaction_id)
    
    @staticmethod
    def get_or_404(session: Session, transaction_id: int) -> TradingTransaction:
        """
        Get a transaction by ID or raise ResourceNotFoundError.
        
        Args:
            session: Database session
            transaction_id: Transaction ID to retrieve
            
        Returns:
            TradingTransaction instance
            
        Raises:
            ResourceNotFoundError: If transaction not found
        """
        transaction = TransactionService.get_by_id(session, transaction_id)
        if not transaction:
            raise ResourceNotFoundError(f"Transaction with ID {transaction_id} not found")
        return transaction
    
    @staticmethod
    def get_by_service(session: Session, service_id: int, state: Optional[str] = None) -> List[TradingTransaction]:
        """
        Get transactions for a service, optionally filtered by state.
        
        Args:
            session: Database session
            service_id: Service ID
            state: Optional state filter
            
        Returns:
            List of transactions
            
        Raises:
            ValidationError: If state is invalid
        """
        try:
            return TradingTransaction.get_by_service(session, service_id, state)
        except ValueError as e:
            # Convert ValueError from model to ValidationError for API consistency
            raise ValidationError(str(e))
    
    @staticmethod
    def get_open_transactions(session: Session, service_id: Optional[int] = None) -> List[TradingTransaction]:
        """
        Get all open transactions, optionally filtered by service ID.
        
        Args:
            session: Database session
            service_id: Optional service ID filter
            
        Returns:
            List of open transactions
        """
        return TradingTransaction.get_open_transactions(session, service_id)
    
    @staticmethod
    def check_ownership(session: Session, transaction_id: int, user_id: int) -> bool:
        """
        Check if a user owns a transaction (through service ownership).
        
        Args:
            session: Database session
            transaction_id: Transaction ID
            user_id: User ID
            
        Returns:
            True if the user owns the service that owns the transaction, False otherwise
        """
        transaction = TransactionService.get_by_id(session, transaction_id)
        if not transaction:
            return False
        
        service = session.query(TradingService).filter_by(id=transaction.service_id, user_id=user_id).first()
        return service is not None
    
    @staticmethod
    def verify_ownership(session: Session, transaction_id: int, user_id: int) -> TradingTransaction:
        """
        Verify a user owns a transaction (through service ownership), and return the transaction if they do.
        
        Args:
            session: Database session
            transaction_id: Transaction ID
            user_id: User ID
            
        Returns:
            TradingTransaction instance
            
        Raises:
            ResourceNotFoundError: If transaction not found
            AuthorizationError: If user does not own the transaction
        """
        transaction = TransactionService.get_or_404(session, transaction_id)
        
        service = session.query(TradingService).filter_by(id=transaction.service_id, user_id=user_id).first()
        if not service:
            raise AuthorizationError(f"User {user_id} does not own the service for transaction {transaction_id}")
        
        return transaction
    
    # Write operations
    @staticmethod
    def create_buy_transaction(session: Session, service_id: int, stock_symbol: str, 
                              shares: float, purchase_price: float) -> TradingTransaction:
        """
        Create a new buy transaction for a trading service.
        
        Args:
            session: Database session
            service_id: Trading service ID
            stock_symbol: Stock symbol to buy
            shares: Number of shares to buy
            purchase_price: Price per share
            
        Returns:
            The created transaction instance
            
        Raises:
            ValidationError: If the input data is invalid
            ResourceNotFoundError: If the service doesn't exist
            BusinessLogicError: If the service doesn't have enough funds or is not in BUY mode
        """
        from app.services.events import EventService
        
        try:
            # Validate input
            if shares <= 0:
                raise ValidationError("Shares must be greater than zero")
                
            if purchase_price <= 0:
                raise ValidationError("Purchase price must be greater than zero")
            
            # Get the service
            service = session.query(TradingService).filter_by(id=service_id).first()
            if not service:
                raise ResourceNotFoundError(f"Trading service with ID {service_id} not found")
            
            # Check if service can buy
            total_cost = shares * purchase_price
            if total_cost > service.current_balance:
                raise BusinessLogicError(f"Insufficient funds. Required: ${total_cost:.2f}, Available: ${service.current_balance:.2f}")
            
            if not service.can_buy:
                raise BusinessLogicError(f"Service is not in a state that allows buying (current state: {service.state}, mode: {service.mode})")
            
            # Find stock if it exists
            stock = session.query(Stock).filter(Stock.symbol == stock_symbol.upper()).first()
            stock_id = stock.id if stock else None
            
            # Create transaction
            transaction_data = {
                'service_id': service_id,
                'stock_id': stock_id,
                'stock_symbol': stock_symbol.upper(),
                'shares': shares,
                'purchase_price': purchase_price,
                'state': TransactionState.OPEN.value,
                'purchase_date': get_current_datetime()
            }
            
            transaction = TradingTransaction.from_dict(transaction_data)
            session.add(transaction)
            
            # Update service
            service.current_balance -= total_cost
            service.current_shares += shares
            service.buy_count += 1
            service.mode = TradingMode.SELL.value
            
            session.commit()
            
            # Emit WebSocket events
            transaction_data = transaction.to_dict()
            service_data = service_schema.dump(service)
            
            EventService.emit_transaction_update(
                action='created',
                transaction_data=transaction_data,
                service_id=service_id
            )
            
            EventService.emit_service_update(
                action='updated',
                service_data=service_data,
                service_id=service_id
            )
            
            return transaction
            
        except ValidationError:
            session.rollback()
            raise
        except ResourceNotFoundError:
            session.rollback()
            raise
        except BusinessLogicError:
            session.rollback()
            raise
        except Exception as e:
            logger.error(f"Error creating buy transaction: {str(e)}")
            session.rollback()
            raise BusinessLogicError(f"Could not create buy transaction: {str(e)}")
    
    @staticmethod
    def complete_transaction(session: Session, transaction_id: int, sale_price: Decimal) -> TradingTransaction:
        """
        Complete a transaction by selling shares.
        
        Args:
            session: Database session
            transaction_id: Transaction ID to complete
            sale_price: Price per share for the sale
            
        Returns:
            Updated transaction instance
            
        Raises:
            ValidationError: If sale price is invalid
            ResourceNotFoundError: If transaction not found
            BusinessLogicError: If transaction is already completed
        """
        from app.services.events import EventService
        
        try:
            # Validate sale price
            if sale_price <= 0:
                raise ValidationError("Sale price must be greater than zero")
            
            # Get the transaction
            transaction = TransactionService.get_or_404(session, transaction_id)
            
            # Check if transaction can be completed
            if transaction.state == TransactionState.CLOSED.value:
                raise BusinessLogicError("Transaction is already completed")
            
            if transaction.state == TransactionState.CANCELLED.value:
                raise BusinessLogicError("Cannot complete a cancelled transaction")
            
            # Update transaction
            transaction.update_from_dict({
                'sale_price': sale_price,
                'sale_date': get_current_datetime(),
                'state': TransactionState.CLOSED.value
            })
            
            # Update service
            service = transaction.service
            service.current_balance += (transaction.sale_price * transaction.shares)
            service.total_gain_loss += transaction.gain_loss
            service.current_shares -= transaction.shares
            service.sell_count += 1
            
            # Change service mode to BUY if no shares left
            if service.current_shares == 0:
                service.mode = TradingMode.BUY.value
            
            session.commit()
            
            # Emit WebSocket events
            transaction_data = transaction.to_dict()
            service_data = service_schema.dump(service)
            
            EventService.emit_transaction_update(
                action='completed',
                transaction_data=transaction_data,
                service_id=service.id
            )
            
            EventService.emit_service_update(
                action='updated',
                service_data=service_data,
                service_id=service.id
            )
            
            return transaction
            
        except ValidationError:
            session.rollback()
            raise
        except ResourceNotFoundError:
            session.rollback()
            raise
        except BusinessLogicError:
            session.rollback()
            raise
        except Exception as e:
            logger.error(f"Error completing transaction: {str(e)}")
            session.rollback()
            raise BusinessLogicError(f"Could not complete transaction: {str(e)}")
    
    @staticmethod
    def cancel_transaction(session: Session, transaction_id: int, reason: str = "User cancelled") -> TradingTransaction:
        """
        Cancel a transaction.
        
        Args:
            session: Database session
            transaction_id: Transaction ID to cancel
            reason: Reason for cancellation
            
        Returns:
            Updated transaction instance
            
        Raises:
            ResourceNotFoundError: If transaction not found
            BusinessLogicError: If transaction cannot be cancelled
        """
        from app.services.events import EventService
        
        try:
            # Get the transaction
            transaction = TransactionService.get_or_404(session, transaction_id)
            
            # Check if transaction can be cancelled
            if transaction.state == TransactionState.CLOSED.value:
                raise BusinessLogicError("Cannot cancel a completed transaction")
                
            if transaction.state == TransactionState.CANCELLED.value:
                raise BusinessLogicError("Transaction is already cancelled")
            
            if not transaction.can_be_cancelled:
                raise BusinessLogicError("Transaction cannot be cancelled in its current state")
            
            # Update transaction
            transaction.update_from_dict({
                'state': TransactionState.CANCELLED.value,
                'notes': reason
            })
            
            # Update service
            service = transaction.service
            service.current_balance += (transaction.purchase_price * transaction.shares)
            service.current_shares -= transaction.shares
            
            # Change service mode to BUY if no shares left
            if service.current_shares == 0:
                service.mode = TradingMode.BUY.value
            
            session.commit()
            
            # Emit WebSocket events
            transaction_data = transaction.to_dict()
            service_data = service_schema.dump(service)
            
            EventService.emit_transaction_update(
                action='cancelled',
                transaction_data=transaction_data,
                service_id=service.id,
                additional_data={'reason': reason}
            )
            
            EventService.emit_service_update(
                action='updated',
                service_data=service_data,
                service_id=service.id
            )
            
            return transaction
            
        except ResourceNotFoundError:
            session.rollback()
            raise
        except BusinessLogicError:
            session.rollback()
            raise
        except Exception as e:
            logger.error(f"Error cancelling transaction: {str(e)}")
            session.rollback()
            raise BusinessLogicError(f"Could not cancel transaction: {str(e)}")
    
    @staticmethod
    def delete_transaction(session: Session, transaction_id: int) -> bool:
        """
        Delete a transaction. Only cancelled transactions can be deleted.
        
        Args:
            session: Database session
            transaction_id: Transaction ID to delete
            
        Returns:
            True if successful
            
        Raises:
            ResourceNotFoundError: If transaction not found
            BusinessLogicError: If transaction cannot be deleted
        """
        from app.services.events import EventService
        
        try:
            # Get the transaction
            transaction = TransactionService.get_or_404(session, transaction_id)
            
            # Check if transaction can be deleted
            if transaction.state != TransactionState.CANCELLED.value:
                raise BusinessLogicError("Cannot delete an open or closed transaction")
            
            service_id = transaction.service_id
            
            # Delete transaction
            session.delete(transaction)
            session.commit()
            
            # Emit WebSocket event
            EventService.emit_transaction_update(
                action='deleted',
                transaction_data={'id': transaction_id},
                service_id=service_id
            )
            
            return True
            
        except ResourceNotFoundError:
            session.rollback()
            raise
        except BusinessLogicError:
            session.rollback()
            raise
        except Exception as e:
            logger.error(f"Error deleting transaction: {str(e)}")
            session.rollback()
            raise BusinessLogicError(f"Could not delete transaction: {str(e)}")
    
    @staticmethod
    def update_transaction_notes(session: Session, transaction_id: int, notes: str) -> TradingTransaction:
        """
        Update transaction notes.
        
        Args:
            session: Database session
            transaction_id: Transaction ID
            notes: New notes
            
        Returns:
            Updated transaction instance
            
        Raises:
            ResourceNotFoundError: If transaction not found
        """
        from app.services.events import EventService
        
        try:
            # Get the transaction
            transaction = TransactionService.get_or_404(session, transaction_id)
            
            # Update notes
            if transaction.notes != notes:
                transaction.update_from_dict({
                    'notes': notes,
                    'updated_at': get_current_datetime()
                })
                
                session.commit()
                
                # Emit WebSocket event
                transaction_data = transaction.to_dict()
                
                EventService.emit_transaction_update(
                    action='updated',
                    transaction_data=transaction_data,
                    service_id=transaction.service_id
                )
            
            return transaction
            
        except ResourceNotFoundError:
            session.rollback()
            raise
        except Exception as e:
            logger.error(f"Error updating transaction notes: {str(e)}")
            session.rollback()
            raise BusinessLogicError(f"Could not update transaction notes: {str(e)}")
    
    @staticmethod
    def calculate_transaction_metrics(session: Session, service_id: int) -> Dict[str, Any]:
        """
        Calculate metrics for transactions of a service.
        
        Args:
            session: Database session
            service_id: Service ID
            
        Returns:
            Dictionary with transaction metrics
        """
        try:
            # Get all transactions for the service
            transactions = TransactionService.get_by_service(session, service_id)
            
            # Initialize metrics
            metrics = {
                'total_transactions': len(transactions),
                'open_transactions': 0,
                'closed_transactions': 0,
                'cancelled_transactions': 0,
                'total_bought': 0,
                'total_sold': 0,
                'total_gain_loss': 0,
                'average_gain_loss_percent': 0,
                'best_transaction': None,
                'worst_transaction': None,
                'average_transaction_duration_days': 0
            }
            
            if not transactions:
                return metrics
            
            # Calculate metrics
            total_gain_loss_percent = 0
            total_duration_days = 0
            closed_count = 0
            best_gain_percent = -float('inf')
            worst_gain_percent = float('inf')
            best_transaction = None
            worst_transaction = None
            
            for transaction in transactions:
                if transaction.state == TransactionState.OPEN.value:
                    metrics['open_transactions'] += 1
                    metrics['total_bought'] += float(transaction.total_cost)
                elif transaction.state == TransactionState.CLOSED.value:
                    metrics['closed_transactions'] += 1
                    metrics['total_bought'] += float(transaction.total_cost)
                    metrics['total_sold'] += float(transaction.total_revenue)
                    metrics['total_gain_loss'] += float(transaction.gain_loss)
                    
                    # Calculate gain/loss percent
                    gain_percent = transaction.profit_loss_percent
                    total_gain_loss_percent += gain_percent
                    
                    # Track best and worst transactions
                    if gain_percent > best_gain_percent:
                        best_gain_percent = gain_percent
                        best_transaction = transaction
                    if gain_percent < worst_gain_percent:
                        worst_gain_percent = gain_percent
                        worst_transaction = transaction
                    
                    # Calculate duration
                    if transaction.duration_days is not None:
                        total_duration_days += transaction.duration_days
                    
                    closed_count += 1
                elif transaction.state == TransactionState.CANCELLED.value:
                    metrics['cancelled_transactions'] += 1
            
            # Calculate averages
            if closed_count > 0:
                metrics['average_gain_loss_percent'] = total_gain_loss_percent / closed_count
                metrics['average_transaction_duration_days'] = total_duration_days / closed_count
                
                # Set best and worst transactions
                if best_transaction:
                    metrics['best_transaction'] = {
                        'id': best_transaction.id,
                        'stock_symbol': best_transaction.stock_symbol,
                        'gain_percent': best_gain_percent,
                        'gain_amount': float(best_transaction.gain_loss)
                    }
                
                if worst_transaction:
                    metrics['worst_transaction'] = {
                        'id': worst_transaction.id,
                        'stock_symbol': worst_transaction.stock_symbol,
                        'gain_percent': worst_gain_percent,
                        'gain_amount': float(worst_transaction.gain_loss)
                    }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating transaction metrics: {str(e)}")
            raise BusinessLogicError(f"Could not calculate transaction metrics: {str(e)}")
