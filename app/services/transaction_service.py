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
from sqlalchemy import and_

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
        return session.query(TradingTransaction).get(transaction_id)
    
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
            query = session.query(TradingTransaction).filter(TradingTransaction.service_id == service_id)
            
            if state:
                if not TransactionState.is_valid(state):
                    raise ValueError(f"Invalid transaction state: {state}")
                query = query.filter(TradingTransaction.state == state)
                
            return query.order_by(TradingTransaction.purchase_date.desc()).all()
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
        query = session.query(TradingTransaction).filter(TradingTransaction.state == TransactionState.OPEN.value)
        
        if service_id is not None:
            query = query.filter(TradingTransaction.service_id == service_id)
            
        return query.order_by(TradingTransaction.purchase_date).all()
    
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
    
    @staticmethod
    def duration_days(transaction: TradingTransaction) -> Optional[int]:
        """
        Get the duration of the transaction in days.
        
        Args:
            transaction: TradingTransaction instance
            
        Returns:
            Number of days the transaction has been open, or None if no purchase date
        """
        if not transaction.purchase_date:
            return None
            
        end_date = transaction.sale_date if transaction.sale_date else get_current_datetime()
        return (end_date - transaction.purchase_date).days
    
    @staticmethod
    def total_cost(transaction: TradingTransaction) -> Decimal:
        """
        Calculate the total cost of a transaction's purchase.
        
        Args:
            transaction: TradingTransaction instance
            
        Returns:
            Total cost of the purchase
        """
        if transaction.purchase_price and transaction.shares:
            return transaction.purchase_price * transaction.shares
        return Decimal('0')
    
    @staticmethod
    def total_revenue(transaction: TradingTransaction) -> Decimal:
        """
        Calculate the total revenue from a transaction's sale.
        
        Args:
            transaction: TradingTransaction instance
            
        Returns:
            Total revenue from the sale, or 0 if not sold
        """
        if transaction.sale_price and transaction.shares:
            return transaction.sale_price * transaction.shares
        return Decimal('0')
    
    @staticmethod
    def profit_loss_percent(transaction: TradingTransaction) -> float:
        """
        Calculate the profit/loss as a percentage.
        
        Args:
            transaction: TradingTransaction instance
            
        Returns:
            Percentage profit or loss, or 0 if not applicable
        """
        if transaction.purchase_price and transaction.sale_price and transaction.purchase_price > 0:
            return float(((transaction.sale_price - transaction.purchase_price) / transaction.purchase_price) * 100)
        return 0.0
    
    @staticmethod
    def transaction_to_dict(transaction: TradingTransaction) -> Dict[str, Any]:
        """
        Convert a transaction to a dictionary for API responses.
        
        Args:
            transaction: TradingTransaction instance
            
        Returns:
            Dictionary representation of the transaction
        """
        return {
            'id': transaction.id,
            'service_id': transaction.service_id,
            'stock_id': transaction.stock_id,
            'stock_symbol': transaction.stock_symbol,
            'shares': float(transaction.shares) if transaction.shares else None,
            'state': transaction.state,
            'purchase_price': float(transaction.purchase_price) if transaction.purchase_price else None,
            'sale_price': float(transaction.sale_price) if transaction.sale_price else None,
            'gain_loss': float(transaction.gain_loss) if transaction.gain_loss else None,
            'purchase_date': transaction.purchase_date.isoformat() if transaction.purchase_date else None,
            'sale_date': transaction.sale_date.isoformat() if transaction.sale_date else None,
            'notes': transaction.notes,
            'created_at': transaction.created_at.isoformat() if transaction.created_at else None,
            'updated_at': transaction.updated_at.isoformat() if transaction.updated_at else None,
            'is_complete': transaction.is_complete,
            'is_profitable': transaction.is_profitable,
            'duration_days': TransactionService.duration_days(transaction),
            'total_cost': float(TransactionService.total_cost(transaction)) if TransactionService.total_cost(transaction) else 0.0,
            'total_revenue': float(TransactionService.total_revenue(transaction)) if TransactionService.total_revenue(transaction) else 0.0,
            'profit_loss_percent': TransactionService.profit_loss_percent(transaction)
        }
    
    @staticmethod
    def transaction_from_dict(data: Dict[str, Any]) -> TradingTransaction:
        """
        Create a new transaction instance from a dictionary.
        
        Args:
            data: Dictionary with transaction attributes
            
        Returns:
            New TradingTransaction instance
        """
        return TradingTransaction(**{k: v for k, v in data.items() if k in [
            'service_id', 'stock_id', 'stock_symbol', 'shares', 'state',
            'purchase_price', 'sale_price', 'gain_loss', 'purchase_date',
            'sale_date', 'notes'
        ]})
    
    @staticmethod
    def update_transaction_from_dict(transaction: TradingTransaction, data: Dict[str, Any]) -> bool:
        """
        Update transaction attributes from a dictionary.
        
        Args:
            transaction: TradingTransaction instance to update
            data: Dictionary with attribute key/value pairs
            
        Returns:
            True if any fields were updated, False otherwise
        """
        updated = False
        for key, value in data.items():
            if hasattr(transaction, key) and key not in ['id', 'created_at', 'updated_at']:
                if getattr(transaction, key) != value:
                    setattr(transaction, key, value)
                    updated = True
        
        # Recalculate gain/loss if needed
        if ('sale_price' in data) and transaction.sale_price and transaction.purchase_price:
            transaction.gain_loss = transaction.calculate_gain_loss()
            updated = True
            
        return updated
    
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
            
            # Update service balance
            service.current_balance -= Decimal(str(total_cost))
            service.updated_at = get_current_datetime()
            
            session.commit()
            
            # Prepare response data
            transaction_data = transaction_schema.dump(transaction)
            service_data = service_schema.dump(service)
            
            # Emit WebSocket events
            EventService.emit_transaction_update(
                action='created',
                transaction_data=transaction_data,
                service_id=service_id
            )
            
            EventService.emit_service_update(
                action='balance_updated',
                service_data=service_data,
                service_id=service_id
            )
            
            return transaction
        except Exception as e:
            logger.error(f"Error creating buy transaction: {str(e)}")
            session.rollback()
            if isinstance(e, (ValidationError, ResourceNotFoundError, BusinessLogicError)):
                raise
            raise ValidationError(f"Could not create buy transaction: {str(e)}")
    
    @staticmethod
    def complete_transaction(session: Session, transaction_id: int, sale_price: Decimal) -> TradingTransaction:
        """
        Complete (sell) an open transaction.
        
        Args:
            session: Database session
            transaction_id: Transaction ID to complete
            sale_price: Sale price per share
            
        Returns:
            Updated transaction instance
            
        Raises:
            ValidationError: If the sale price is invalid
            ResourceNotFoundError: If the transaction doesn't exist
            BusinessLogicError: If the transaction can't be completed (already completed/cancelled)
        """
        from app.services.events import EventService
        
        try:
            # Validate sale price
            if sale_price <= 0:
                raise ValidationError("Sale price must be greater than zero")
            
            # Get transaction
            transaction = TransactionService.get_or_404(session, transaction_id)
            
            # Check if transaction can be completed
            if transaction.state != TransactionState.OPEN.value:
                raise BusinessLogicError(f"Transaction cannot be completed because it is not open (current state: {transaction.state})")
            
            # Get associated service
            service = session.query(TradingService).filter_by(id=transaction.service_id).first()
            if not service:
                raise ResourceNotFoundError(f"Trading service with ID {transaction.service_id} not found")
            
            # Update transaction
            transaction.sale_price = sale_price
            transaction.sale_date = get_current_datetime()
            transaction.state = TransactionState.CLOSED.value
            
            # Calculate gain/loss
            transaction.gain_loss = transaction.calculate_gain_loss()
            
            # Update service balance
            sale_amount = Decimal(str(sale_price)) * Decimal(str(transaction.shares))
            service.current_balance += sale_amount
            service.updated_at = get_current_datetime()
            
            # Update profit/loss history
            if transaction.gain_loss > 0:
                service.total_profit += transaction.gain_loss
            else:
                service.total_loss += abs(transaction.gain_loss)
            
            session.commit()
            
            # Prepare response data
            transaction_data = transaction_schema.dump(transaction)
            service_data = service_schema.dump(service)
            
            # Emit WebSocket events
            EventService.emit_transaction_update(
                action='completed',
                transaction_data=transaction_data,
                service_id=service.id
            )
            
            EventService.emit_service_update(
                action='balance_updated',
                service_data=service_data,
                service_id=service.id
            )
            
            return transaction
        except Exception as e:
            logger.error(f"Error completing transaction: {str(e)}")
            session.rollback()
            if isinstance(e, (ValidationError, ResourceNotFoundError, BusinessLogicError)):
                raise
            raise ValidationError(f"Could not complete transaction: {str(e)}")
    
    @staticmethod
    def cancel_transaction(session: Session, transaction_id: int, reason: str = "User cancelled") -> TradingTransaction:
        """
        Cancel an open transaction.
        
        Args:
            session: Database session
            transaction_id: Transaction ID to cancel
            reason: Reason for cancellation
            
        Returns:
            Updated transaction instance
            
        Raises:
            ResourceNotFoundError: If the transaction doesn't exist
            BusinessLogicError: If the transaction can't be cancelled (already completed/cancelled)
        """
        from app.services.events import EventService
        
        try:
            # Get transaction
            transaction = TransactionService.get_or_404(session, transaction_id)
            
            # Check if transaction can be cancelled
            if not transaction.can_be_cancelled:
                raise BusinessLogicError(f"Transaction cannot be cancelled because it is in state: {transaction.state}")
            
            # Get associated service
            service = session.query(TradingService).filter_by(id=transaction.service_id).first()
            if not service:
                raise ResourceNotFoundError(f"Trading service with ID {transaction.service_id} not found")
            
            # Update transaction
            transaction.state = TransactionState.CANCELLED.value
            transaction.notes = f"{transaction.notes or ''}\nCancelled: {reason}".strip()
            transaction.updated_at = get_current_datetime()
            
            # Refund service balance
            refund_amount = Decimal(str(transaction.purchase_price)) * Decimal(str(transaction.shares))
            service.current_balance += refund_amount
            service.updated_at = get_current_datetime()
            
            session.commit()
            
            # Prepare response data
            transaction_data = transaction_schema.dump(transaction)
            service_data = service_schema.dump(service)
            
            # Emit WebSocket events
            EventService.emit_transaction_update(
                action='cancelled',
                transaction_data=transaction_data,
                service_id=service.id
            )
            
            EventService.emit_service_update(
                action='balance_updated',
                service_data=service_data,
                service_id=service.id
            )
            
            return transaction
        except Exception as e:
            logger.error(f"Error cancelling transaction: {str(e)}")
            session.rollback()
            if isinstance(e, (ResourceNotFoundError, BusinessLogicError)):
                raise
            raise BusinessLogicError(f"Could not cancel transaction: {str(e)}")
    
    @staticmethod
    def delete_transaction(session: Session, transaction_id: int) -> bool:
        """
        Delete a transaction.
        
        Args:
            session: Database session
            transaction_id: Transaction ID to delete
            
        Returns:
            True if successful
            
        Raises:
            ResourceNotFoundError: If the transaction doesn't exist
            BusinessLogicError: If the transaction can't be deleted (is open)
        """
        from app.services.events import EventService
        
        try:
            # Get transaction
            transaction = TransactionService.get_or_404(session, transaction_id)
            
            # Don't allow deletion of open transactions
            if transaction.state == TransactionState.OPEN.value:
                raise BusinessLogicError("Cannot delete an open transaction. Cancel it first.")
            
            # Store service ID and transaction ID for event emission
            service_id = transaction.service_id
            transaction_id = transaction.id
            
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
        except Exception as e:
            logger.error(f"Error deleting transaction: {str(e)}")
            session.rollback()
            if isinstance(e, (ResourceNotFoundError, BusinessLogicError)):
                raise
            raise BusinessLogicError(f"Could not delete transaction: {str(e)}")
    
    @staticmethod
    def update_transaction_notes(session: Session, transaction_id: int, notes: str) -> TradingTransaction:
        """
        Update transaction notes.
        
        Args:
            session: Database session
            transaction_id: Transaction ID
            notes: New notes text
            
        Returns:
            Updated transaction instance
            
        Raises:
            ResourceNotFoundError: If the transaction doesn't exist
        """
        from app.services.events import EventService
        
        try:
            # Get transaction
            transaction = TransactionService.get_or_404(session, transaction_id)
            
            # Update notes
            transaction.notes = notes
            transaction.updated_at = get_current_datetime()
            
            session.commit()
            
            # Prepare response data
            transaction_data = transaction_schema.dump(transaction)
            
            # Emit WebSocket event
            EventService.emit_transaction_update(
                action='updated',
                transaction_data=transaction_data,
                service_id=transaction.service_id
            )
            
            return transaction
        except Exception as e:
            logger.error(f"Error updating transaction notes: {str(e)}")
            session.rollback()
            if isinstance(e, ResourceNotFoundError):
                raise
            raise ValidationError(f"Could not update transaction notes: {str(e)}")
    
    @staticmethod
    def calculate_transaction_metrics(session: Session, service_id: int) -> Dict[str, Any]:
        """
        Calculate metrics for a service's transactions.
        
        Args:
            session: Database session
            service_id: Service ID
            
        Returns:
            Dictionary of transaction metrics
        """
        from app.services.events import EventService
        
        metrics = {
            'total_transactions': 0,
            'open_transactions': 0,
            'closed_transactions': 0,
            'cancelled_transactions': 0,
            'total_profit': 0.0,
            'total_loss': 0.0,
            'net_gain_loss': 0.0,
            'average_profit_per_transaction': 0.0,
            'average_loss_per_transaction': 0.0,
            'profitable_transactions': 0,
            'unprofitable_transactions': 0,
            'win_rate': 0.0
        }
        
        # Get all transactions for the service
        transactions = TransactionService.get_by_service(session, service_id)
        
        if not transactions:
            return metrics
            
        # Count transactions by state
        for t in transactions:
            if t.state == TransactionState.OPEN.value:
                metrics['open_transactions'] += 1
            elif t.state == TransactionState.CLOSED.value:
                metrics['closed_transactions'] += 1
                
                if t.is_profitable:
                    metrics['profitable_transactions'] += 1
                    metrics['total_profit'] += float(t.gain_loss or 0)
                else:
                    metrics['unprofitable_transactions'] += 1
                    metrics['total_loss'] += abs(float(t.gain_loss or 0))
            elif t.state == TransactionState.CANCELLED.value:
                metrics['cancelled_transactions'] += 1
                
        metrics['total_transactions'] = len(transactions)
        metrics['net_gain_loss'] = metrics['total_profit'] - metrics['total_loss']
        
        # Calculate averages and rates
        if metrics['profitable_transactions'] > 0:
            metrics['average_profit_per_transaction'] = metrics['total_profit'] / metrics['profitable_transactions']
            
        if metrics['unprofitable_transactions'] > 0:
            metrics['average_loss_per_transaction'] = metrics['total_loss'] / metrics['unprofitable_transactions']
            
        if metrics['closed_transactions'] > 0:
            metrics['win_rate'] = (metrics['profitable_transactions'] / metrics['closed_transactions']) * 100
            
        # Emit metrics update event
        EventService.emit_metrics_update(
            metric_type='transaction_stats',
            metric_data=metrics,
            resource_id=service_id,
            resource_type='service'
        )
            
        return metrics
