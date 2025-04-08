"""Transaction service for managing TradingTransaction model operations.

This service encapsulates all database interactions for the TradingTransaction model,
providing a clean API for trading transaction management operations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.orm import Session

from app.api.schemas.trading_service import service_schema
from app.api.schemas.trading_transaction import transaction_schema
from app.models.enums import TransactionState
from app.models.stock import Stock
from app.models.trading_service import TradingService
from app.models.trading_transaction import TradingTransaction
from app.services.events import EventService
from app.utils.current_datetime import get_current_datetime
from app.utils.errors import (
    AuthorizationError,
    BusinessLogicError,
    ResourceNotFoundError,
    ValidationError,
)

# Set up logging
logger: logging.Logger = logging.getLogger(__name__)


class TransactionService:
    """Service for TradingTransaction model operations."""

    # Read operations
    @staticmethod
    def get_by_id(session: Session, transaction_id: int) -> TradingTransaction | None:
        """Get a transaction by ID.

        Args:
            session: Database session
            transaction_id: Transaction ID to retrieve

        Returns:
            TradingTransaction instance if found, None otherwise

        """
        return session.execute(
            select(TradingTransaction).where(TradingTransaction.id == transaction_id),
        ).scalar_one_or_none()

    @staticmethod
    def get_or_404(session: Session, transaction_id: int) -> TradingTransaction:
        """Get a transaction by ID or raise ResourceNotFoundError.

        Args:
            session: Database session
            transaction_id: Transaction ID to retrieve

        Returns:
            TradingTransaction instance

        Raises:
            ResourceNotFoundError: If transaction not found

        """
        transaction: TradingTransaction | None = TransactionService.get_by_id(
            session,
            transaction_id,
        )
        if not transaction:
            TransactionService._raise_resource_not_found(
                transaction_id,
                ValidationError.TRANSACTION_NOT_FOUND.format(transaction_id),
            )
        return transaction

    @staticmethod
    def get_by_service(
        session: Session,
        service_id: int,
        state: str | None = None,
    ) -> list[TradingTransaction]:
        """Get transactions for a service, optionally filtered by state.

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
            transactions: list[TradingTransaction] = (
                session.execute(
                    select(TradingTransaction).where(
                        TradingTransaction.service_id == service_id,
                    ),
                )
                .scalars()
                .all()
            )

            if state and not TransactionState.is_valid(state):
                TransactionService._raise_validation_error(
                    ValidationError.INVALID_STATE.format(state),
                )

            if state:
                transactions = [t for t in transactions if t.state == state]

            return sorted(transactions, key=lambda x: x.purchase_date, reverse=True)
        except ValueError as e:
            TransactionService._raise_validation_error(str(e))

    @staticmethod
    def get_open_transactions(
        session: Session,
        service_id: int | None = None,
    ) -> list[TradingTransaction]:
        """Get all open transactions, optionally filtered by service ID.

        Args:
            session: Database session
            service_id: Optional service ID filter

        Returns:
            List of open transactions

        """
        transactions: list[TradingTransaction] = (
            session.execute(
                select(TradingTransaction).where(
                    TradingTransaction.state == TransactionState.OPEN.value,
                ),
            )
            .scalars()
            .all()
        )

        if service_id is not None:
            transactions = [t for t in transactions if t.service_id == service_id]

        return sorted(transactions, key=lambda x: x.purchase_date, reverse=True)

    @staticmethod
    def check_ownership(session: Session, transaction_id: int, user_id: int) -> bool:
        """Check if a user owns a transaction (through service ownership).

        Args:
            session: Database session
            transaction_id: Transaction ID
            user_id: User ID

        Returns:
            True if the user owns the service that owns the transaction, False otherwise

        """
        transaction: TradingTransaction | None = TransactionService.get_by_id(
            session,
            transaction_id,
        )
        if not transaction:
            return False

        service: TradingService | None = session.execute(
            select(TradingService).where(
                TradingService.id == transaction.service_id,
                TradingService.user_id == user_id,
            ),
        ).scalar_one_or_none()
        return service is not None

    @staticmethod
    def verify_ownership(
        session: Session,
        transaction_id: int,
        user_id: int,
    ) -> TradingTransaction:
        """Verify a user owns a transaction (through service ownership).

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
        transaction: TradingTransaction = TransactionService.get_or_404(
            session,
            transaction_id,
        )

        service: TradingService | None = session.execute(
            select(TradingService).where(
                TradingService.id == transaction.service_id,
                TradingService.user_id == user_id,
            ),
        ).scalar_one_or_none()
        if not service:
            TransactionService._raise_authorization_error(
                ValidationError.USER_NOT_OWNER.format(user_id, transaction_id),
            )

        return transaction

    @staticmethod
    def duration_days(transaction: TradingTransaction) -> int | None:
        """Get the duration of the transaction in days.

        Args:
            transaction: TradingTransaction instance

        Returns:
            Number of days the transaction has been open, or None if no purchase date

        """
        if transaction.purchase_date is None:
            return None

        end_date: datetime | None = (
            transaction.sale_date
            if transaction.sale_date is not None
            else get_current_datetime()
        )
        return (end_date - transaction.purchase_date).days

    @staticmethod
    def total_cost(transaction: TradingTransaction) -> float:
        """Calculate the total cost of a transaction's purchase.

        Args:
            transaction: TradingTransaction instance

        Returns:
            Total cost of the purchase

        """
        if transaction.purchase_price is not None and transaction.shares is not None:
            return transaction.purchase_price * transaction.shares
        return 0.0

    @staticmethod
    def total_revenue(transaction: TradingTransaction) -> float:
        """Calculate the total revenue from a transaction's sale.

        Args:
            transaction: TradingTransaction instance

        Returns:
            Total revenue from the sale, or 0 if not sold

        """
        if transaction.sale_price is not None and transaction.shares is not None:
            return transaction.sale_price * transaction.shares
        return 0.0

    @staticmethod
    def profit_loss_percent(transaction: TradingTransaction) -> float:
        """Calculate the profit/loss as a percentage.

        Args:
            transaction: TradingTransaction instance

        Returns:
            Percentage profit or loss, or 0 if not applicable

        """
        if (
            transaction.purchase_price is not None
            and transaction.sale_price is not None
            and transaction.purchase_price > 0
        ):
            return float(
                (transaction.sale_price - transaction.purchase_price)
                / transaction.purchase_price
                * 100,
            )
        return 0.0

    @staticmethod
    def transaction_to_dict(transaction: TradingTransaction) -> dict[str, any]:
        """Convert a transaction to a dictionary for API responses.

        Args:
            transaction: TradingTransaction instance

        Returns:
            Dictionary representation of the transaction

        """
        return {
            "id": transaction.id,
            "service_id": transaction.service_id,
            "stock_id": (
                transaction.stock_id if transaction.stock_id is not None else None
            ),
            "stock_symbol": transaction.stock_symbol,
            "shares": (
                float(str(transaction.shares))
                if transaction.shares is not None
                else None
            ),
            "state": transaction.state,
            "purchase_price": (
                float(str(transaction.purchase_price))
                if transaction.purchase_price is not None
                else None
            ),
            "sale_price": (
                float(str(transaction.sale_price))
                if transaction.sale_price is not None
                else None
            ),
            "gain_loss": (
                float(str(transaction.gain_loss))
                if transaction.gain_loss is not None
                else None
            ),
            "purchase_date": (
                transaction.purchase_date.isoformat()
                if transaction.purchase_date is not None
                else None
            ),
            "sale_date": (
                transaction.sale_date.isoformat()
                if transaction.sale_date is not None
                else None
            ),
            "notes": transaction.notes,
            "created_at": (
                transaction.created_at.isoformat()
                if transaction.created_at is not None
                else None
            ),
            "updated_at": (
                transaction.updated_at.isoformat()
                if transaction.updated_at is not None
                else None
            ),
            "is_complete": (
                transaction.is_complete
                if hasattr(transaction, "is_complete")
                else False
            ),
            "is_profitable": (
                transaction.is_profitable
                if hasattr(transaction, "is_profitable")
                else False
            ),
            "duration_days": TransactionService.duration_days(transaction),
            "total_cost": (
                float(str(TransactionService.total_cost(transaction)))
                if TransactionService.total_cost(transaction) is not None
                else 0.0
            ),
            "total_revenue": (
                float(str(TransactionService.total_revenue(transaction)))
                if TransactionService.total_revenue(transaction) is not None
                else 0.0
            ),
            "profit_loss_percent": TransactionService.profit_loss_percent(transaction),
        }

    @staticmethod
    def transaction_from_dict(data: dict[str, any]) -> TradingTransaction:
        """Create a new transaction instance from a dictionary.

        Args:
            data: Dictionary with transaction attributes

        Returns:
            New TradingTransaction instance

        """
        data_dict: dict[str, any] = data if isinstance(data, dict) else {}

        return TradingTransaction(
            **{
                k: v
                for k, v in data_dict.items()
                if k
                in [
                    "service_id",
                    "stock_id",
                    "stock_symbol",
                    "shares",
                    "state",
                    "purchase_price",
                    "sale_price",
                    "gain_loss",
                    "purchase_date",
                    "sale_date",
                    "notes",
                ]
            },
        )

    @staticmethod
    def update_transaction_from_dict(
        transaction: TradingTransaction,
        data: dict[str, any],
    ) -> bool:
        """Update transaction attributes from a dictionary.

        Args:
            transaction: TradingTransaction instance to update
            data: Dictionary with attribute key/value pairs

        Returns:
            True if any fields were updated, False otherwise

        """
        data_dict: dict[str, any] = data if isinstance(data, dict) else {}

        updated = False
        for key, value in data_dict.items():
            if (
                transaction.get(key)
                and key not in ["id", "created_at", "updated_at"]
                and transaction.get(key) != value
            ):
                transaction[key] = value
                updated = True

        # Recalculate gain/loss if needed
        if (
            "sale_price" in data_dict
            and transaction.sale_price is not None
            and transaction.purchase_price is not None
        ):
            transaction.gain_loss = transaction.calculated_gain_loss
            updated = True

        return updated

    # Write operations
    @staticmethod
    def create_buy_transaction(
        session: Session,
        service_id: int,
        stock_symbol: str,
        shares: float,
        purchase_price: float,
    ) -> TradingTransaction:
        """Create a new buy transaction for a trading service.

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
            BusinessLogicError: If the service doesn't have enough funds or is not in
            BUY mode

        """
        try:
            # Validate input
            if shares <= 0:
                TransactionService._raise_validation_error(
                    ValidationError.SHARES_POSITIVE,
                )

            if purchase_price <= 0:
                TransactionService._raise_validation_error(
                    ValidationError.PRICE_POSITIVE,
                )

            # Get the service
            service: TradingService | None = session.execute(
                select(TradingService).where(TradingService.id == service_id),
            ).scalar_one_or_none()
            if not service:
                TransactionService._raise_resource_not_found(
                    service_id,
                    ValidationError.SERVICE_NOT_FOUND.format(service_id),
                )

            # Check if service can buy
            total_cost: float = shares * purchase_price
            current_balance: float = service.current_balance
            if total_cost > current_balance:
                TransactionService._raise_business_error(
                    ValidationError.INSUFFICIENT_FUNDS.format(
                        total_cost,
                        current_balance,
                    ),
                )

            # Check if service is in buy mode
            if not service.can_buy:
                TransactionService._raise_business_error(
                    ValidationError.SERVICE_NOT_BUYING.format(
                        service.state,
                        service.mode,
                    ),
                )

            # Find stock if it exists
            stock: Stock | None = session.execute(
                select(Stock).where(Stock.symbol == stock_symbol.upper()),
            ).scalar_one_or_none()
            stock_id: int | None = stock.id if stock else None

            # Create transaction
            transaction_data: dict[str, any] = {
                "service_id": service_id,
                "stock_id": stock_id,
                "stock_symbol": stock_symbol.upper(),
                "shares": shares,
                "purchase_price": purchase_price,
                "state": TransactionState.OPEN.value,
                "purchase_date": get_current_datetime(),
            }

            transaction: TradingTransaction = TradingTransaction.from_dict(
                transaction_data,
            )
            session.add(transaction)

            # Update service balance
            service.current_balance = float(current_balance) - total_cost
            service.updated_at = get_current_datetime()

            session.commit()

            # Prepare response data
            transaction_data: dict[str, any] = transaction_schema.dump(transaction)
            transaction_data_dict: dict[str, any] = (
                transaction_data
                if isinstance(transaction_data, dict)
                else transaction_data[0]
            )

            service_data: dict[str, any] = service_schema.dump(service)
            service_data_dict: dict[str, any] = (
                service_data if isinstance(service_data, dict) else service_data[0]
            )

            # Emit WebSocket events
            EventService.emit_transaction_update(
                action="created",
                transaction_data=transaction_data_dict,
                service_id=service_id,
            )

            EventService.emit_service_update(
                action="balance_updated",
                service_data=service_data_dict,
                service_id=service_id,
            )

        except Exception as e:
            logger.exception("Error creating buy transaction")
            session.rollback()
            TransactionService._reraise_or_convert_error(
                e,
                (ValidationError, ResourceNotFoundError, BusinessLogicError),
                ValidationError,
                ValidationError.CREATE_BUY_ERROR.format(str(e)),
            )
        return transaction

    @staticmethod
    def complete_transaction(
        session: Session,
        transaction_id: int,
        sale_price: float,
    ) -> TradingTransaction:
        """Complete (sell) an open transaction.

        Args:
            session: Database session
            transaction_id: Transaction ID to complete
            sale_price: Sale price per share

        Returns:
            Updated transaction instance

        Raises:
            ValidationError: If the sale price is invalid
            ResourceNotFoundError: If the transaction doesn't exist
            BusinessLogicError: If the transaction can't be completed (already
            completed/cancelled)

        """
        try:
            # Validate sale price
            if sale_price <= 0:
                TransactionService._raise_validation_error(
                    ValidationError.PRICE_POSITIVE,
                )

            # Get transaction
            transaction: TradingTransaction = TransactionService.get_or_404(
                session,
                transaction_id,
            )

            # Check if transaction can be completed
            if transaction.state != TransactionState.OPEN.value:
                TransactionService._raise_business_error(
                    ValidationError.TRANSACTION_NOT_OPEN.format(transaction.state),
                )

            # Get associated service
            service: TradingService | None = session.execute(
                select(TradingService).where(
                    TradingService.id == transaction.service_id,
                ),
            ).scalar_one_or_none()
            if not service:
                TransactionService._raise_resource_not_found(
                    transaction.service_id,
                    ValidationError.SERVICE_NOT_FOUND.format(transaction.service_id),
                )

            # Update transaction
            transaction.sale_price = sale_price
            transaction.sale_date = get_current_datetime()
            transaction.state = TransactionState.CLOSED.value

            # Calculate gain/loss
            transaction.gain_loss = transaction.calculated_gain_loss

            # Update service balance
            sale_amount: float = sale_price * float(transaction.shares)
            service.current_balance = float(service.current_balance) + sale_amount
            service.updated_at = get_current_datetime()

            # Update total gain/loss
            gain_loss_amount = float(transaction.calculated_gain_loss)
            service.total_gain_loss = float(service.total_gain_loss) + gain_loss_amount

            session.commit()

            # Prepare response data
            transaction_data: dict[str, any] = transaction_schema.dump(transaction)
            transaction_data_dict: dict[str, any] = (
                transaction_data
                if isinstance(transaction_data, dict)
                else transaction_data[0]
            )

            service_data: dict[str, any] = service_schema.dump(service)
            service_data_dict: dict[str, any] = (
                service_data if isinstance(service_data, dict) else service_data[0]
            )

            # Store service ID for event emission
            service_id_val: int = service.id

            # Emit WebSocket events
            EventService.emit_transaction_update(
                action="completed",
                transaction_data=transaction_data_dict,
                service_id=service_id_val,
            )

            EventService.emit_service_update(
                action="balance_updated",
                service_data=service_data_dict,
                service_id=service_id_val,
            )

        except Exception as e:
            logger.exception("Error completing transaction")
            session.rollback()
            TransactionService._reraise_or_convert_error(
                e,
                (ValidationError, ResourceNotFoundError, BusinessLogicError),
                ValidationError,
                ValidationError.COMPLETE_ERROR.format(str(e)),
            )
        return transaction

    @staticmethod
    def cancel_transaction(
        session: Session,
        transaction_id: int,
        reason: str = "User cancelled",
    ) -> TradingTransaction:
        """Cancel an open transaction.

        Args:
            session: Database session
            transaction_id: Transaction ID to cancel
            reason: Reason for cancellation

        Returns:
            Updated transaction instance

        Raises:
            ResourceNotFoundError: If the transaction doesn't exist
            BusinessLogicError: If the transaction can't be cancelled (already
            completed/cancelled)

        """
        try:
            # Get transaction
            transaction: TradingTransaction = TransactionService.get_or_404(
                session,
                transaction_id,
            )

            # Check if transaction can be cancelled - avoid direct boolean comparison
            if not transaction.can_be_cancelled:
                TransactionService._raise_business_error(
                    ValidationError.TRANSACTION_NOT_CANCELLABLE.format(
                        transaction.state,
                    ),
                )

            # Get associated service
            service: TradingService | None = session.execute(
                select(TradingService).where(
                    TradingService.id == transaction.service_id,
                ),
            ).scalar_one_or_none()
            if not service:
                TransactionService._raise_resource_not_found(
                    transaction.service_id,
                    ValidationError.SERVICE_NOT_FOUND.format(transaction.service_id),
                )

            # Update transaction
            transaction.state = TransactionState.CANCELLED.value
            transaction.notes = (
                f"{str(transaction.notes) or ''}\nCancelled: {reason}".strip()
            )
            transaction.updated_at = get_current_datetime()

            # Refund service balance
            refund_amount: float = transaction.purchase_price * transaction.shares
            service.current_balance = float(service.current_balance) + float(
                refund_amount,
            )
            service.updated_at = get_current_datetime()

            session.commit()

            # Prepare response data
            transaction_data: dict[str, any] = transaction_schema.dump(transaction)
            transaction_data_dict: dict[str, any] = (
                transaction_data
                if isinstance(transaction_data, dict)
                else transaction_data[0]
            )

            service_data: dict[str, any] = service_schema.dump(service)
            service_data_dict: dict[str, any] = (
                service_data if isinstance(service_data, dict) else service_data[0]
            )

            # Emit WebSocket events
            EventService.emit_transaction_update(
                action="cancelled",
                transaction_data=transaction_data_dict,
                service_id=service.id,
            )

            EventService.emit_service_update(
                action="balance_updated",
                service_data=service_data_dict,
                service_id=service.id,
            )

        except Exception as e:
            logger.exception("Error cancelling transaction")
            session.rollback()
            TransactionService._reraise_or_convert_error(
                e,
                (ResourceNotFoundError, BusinessLogicError),
                BusinessLogicError,
                ValidationError.CANCEL_ERROR.format(str(e)),
            )
        return transaction

    @staticmethod
    def delete_transaction(session: Session, transaction_id: int) -> bool:
        """Delete a transaction.

        Args:
            session: Database session
            transaction_id: Transaction ID to delete

        Returns:
            True if successful

        Raises:
            ResourceNotFoundError: If the transaction doesn't exist
            BusinessLogicError: If the transaction can't be deleted (is open)

        """
        try:
            # Get transaction
            transaction: TradingTransaction = TransactionService.get_or_404(
                session,
                transaction_id,
            )

            # Don't allow deletion of open transactions
            if transaction.state == TransactionState.OPEN.value:
                TransactionService._raise_business_error(
                    ValidationError.CANNOT_DELETE_OPEN,
                )

            # Store service ID and transaction ID for event emission
            service_id: int = transaction.service_id
            transaction_id_val: int = transaction.id

            # Delete transaction
            session.delete(transaction)
            session.commit()

            # Emit WebSocket event
            EventService.emit_transaction_update(
                action="deleted",
                transaction_data={"id": transaction_id_val},
                service_id=service_id,
            )

        except Exception as e:
            logger.exception("Error deleting transaction")
            session.rollback()
            TransactionService._reraise_or_convert_error(
                e,
                (ResourceNotFoundError, BusinessLogicError),
                BusinessLogicError,
                ValidationError.DELETE_ERROR.format(str(e)),
            )
        return True

    @staticmethod
    def update_transaction_notes(
        session: Session,
        transaction_id: int,
        notes: str,
    ) -> TradingTransaction:
        """Update transaction notes.

        Args:
            session: Database session
            transaction_id: Transaction ID
            notes: New notes text

        Returns:
            Updated transaction instance

        Raises:
            ResourceNotFoundError: If the transaction doesn't exist

        """
        try:
            # Get transaction
            transaction: TradingTransaction = TransactionService.get_or_404(
                session,
                transaction_id,
            )

            # Update notes
            transaction.notes = notes
            transaction.updated_at = get_current_datetime()

            session.commit()

            # Prepare response data
            transaction_data: dict[str, any] = transaction_schema.dump(transaction)
            transaction_data_dict: dict[str, any] = (
                transaction_data
                if isinstance(transaction_data, dict)
                else transaction_data[0]
            )

            # Emit WebSocket event
            EventService.emit_transaction_update(
                action="updated",
                transaction_data=transaction_data_dict,
                service_id=transaction.service_id,
            )

        except Exception as e:
            logger.exception("Error updating transaction notes")
            session.rollback()
            TransactionService._reraise_or_convert_error(
                e,
                (ResourceNotFoundError,),
                ValidationError,
                ValidationError.UPDATE_NOTES_ERROR.format(str(e)),
            )
        return transaction

    @staticmethod
    def calculate_transaction_metrics(
        session: Session,
        service_id: int,
    ) -> dict[str, any]:
        """Calculate metrics for a service's transactions.

        Args:
            session: Database session
            service_id: Service ID

        Returns:
            Dictionary of transaction metrics

        """
        metrics: dict[str, any] = {
            "total_transactions": 0,
            "open_transactions": 0,
            "closed_transactions": 0,
            "cancelled_transactions": 0,
            "total_profit": 0.0,
            "total_loss": 0.0,
            "net_gain_loss": 0.0,
            "average_profit_per_transaction": 0.0,
            "average_loss_per_transaction": 0.0,
            "profitable_transactions": 0,
            "unprofitable_transactions": 0,
            "win_rate": 0.0,
        }

        # Get all transactions for the service
        transactions: list[TradingTransaction] = TransactionService.get_by_service(
            session,
            service_id,
        )

        if not transactions:
            return metrics

        # Count transactions by state
        for t in transactions:
            if t.state == TransactionState.OPEN.value:
                metrics["open_transactions"] += 1
            elif t.state == TransactionState.CLOSED.value:
                metrics["closed_transactions"] += 1
                if t.is_profitable:
                    metrics["profitable_transactions"] += 1
                    metrics["total_profit"] += (
                        float(str(t.gain_loss)) if t.gain_loss is not None else 0
                    )
                else:
                    metrics["unprofitable_transactions"] += 1
                    metrics["total_loss"] += abs(
                        float(str(t.gain_loss)) if t.gain_loss is not None else 0,
                    )
            elif t.state == TransactionState.CANCELLED.value:
                metrics["cancelled_transactions"] += 1

        metrics["total_transactions"] = len(transactions)
        metrics["net_gain_loss"] = metrics["total_profit"] - metrics["total_loss"]

        # Calculate averages and rates
        if metrics["profitable_transactions"] > 0:
            metrics["average_profit_per_transaction"] = (
                metrics["total_profit"] / metrics["profitable_transactions"]
            )

        if metrics["unprofitable_transactions"] > 0:
            metrics["average_loss_per_transaction"] = (
                metrics["total_loss"] / metrics["unprofitable_transactions"]
            )

        if metrics["closed_transactions"] > 0:
            metrics["win_rate"] = (
                metrics["profitable_transactions"] / metrics["closed_transactions"]
            ) * 100

        # Emit metrics update event
        metrics_data_dict: dict[str, any] = metrics
        EventService.emit_metrics_update(
            metric_type="transaction_stats",
            metric_data=metrics_data_dict,
            resource_id=service_id,
            resource_type="service",
        )

        return metrics

    @staticmethod
    def _raise_validation_error(
        message: str,
        errors: dict[str, any] | None = None,
    ) -> None:
        """Raise a validation error with the given message and errors.

        Args:
            message: The error message
            errors: Dictionary of validation errors to include

        Raises:
            ValidationError: Always raised

        """
        raise ValidationError(message, errors)

    @staticmethod
    def _raise_resource_not_found(
        resource_id: int | str,
    ) -> None:
        """Raise a resource not found error with the given message.

        Args:
            resource_id: The ID of the resource that was not found
            message: The error message

        Raises:
            ResourceNotFoundError: Always raised

        """
        # Define the resource type as a variable before using it in the exception
        resource_type: str = "Transaction"
        # The ResourceNotFoundError takes resource_type, resource_id, and optional
        # payload
        raise ResourceNotFoundError(resource_type, resource_id)

    @staticmethod
    def _raise_business_error(message: str) -> None:
        """Raise a business logic error with the given message.

        Args:
            message: The error message

        Raises:
            BusinessLogicError: Always raised

        """
        raise BusinessLogicError(message)

    @staticmethod
    def _raise_authorization_error(message: str) -> None:
        """Raise an authorization error with the given message.

        Args:
            message: The error message

        Raises:
            AuthorizationError: Always raised

        """
        raise AuthorizationError(message)

    @staticmethod
    def _reraise_or_convert_error(
        e: Exception,
        allowed_types: tuple[type[Exception], ...],
        conversion_type: type[Exception],
        message: str,
    ) -> None:
        """Re-raise original error if allowed, or convert to specified type."""
        if isinstance(e, allowed_types):
            raise e
        raise conversion_type(message.format(e)) from e

    @staticmethod
    def get_services_by_user(session: Session, user_id: int) -> list[TradingService]:
        """Get all services owned by a user.

        Args:
            session: Database session
            user_id: User ID

        Returns:
            List of trading services owned by the user

        """
        return (
            session.execute(
                select(TradingService).where(TradingService.user_id == user_id),
            )
            .scalars()
            .all()
        )

    @staticmethod
    def get_service_by_id(session: Session, service_id: int) -> TradingService | None:
        """Get a trading service by ID.

        Args:
            session: Database session
            service_id: Service ID

        Returns:
            Trading service if found, None otherwise

        """
        return session.execute(
            select(TradingService).where(TradingService.id == service_id),
        ).scalar_one_or_none()

    @staticmethod
    def get_transactions_for_user(
        session: Session,
        user_id: int,
        filters: dict[str, any] | None = None,
    ) -> list[TradingTransaction]:
        """Get all transactions for a user across all their services.

        Args:
            session: Database session
            user_id: User ID
            filters: Optional filters to apply (service_id, state)

        Returns:
            List of filtered transactions owned by the user

        """
        # Get all services owned by the user
        user_services: list[TradingService] = TransactionService.get_services_by_user(
            session,
            user_id,
        )

        if not user_services:
            return []

        service_ids: list[int] = [service.id for service in user_services]
        filters = filters or {}

        all_transactions: list[TradingTransaction] = []

        # If filtering by specific service
        if "service_id" in filters and filters["service_id"] in service_ids:
            if "state" in filters:
                transactions = TransactionService.get_by_service(
                    session,
                    filters["service_id"],
                    filters["state"],
                )
            else:
                transactions = TransactionService.get_by_service(
                    session,
                    filters["service_id"],
                )
            all_transactions.extend(transactions)
        else:
            # Get transactions for all user's services
            for service_id in service_ids:
                if "state" in filters:
                    transactions = TransactionService.get_by_service(
                        session,
                        service_id,
                        filters["state"],
                    )
                else:
                    transactions = TransactionService.get_by_service(
                        session,
                        service_id,
                    )
                all_transactions.extend(transactions)

        return all_transactions

    @staticmethod
    def sort_transactions(
        transactions: list[TradingTransaction],
        sort_field: str = "purchase_date",
        sort_order: str = "desc",
    ) -> list[TradingTransaction]:
        """Sort transactions by the specified field and order.

        Args:
            transactions: List of transactions to sort
            sort_field: Field to sort by (default: purchase_date)
            sort_order: Sort direction (asc/desc)

        Returns:
            Sorted list of transactions

        """

        def get_sort_key(t: TradingTransaction) -> any:
            try:
                val: any | None = getattr(t, sort_field, None)
                if val is None:
                    val = getattr(t, "purchase_date", None)
            except AttributeError:
                return None
            return val

        return sorted(
            transactions,
            key=get_sort_key,
            reverse=(sort_order.lower() == "desc"),
        )
