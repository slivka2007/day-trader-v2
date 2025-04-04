"""Trading Service service for managing TradingService model operations.

This service encapsulates all database interactions for the TradingService model,
providing a clean API for trading service management operations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import and_, or_, select

from app.api.schemas.trading_service import service_schema
from app.models.enums import ServiceState, TradingMode
from app.models.stock import Stock
from app.models.stock_daily_price import StockDailyPrice
from app.models.trading_service import TradingService
from app.services.events import EventService
from app.services.price_service import PriceService
from app.services.stock_service import StockService
from app.services.transaction_service import TransactionService
from app.utils.constants import TradingServiceConstants
from app.utils.current_datetime import get_current_date, get_current_datetime
from app.utils.errors import (
    AuthorizationError,
    BusinessLogicError,
    ResourceNotFoundError,
    TradingServiceError,
    ValidationError,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models.trading_transaction import TradingTransaction

# Set up logging
logger: logging.Logger = logging.getLogger(__name__)


class TradingServiceService:
    """Service for TradingService model operations.

    This class provides methods for managing trading service lifecycle,
    including CRUD operations and trading strategy execution.
    """

    # Resource types
    RESOURCE_TRADING_SERVICE: str = TradingServiceConstants.RESOURCE_TRADING_SERVICE
    RESOURCE_STOCK: str = TradingServiceConstants.RESOURCE_STOCK

    # Constants
    MIN_DAYS_FOR_SMA: int = TradingServiceConstants.MIN_DAYS_FOR_SMA

    @dataclass
    class BacktestDayParams:
        """Parameters for processing a backtest day."""

        price: StockDailyPrice
        price_history: list[float]
        current_balance: float
        shares_held: int
        last_buy_price: float | None
        buy_threshold: float
        sell_threshold: float
        allocation_percent: float
        day_index: int

    @staticmethod
    def _raise_error(error_class: type[Exception], *args: any) -> None:
        """Raise the specified error with given arguments.

        Args:
            error_class: The error class to raise
            args: Arguments to pass to the error constructor

        Raises:
            Exception: The specified error class with given arguments

        """
        raise error_class(*args)

    @staticmethod
    def _raise_not_found(resource_type: str, resource_id: int | str) -> None:
        """Raise ResourceNotFoundError with consistent formatting.

        Args:
            resource_type: Type of resource that was not found
            resource_id: ID of the resource that was not found

        Raises:
            ResourceNotFoundError: Always raised with formatted message

        """
        TradingServiceService._raise_error(
            ResourceNotFoundError,
            resource_type,
            resource_id,
        )

    @staticmethod
    def _raise_validation_error(
        message: str,
        errors: dict[str, any] | None = None,
    ) -> None:
        """Raise ValidationError with consistent formatting.

        Args:
            message: Error message
            errors: Optional validation errors dictionary

        Raises:
            ValidationError: Always raised with formatted message

        """
        TradingServiceService._raise_error(ValidationError, message, errors)

    @staticmethod
    def _raise_business_error(message: str) -> None:
        """Raise BusinessLogicError with consistent formatting.

        Args:
            message: Error message

        Raises:
            BusinessLogicError: Always raised with formatted message

        """
        TradingServiceService._raise_error(BusinessLogicError, message)

    @staticmethod
    def _reraise_if_validation_error(e: Exception) -> None:
        """Re-raise if the exception is a ValidationError.

        Args:
            e: The caught exception

        Raises:
            ValidationError: If e is a ValidationError

        """
        if isinstance(e, ValidationError):
            TradingServiceService._raise_error(type(e), *e.args)

    @staticmethod
    def _reraise_if_known_error(e: Exception) -> None:
        """Re-raise if the exception is a known error type.

        Args:
            e: The caught exception

        Raises:
            ResourceNotFoundError: If e is a ResourceNotFoundError
            BusinessLogicError: If e is a BusinessLogicError

        """
        if isinstance(e, (ResourceNotFoundError, BusinessLogicError)):
            TradingServiceService._raise_error(type(e), *e.args)

    # Read operations
    @staticmethod
    def get_by_id(session: Session, service_id: int) -> TradingService | None:
        """Get a trading service by ID.

        Args:
            session: Database session
            service_id: Trading service ID to retrieve

        Returns:
            TradingService instance if found, None otherwise

        """
        return session.execute(
            select(TradingService).where(TradingService.id == service_id),
        ).scalar_one_or_none()

    @staticmethod
    def get_or_404(session: Session, service_id: int) -> TradingService:
        """Get a trading service by ID or raise ResourceNotFoundError.

        Args:
            session: Database session
            service_id: Trading service ID to retrieve

        Returns:
            TradingService instance

        Raises:
            ResourceNotFoundError: If trading service not found

        """
        service: TradingService | None = TradingServiceService.get_by_id(
            session,
            service_id,
        )
        if not service:
            TradingServiceService._raise_not_found(
                TradingServiceService.RESOURCE_TRADING_SERVICE,
                service_id,
            )
        return service

    @staticmethod
    def get_by_user(session: Session, user_id: int) -> list[TradingService]:
        """Get all trading services for a user.

        Args:
            session: Database session
            user_id: User ID

        Returns:
            List of trading services

        """
        return (
            session.execute(
                select(TradingService).where(TradingService.user_id == user_id),
            )
            .scalars()
            .all()
        )

    @staticmethod
    def get_by_stock(session: Session, stock_symbol: str) -> list[TradingService]:
        """Get all trading services for a stock.

        Args:
            session: Database session
            stock_symbol: Stock symbol

        Returns:
            List of trading services

        """
        return (
            session.execute(
                select(TradingService).where(
                    TradingService.stock_symbol == stock_symbol.upper(),
                ),
            )
            .scalars()
            .all()
        )

    @staticmethod
    def get_all(session: Session) -> list[TradingService]:
        """Get all trading services.

        Args:
            session: Database session

        Returns:
            List of TradingService instances

        """
        return session.execute(select(TradingService)).scalars().all()

    @staticmethod
    def check_ownership(session: Session, service_id: int, user_id: int) -> bool:
        """Check if a user owns a service.

        Args:
            session: Database session
            service_id: Service ID
            user_id: User ID

        Returns:
            True if the user owns the service, False otherwise

        """
        service: TradingService | None = TradingServiceService.get_by_id(
            session,
            service_id,
        )
        if not service:
            return False

        return bool(service.user_id == user_id)

    @staticmethod
    def verify_ownership(
        session: Session,
        service_id: int,
        user_id: int,
    ) -> TradingService:
        """Verify a user owns a trading service, and return the service if they do.

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
        service: TradingService = TradingServiceService.get_or_404(session, service_id)

        if not bool(service.user_id == user_id):
            raise AuthorizationError

        return service

    @staticmethod
    def search_services(
        session: Session,
        user_id: int,
        query: str,
    ) -> list[TradingService]:
        """Search trading services by name or stock symbol.

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
        query_upper: str = query.upper()

        # Search for services matching the query by name or stock symbol
        services: list[TradingService] = (
            session.execute(
                select(TradingService).where(
                    and_(
                        TradingService.user_id == user_id,
                        or_(
                            TradingService.name.ilike(f"%{query}%"),
                            TradingService.stock_symbol == query_upper,
                        ),
                    ),
                ),
            )
            .scalars()
            .all()
        )

        return services

    @staticmethod
    def get_current_price_for_service(
        session: Session,
        service: TradingService,
    ) -> float:
        """Get the current price of the stock for a trading service.

        Args:
            session: Database session
            service: TradingService instance

        Returns:
            Current price of the stock

        """
        # Check if the service has a stock relationship
        if service.stock is not None and service.stock.id is not None:
            # Use StockService to get latest price

            return StockService.get_latest_price(session, service.stock) or 0.0

        # If no stock relationship, try to find by symbol
        return (
            TradingServiceService.get_current_price(session, service.stock_symbol)
            or 0.0
        )

    @staticmethod
    def calculate_performance_pct(session: Session, service: TradingService) -> float:
        """Return the performance of a trading service as a percentage.

        Calculates the percentage return based on initial balance.

        Args:
            session: Database session
            service: TradingService instance

        Returns:
            Performance percentage

        Raises:
            ResourceNotFoundError: If service not found

        """
        if service.initial_balance is None or service.initial_balance == 0.0:
            return 0.0

        # Get current price of the stock
        current_price: float = TradingServiceService.get_current_price_for_service(
            session,
            service,
        )

        # Calculate total value (balance + shares)
        total_value: float = service.current_balance + (
            service.current_shares * current_price
        )

        # Calculate performance as percentage
        return float(
            Decimal(
                str((total_value - service.initial_balance) / service.initial_balance),
            )
            * 100,
        )

    @staticmethod
    def update_service_attributes(
        service: TradingService,
        data: dict[str, any],
        allowed_fields: set[str] | None = None,
    ) -> bool:
        """Update service attributes from data dictionary.

        Args:
            service: TradingService instance
            data: Dictionary of attribute key/value pairs
            allowed_fields: Set of field names that are allowed to be updated

        Returns:
            True if any fields were updated, False otherwise

        """
        if allowed_fields is None:
            allowed_fields = {
                "name",
                "description",
                "is_active",
                "minimum_balance",
                "allocation_percent",
                "buy_threshold",
                "sell_threshold",
                "stop_loss_percent",
                "take_profit_percent",
            }

        updated = False
        for key, value in data.items():
            if key in allowed_fields and service[key] != value:
                service[key] = value
                updated = True

        return updated

    # Write operations
    @staticmethod
    def create_service(
        session: Session,
        user_id: int,
        data: dict[str, any],
    ) -> TradingService:
        """Create a new trading service.

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
        try:
            # Validate required fields
            required_fields: list[str] = ["name", "stock_symbol", "initial_balance"]
            for field in required_fields:
                if field not in data or not data[field]:
                    TradingServiceService._raise_validation_error(
                        TradingServiceError.REQUIRED_FIELD.format(field),
                    )

            # Validate initial balance
            initial_balance: float = data["initial_balance"]
            if initial_balance <= 0:
                TradingServiceService._raise_validation_error(
                    TradingServiceError.INITIAL_BALANCE,
                )

            # Find stock if it exists
            stock_symbol: str = data["stock_symbol"].upper()
            stock: Stock | None = session.execute(
                select(Stock).where(Stock.symbol == stock_symbol),
            ).scalar_one_or_none()
            stock_id: int | None = stock.id if stock else None

            # Set up service data
            service_data: dict[str, any] = {
                "user_id": user_id,
                "stock_id": stock_id,
                "stock_symbol": stock_symbol,
                "name": data["name"],
                "description": data.get("description", ""),
                "initial_balance": initial_balance,
                "current_balance": initial_balance,
                "minimum_balance": data.get("minimum_balance", 0),
                "allocation_percent": data.get("allocation_percent", 50),
                "buy_threshold": data.get("buy_threshold", 3.0),
                "sell_threshold": data.get("sell_threshold", 2.0),
                "stop_loss_percent": data.get("stop_loss_percent", 5.0),
                "take_profit_percent": data.get("take_profit_percent", 10.0),
                "state": ServiceState.INACTIVE.value,
                "mode": TradingMode.BUY.value,
                "is_active": True,
            }

            # Create service
            service: TradingService = TradingService(**service_data)
            session.add(service)
            session.commit()

            # Prepare response data
            service_data: dict[str, any] = service_schema.dump(service)

            # Emit WebSocket events
            EventService.emit_service_update(
                action="created",
                service_data=(
                    service_data if isinstance(service_data, dict) else service_data[0]
                ),
                service_id=service.id,
            )

        except Exception as e:
            logger.exception("Error creating trading service")
            session.rollback()
            TradingServiceService._reraise_if_validation_error(e)
            TradingServiceService._raise_validation_error(
                TradingServiceError.CREATE_SERVICE.format(e),
            )
        return service

    @staticmethod
    def update_service(
        session: Session,
        service: TradingService,
        data: dict[str, any],
    ) -> TradingService:
        """Update trading service attributes.

        Args:
            session: Database session
            service: TradingService instance to update
            data: Dictionary of attributes to update

        Returns:
            Updated TradingService instance

        Raises:
            ValidationError: If invalid data is provided

        """
        try:
            # Define which fields can be updated
            allowed_fields: set[str] = {
                "name",
                "description",
                "is_active",
                "minimum_balance",
                "allocation_percent",
                "buy_threshold",
                "sell_threshold",
                "stop_loss_percent",
                "take_profit_percent",
            }

            # Don't allow critical fields to be updated
            for field in [
                "user_id",
                "stock_id",
                "stock_symbol",
                "initial_balance",
                "current_balance",
            ]:
                data.pop(field, None)

            # Update the service attributes
            updated: bool = TradingServiceService.update_service_attributes(
                service,
                data,
                allowed_fields,
            )

            # Only commit if something was updated
            if updated:
                service.updated_at = get_current_datetime()
                session.commit()

                # Prepare response data
                service_data: dict[str, any] = service_schema.dump(service)

                # Emit WebSocket event
                EventService.emit_service_update(
                    action="updated",
                    service_data=(
                        service_data
                        if isinstance(service_data, dict)
                        else service_data[0]
                    ),
                    service_id=service.id,
                )

        except Exception as e:
            logger.exception("Error updating trading service")
            session.rollback()
            TradingServiceService._reraise_if_validation_error(e)
            TradingServiceService._raise_validation_error(
                TradingServiceError.UPDATE_SERVICE.format(e),
            )
        return service

    @staticmethod
    def toggle_active(session: Session, service: TradingService) -> TradingService:
        """Toggle service active status.

        Args:
            session: Database session
            service: TradingService instance

        Returns:
            Updated TradingService instance

        """
        try:
            # Toggle active status
            service.is_active = not bool(service.is_active)
            service.updated_at = get_current_datetime()
            session.commit()

            # Prepare response data
            service_data: dict[str, any] = service_schema.dump(service)
            action: str = "activated" if bool(service.is_active) else "deactivated"

            # Emit WebSocket event
            EventService.emit_service_update(
                action=action,
                service_data=(
                    service_data if isinstance(service_data, dict) else service_data[0]
                ),
                service_id=service.id,
            )

        except Exception as e:
            logger.exception("Error toggling trading service active status")
            session.rollback()
            TradingServiceService._reraise_if_validation_error(e)
            TradingServiceService._raise_validation_error(
                TradingServiceError.UPDATE_SERVICE.format(e),
            )
        return service

    @staticmethod
    def change_state(
        session: Session,
        service: TradingService,
        new_state: str,
    ) -> TradingService:
        """Change service state.

        Args:
            session: Database session
            service: TradingService instance
            new_state: New state value

        Returns:
            Updated TradingService instance

        Raises:
            ValidationError: If new state is invalid

        """
        try:
            # Validate state
            if not ServiceState.is_valid(new_state):
                valid_states: list[str] = ServiceState.values()
                TradingServiceService._raise_validation_error(
                    f"Invalid service state: {new_state}. Valid states are: "
                    f"{', '.join(valid_states)}",
                )

            # Check if state is changing
            if bool(service.state == new_state):
                return service

            # Update state
            service.state = new_state
            service.updated_at = get_current_datetime()
            session.commit()

            # Prepare response data
            service_data: dict[str, any] = service_schema.dump(service)

            # Emit WebSocket event
            EventService.emit_service_update(
                action="state_changed",
                service_data=(
                    service_data if isinstance(service_data, dict) else service_data[0]
                ),
                service_id=service.id,
            )

        except Exception as e:
            logger.exception("Error changing trading service state")
            session.rollback()
            TradingServiceService._reraise_if_validation_error(e)
            TradingServiceService._raise_validation_error(
                TradingServiceError.UPDATE_SERVICE.format(e),
            )
        return service

    @staticmethod
    def change_mode(
        session: Session,
        service: TradingService,
        new_mode: str,
    ) -> TradingService:
        """Change service trading mode.

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
        try:
            # Validate mode
            if not TradingMode.is_valid(new_mode):
                valid_modes: list[str] = TradingMode.values()
                TradingServiceService._raise_validation_error(
                    f"Invalid trading mode: {new_mode}. Valid modes are: "
                    f"{', '.join(valid_modes)}",
                )

            # Check if mode is changing
            if bool(service.mode == new_mode):
                return service

            # Validate mode transitions
            if new_mode == TradingMode.SELL.value and bool(service.current_shares <= 0):
                TradingServiceService._raise_business_error(
                    TradingServiceError.NO_SELL_NO_SHARES,
                )

            if new_mode == TradingMode.BUY.value and bool(
                service.current_balance <= service.minimum_balance,
            ):
                TradingServiceService._raise_business_error(
                    TradingServiceError.NO_BUY_MIN_BALANCE,
                )

            # Update mode
            service.mode = new_mode
            service.updated_at = get_current_datetime()
            session.commit()

            # Prepare response data
            service_data: dict[str, any] = service_schema.dump(service)

            # Emit WebSocket event
            EventService.emit_service_update(
                action="mode_changed",
                service_data=(
                    service_data if isinstance(service_data, dict) else service_data[0]
                ),
                service_id=service.id,
            )

        except Exception as e:
            logger.exception("Error changing trading service mode")
            session.rollback()
            TradingServiceService._reraise_if_validation_error(e)
            TradingServiceService._raise_validation_error(
                TradingServiceError.UPDATE_SERVICE.format(e),
            )
        return service

    @staticmethod
    def delete_service(session: Session, service: TradingService) -> bool:
        """Delete a trading service.

        Args:
            session: Database session
            service: TradingService instance

        Returns:
            True if successful

        Raises:
            BusinessLogicError: If service has dependencies that prevent deletion

        """
        try:
            # Check if service has dependencies
            if service.has_dependencies():
                TradingServiceService._raise_business_error(
                    TradingServiceError.DELETE_WITH_TRANSACTIONS,
                )

            # Store service ID for event emission
            service_id: int = service.id

            # Delete service
            session.delete(service)
            session.commit()

            # Emit WebSocket event
            EventService.emit_service_update(
                action="deleted",
                service_data={"id": service_id},
                service_id=service_id,
            )

        except Exception as e:
            logger.exception("Error deleting trading service")
            session.rollback()
            TradingServiceService._raise_validation_error(
                TradingServiceError.UPDATE_SERVICE.format(e),
            )
        return True

    @staticmethod
    def check_buy_condition(
        service: TradingService,
        current_price: float,
        historical_prices: list[float] | None = None,
    ) -> dict[str, any]:
        """Check if the conditions for buying are met.

        Args:
            session: Database session
            service: TradingService instance
            current_price: Current stock price
            historical_prices: Optional list of historical prices for analysis

        Returns:
            Dictionary with buy decision information

        """
        try:
            # Use the model's business logic
            return service.check_buy_condition(current_price, historical_prices)
        except Exception as e:
            logger.exception("Error checking buy condition")
            return {
                "should_buy": False,
                "can_buy": False,
                "reason": f"Error checking buy condition: {e!s}",
            }

    @staticmethod
    def check_sell_condition(
        service: TradingService,
        current_price: float,
        historical_prices: list[float] | None = None,
    ) -> dict[str, any]:
        """Check if the conditions for selling are met.

        Args:
            session: Database session
            service: TradingService instance
            current_price: Current stock price
            historical_prices: Optional list of historical prices for analysis

        Returns:
            Dictionary with sell decision information

        """
        try:
            # Use the model's business logic
            return service.check_sell_condition(current_price, historical_prices)
        except Exception as e:
            logger.exception("Error checking sell condition")
            return {
                "should_sell": False,
                "can_sell": False,
                "reason": f"Error checking sell condition: {e!s}",
            }

    @staticmethod
    def get_current_price(session: Session, stock_symbol: str) -> float:
        """Get the current price for a stock.

        Args:
            session: Database session
            stock_symbol: Stock symbol

        Returns:
            Current price or 0.0 if not available

        """
        try:
            # Get the stock
            stock: Stock | None = session.execute(
                select(Stock).where(Stock.symbol == stock_symbol.upper()),
            ).scalar_one_or_none()

            if not stock:
                return 0.0

            # Use the stock's latest price
            return stock.get_latest_price() or 0.0
        except Exception:
            logger.exception("Error getting current price for stock")
            return 0.0

    @staticmethod
    def execute_trading_strategy(session: Session, service_id: int) -> dict[str, any]:
        """Execute trading strategy for a service.

        This method coordinates the decision-making process for buying or selling
        stocks based on:
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
            BusinessLogicError: If service is not active or other business rule
            violations

        """
        # Get the service
        service: TradingService = TradingServiceService.get_or_404(session, service_id)

        # Check if service is active
        if not bool(service.is_active) or not bool(
            service.state == ServiceState.ACTIVE.value,
        ):
            return {
                "success": False,
                "message": f"Service is not active (state: {service.state}, "
                f"is_active: {service.is_active})",
                "action": "none",
            }

        # Get price analysis for the stock
        price_analysis: dict[str, any] = PriceService.get_price_analysis(
            session,
            service.stock_id,
        )

        if not bool(price_analysis.get("has_data", False)):
            return {
                "success": False,
                "message": "Insufficient price data for analysis",
                "action": "none",
            }

        # Get current price
        current_price: float | None = price_analysis.get("latest_price")
        if not current_price:
            return {
                "success": False,
                "message": "Could not determine current price",
                "action": "none",
            }

        # Trading decision
        result: dict[str, any] = {
            "success": True,
            "service_id": service_id,
            "stock_symbol": service.stock_symbol,
            "current_price": current_price,
            "current_balance": service.current_balance,
            "current_shares": service.current_shares,
            "mode": service.mode,
            "signals": price_analysis.get("signals", {}),
        }

        # Execute strategy based on mode
        if bool(service.mode == TradingMode.BUY.value):
            return TradingServiceService._execute_buy_strategy(
                session,
                service,
                price_analysis,
                current_price,
                result,
            )
        if bool(service.mode == TradingMode.SELL.value):
            return TradingServiceService._execute_sell_strategy(
                session,
                service,
                price_analysis,
                current_price,
                result,
            )
        if bool(service.mode == TradingMode.HOLD.value):
            result["action"] = "none"
            result["message"] = "Service is in HOLD mode, no actions taken"
        else:
            result["action"] = "none"
            result["message"] = f"Unsupported trading mode: {service.mode}"

        return result

    @staticmethod
    def _execute_buy_strategy(
        session: Session,
        service: TradingService,
        price_analysis: dict[str, any],
        current_price: float,
        result: dict[str, any],
    ) -> dict[str, any]:
        """Execute buy strategy for a trading service.

        Args:
            session: Database session
            service: TradingService instance
            price_analysis: Price analysis data
            current_price: Current stock price
            result: Base result dictionary to build upon

        Returns:
            Updated result dictionary with buy action information

        """
        # Check buy conditions using technical analysis
        should_buy: bool = TradingServiceService._should_buy(
            service,
            price_analysis,
            current_price,
        )
        result["should_buy"] = should_buy

        if not should_buy:
            result["action"] = "none"
            result["message"] = "Buy conditions not met"
            return result

        # Calculate how many shares to buy
        max_shares_affordable: int = (
            int(service.current_balance / current_price) if current_price > 0 else 0
        )
        allocation_amount: float = (
            service.current_balance * service.allocation_percent
        ) / 100
        shares_to_buy: int = int(allocation_amount / current_price)
        shares_to_buy = max(1, min(shares_to_buy, max_shares_affordable))

        if shares_to_buy <= 0:
            result["action"] = "none"
            result["message"] = "Not enough funds to buy shares"
            return result

        try:
            # Execute buy transaction
            transaction: TradingTransaction = TransactionService.create_buy_transaction(
                session=session,
                service_id=service.id,
                stock_symbol=service.stock_symbol,
                shares=shares_to_buy,
                purchase_price=current_price,
            )

            result["action"] = "buy"
            result["shares_bought"] = shares_to_buy
            result["transaction_id"] = transaction.id
            result["total_cost"] = shares_to_buy * current_price
            result["message"] = f"Bought {shares_to_buy} shares at ${current_price:.2f}"

            # Update service statistics
            service.buy_count = service.buy_count + 1
            service.current_shares = service.current_shares + shares_to_buy
            service.updated_at = get_current_datetime()
            session.commit()
        except Exception as e:
            logger.exception("Error executing buy transaction")
            result["success"] = False
            result["action"] = "none"
            result["message"] = f"Error executing buy transaction: {e!s}"

        return result

    @staticmethod
    def _execute_sell_strategy(
        session: Session,
        service: TradingService,
        price_analysis: dict[str, any],
        current_price: float,
        result: dict[str, any],
    ) -> dict[str, any]:
        """Execute sell strategy for a trading service.

        Args:
            session: Database session
            service: TradingService instance
            price_analysis: Price analysis data
            current_price: Current stock price
            result: Base result dictionary to build upon

        Returns:
            Updated result dictionary with sell action information

        """
        # Check sell conditions using technical analysis
        should_sell: bool = TradingServiceService._should_sell(
            service,
            price_analysis,
            current_price,
        )
        result["should_sell"] = should_sell

        if not should_sell:
            result["action"] = "none"
            result["message"] = "Sell conditions not met"
            return result

        # Get open transactions to sell
        open_transactions: list[TradingTransaction] = (
            TransactionService.get_open_transactions(session, service.id)
        )

        if not open_transactions:
            result["action"] = "none"
            result["message"] = "No open transactions to sell"
            return result

        completed_transactions: list[TradingTransaction] = []

        # Sell all open transactions
        try:
            for transaction in open_transactions:
                completed: TradingTransaction = TransactionService.complete_transaction(
                    session=session,
                    transaction_id=transaction.id,
                    sale_price=current_price,
                )
                completed_transactions.append(completed)
        except Exception:
            logger.exception("Error completing transaction")

        if not completed_transactions:
            result["action"] = "none"
            result["message"] = "Failed to complete any sell transactions"
            return result

        # Process successful sales
        total_shares_sold: float = sum(
            tx.shares for tx in completed_transactions if tx.shares is not None
        )
        total_revenue: float = total_shares_sold * current_price

        result["action"] = "sell"
        result["transactions_completed"] = len(completed_transactions)
        result["shares_sold"] = total_shares_sold
        result["total_revenue"] = total_revenue
        result["message"] = f"Sold {total_shares_sold} shares at ${current_price:.2f}"

        # Update service statistics
        service.sell_count = service.sell_count + len(
            completed_transactions,
        )
        service.current_shares = service.current_shares - int(
            total_shares_sold,
        )

        # Update gain/loss
        total_gain_loss: float = sum(
            tx.gain_loss for tx in completed_transactions if tx.gain_loss is not None
        )
        service.total_gain_loss = service.total_gain_loss + total_gain_loss

        service.updated_at = get_current_datetime()
        session.commit()

        return result

    @staticmethod
    def _should_buy(
        service: TradingService,
        price_analysis: dict[str, any],
        current_price: float,
    ) -> bool:
        """Determine if conditions for buying are met based on technical analysis.

        Args:
            service: Trading service instance
            price_analysis: Price analysis dictionary from PriceService
            current_price: Current stock price

        Returns:
            True if buy conditions are met, False otherwise

        """
        if not service.can_buy:
            return False

        signals = price_analysis.get("signals", {})

        # Check available funds
        max_shares_affordable: int = (
            int(service.current_balance / current_price) if current_price > 0 else 0
        )
        if max_shares_affordable <= 0:
            return False

        # Default to a conservative strategy that looks for oversold conditions
        # and bullish trends

        # RSI oversold signal (strongest buy indicator)
        if signals.get("rsi") == "oversold":
            return True

        # Bullish MA crossover
        if signals.get("ma_crossover") == "bullish":
            return True

        # Price near lower Bollinger Band (potential reversal)
        if signals.get("bollinger") == "oversold":
            return True

        # Check price trends
        is_uptrend: bool = price_analysis.get("is_uptrend")
        return is_uptrend and signals.get("rsi") == "neutral"

    @staticmethod
    def _should_sell(
        service: TradingService,
        price_analysis: dict[str, any],
    ) -> bool:
        """Determine if conditions for selling are met based on technical analysis.

        Args:
            service: Trading service instance
            price_analysis: Price analysis dictionary from PriceService
            current_price: Current stock price

        Returns:
            True if sell conditions are met, False otherwise

        """
        if not service.can_sell:
            return False

        signals: dict[str, any] = price_analysis.get("signals", {})

        # No shares to sell
        if bool(service.current_shares <= 0):
            return False

        # Default to a strategy that looks for overbought conditions
        # and bearish trends

        # RSI overbought signal (strongest sell indicator)
        if signals.get("rsi") == "overbought":
            return True

        # Bearish MA crossover
        if signals.get("ma_crossover") == "bearish":
            return True

        # Price near upper Bollinger Band (potential reversal)
        if signals.get("bollinger") == "overbought":
            return True

        # Check price trends
        is_uptrend: bool = price_analysis.get("is_uptrend")
        return not is_uptrend and signals.get("rsi", "") != "oversold"

    @staticmethod
    def _calculate_backtest_metrics(
        portfolio_values: list[float],
        initial_balance: float,
        days: int,
    ) -> dict[str, any]:
        """Calculate key metrics for backtest results."""
        start_value: float = initial_balance
        end_value: float = portfolio_values[-1] if portfolio_values else initial_balance
        total_return: float = end_value - start_value
        percent_return: float = (
            (total_return / start_value) * 100 if start_value > 0 else 0
        )

        # Calculate annualized return
        days_elapsed: int = min(days, len(portfolio_values))
        annualized_return: float = (
            ((1 + (percent_return / 100)) ** (365 / days_elapsed) - 1) * 100
            if days_elapsed > 0
            else 0
        )

        # Calculate drawdown
        max_drawdown: float = 0
        peak: float = portfolio_values[0] if portfolio_values else 0
        for value in portfolio_values:
            if value > peak:
                peak = value
            else:
                drawdown: float = (peak - value) / peak * 100 if peak > 0 else 0
                max_drawdown = max(max_drawdown, drawdown)

        # Calculate sharpe ratio
        sharpe_ratio: float = 0
        if len(portfolio_values) > 1:
            daily_returns: list[float] = [
                (portfolio_values[i] / portfolio_values[i - 1]) - 1
                for i in range(1, len(portfolio_values))
            ]
            mean_return: float = sum(daily_returns) / len(daily_returns)
            std_dev: float = (
                sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)
            ) ** 0.5
            sharpe_ratio = (
                (mean_return * 252) / (std_dev * (252**0.5)) if std_dev > 0 else 0
            )

        return {
            "end_value": end_value,
            "total_return": total_return,
            "percent_return": percent_return,
            "annualized_return": annualized_return,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
        }

    @staticmethod
    def _process_backtest_day(
        params: TradingServiceService.BacktestDayParams,
    ) -> tuple[float, int, float | None, dict[str, any] | None]:
        """Process a single day in the backtest simulation."""
        current_price: float = (
            float(params.price.close_price)
            if params.price.close_price is not None
            else 0.0
        )
        params.price_history.append(current_price)
        transaction: dict[str, any] | None = None

        if params.day_index >= TradingServiceService.MIN_DAYS_FOR_SMA:
            price_analysis: dict[str, any] = {
                "close_price": current_price,
                "sma_5": sum(
                    params.price_history[params.day_index - 4 : params.day_index + 1],
                )
                / 5,
                "sma_10": sum(
                    params.price_history[params.day_index - 9 : params.day_index + 1],
                )
                / 10,
                "sma_20": sum(
                    params.price_history[params.day_index - 19 : params.day_index + 1],
                )
                / 20,
            }

            if params.shares_held == 0:
                should_buy: bool = TradingServiceService._should_buy_backtest(
                    price_analysis,
                    current_price,
                    params.current_balance,
                    params.buy_threshold,
                    params.allocation_percent,
                )
                if should_buy:
                    amount_to_spend: float = params.current_balance * (
                        params.allocation_percent / 100.0
                    )
                    shares_to_buy: float = (
                        int((amount_to_spend / current_price) * 100) / 100.0
                    )
                    if shares_to_buy > 0:
                        cost: float = shares_to_buy * current_price
                        if cost <= params.current_balance:
                            params.current_balance -= cost
                            params.shares_held = shares_to_buy
                            params.last_buy_price = current_price
                            transaction = {
                                "type": "buy",
                                "date": params.price.price_date.isoformat(),
                                "price": current_price,
                                "shares": params.shares_held,
                                "cost": cost,
                                "balance": params.current_balance,
                            }

            elif params.shares_held > 0 and params.last_buy_price is not None:
                if params.last_buy_price > 0:
                    price_analysis["percent_gain"] = (
                        (current_price - params.last_buy_price) / params.last_buy_price
                    ) * 100
                should_sell: bool = TradingServiceService._should_sell_backtest(
                    price_analysis,
                )
                if should_sell:
                    revenue: float = params.shares_held * current_price
                    gain_loss: float = revenue - (
                        params.shares_held * params.last_buy_price
                    )
                    params.current_balance += revenue
                    transaction = {
                        "type": "sell",
                        "date": params.price.price_date.isoformat(),
                        "price": current_price,
                        "shares": params.shares_held,
                        "revenue": revenue,
                        "gain_loss": gain_loss,
                        "percent_gain": (
                            gain_loss / (params.shares_held * params.last_buy_price)
                        )
                        * 100
                        if params.last_buy_price > 0
                        else 0,
                        "balance": params.current_balance,
                    }
                    params.shares_held = 0
                    params.last_buy_price = None

        return (
            params.current_balance,
            params.shares_held,
            params.last_buy_price,
            transaction,
        )

    @staticmethod
    def backtest_strategy(
        session: Session,
        service_id: int,
        days: int = 90,
    ) -> dict[str, any]:
        """Backtest a trading strategy using historical price data."""
        try:
            service: TradingService = TradingServiceService.get_or_404(
                session,
                service_id,
            )
            stock: Stock | None = session.execute(
                select(Stock).where(Stock.symbol == service.stock_symbol),
            ).scalar_one_or_none()
            if not stock:
                TradingServiceService._raise_not_found(
                    TradingServiceService.RESOURCE_STOCK,
                    service.stock_symbol,
                )

            EventService.emit_system_notification(
                notification_type="backtest",
                message=f"Starting backtest for service {service_id} ({service.name}) "
                f"on {service.stock_symbol}",
                severity="info",
                details={"service_id": service_id, "days": days},
            )

            end_date: date = get_current_date()
            start_date: date = end_date - timedelta(days=days)
            prices: list[StockDailyPrice] = (
                session.execute(
                    select(StockDailyPrice)
                    .where(
                        and_(
                            StockDailyPrice.stock_id == stock.id,
                            StockDailyPrice.price_date >= start_date,
                            StockDailyPrice.price_date <= end_date,
                        ),
                    )
                    .order_by(StockDailyPrice.price_date),
                )
                .scalars()
                .all()
            )

            if not prices:
                TradingServiceService._raise_business_error(
                    TradingServiceError.INSUFFICIENT_PRICE_DATA.format(
                        service.stock_symbol,
                    ),
                )

            initial_balance: float = 10000.0
            current_balance: float = initial_balance
            shares_held: int = 0
            transactions: list[dict[str, any]] = []
            price_history: list[float] = []
            portfolio_values: list[float] = []
            last_buy_price: float | None = None

            for i, price in enumerate(prices):
                params = TradingServiceService.BacktestDayParams(
                    price=price,
                    price_history=price_history,
                    current_balance=current_balance,
                    shares_held=shares_held,
                    last_buy_price=last_buy_price,
                    buy_threshold=service.buy_threshold,
                    sell_threshold=service.sell_threshold,
                    allocation_percent=service.allocation_percent,
                    day_index=i,
                )
                current_balance, shares_held, last_buy_price, transaction = (
                    TradingServiceService._process_backtest_day(params)
                )

                if transaction:
                    transactions.append(transaction)

                current_price: float = (
                    float(price.close_price) if price.close_price is not None else 0.0
                )
                portfolio_values.append(current_balance + (shares_held * current_price))

            metrics: dict[str, any] = TradingServiceService._calculate_backtest_metrics(
                portfolio_values,
                initial_balance,
                days,
            )

            results: dict[str, any] = {
                "service_id": service_id,
                "service_name": service.name,
                "stock_symbol": service.stock_symbol,
                "backtest_days": days,
                "initial_balance": initial_balance,
                "final_balance": current_balance,
                **metrics,
                "transactions": transactions,
                "transaction_count": len(transactions),
                "portfolio_values": portfolio_values[:10],
                "price_history": price_history[:10],
            }

            EventService.emit_metrics_update(
                metric_type="backtest_results",
                metric_data=results,
                resource_id=service_id,
                resource_type="service",
            )

            EventService.emit_system_notification(
                notification_type="backtest",
                message=f"Backtest completed for service {service_id} with "
                f"{metrics['percent_return']:.2f}% return",
                severity="info",
                details={
                    "service_id": service_id,
                    "percent_return": metrics["percent_return"],
                    "transactions": len(transactions),
                },
            )

        except Exception as e:
            logger.exception("Error in backtest")
            EventService.emit_system_notification(
                notification_type="backtest",
                message=f"Backtest failed for service {service_id}: {e!s}",
                severity="error",
                details={"service_id": service_id, "error": str(e)},
            )
            TradingServiceService._reraise_if_known_error(e)
            TradingServiceService._raise_business_error(
                TradingServiceError.BACKTEST_FAILED.format(e),
            )
        return results

    @staticmethod
    def _should_buy_backtest(
        price_analysis: dict[str, any],
        current_price: float,
        current_balance: float,
    ) -> bool:
        """Simplified version of _should_buy for backtesting.

        Args:
            price_analysis: Price analysis dictionary
            current_price: Current stock price
            current_balance: Available balance
            buy_threshold: Buy threshold percentage
            allocation_percent: Allocation percentage

        Returns:
            True if buy conditions are met, False otherwise

        """
        # Check available funds
        max_shares_affordable: int = (
            int(current_balance / current_price) if current_price > 0 else 0
        )
        signals: dict[str, any] = price_analysis.get("signals", {})
        is_uptrend: bool = price_analysis.get("is_uptrend")

        return max_shares_affordable > 0 and (
            signals.get("rsi") == "oversold"
            or signals.get("ma_crossover") == "bullish"
            or signals.get("bollinger") == "oversold"
            or (not is_uptrend and signals.get("rsi", "") != "oversold")
        )

    @staticmethod
    def _should_sell_backtest(price_analysis: dict[str, any]) -> bool:
        """Simplified version of _should_sell for backtesting.

        Args:
            price_analysis: Price analysis dictionary

        Returns:
            True if sell conditions are met, False otherwise

        """
        signals: dict[str, any] = price_analysis.get("signals", {})
        is_uptrend: bool = price_analysis.get("is_uptrend")

        return (
            signals.get("rsi") == "overbought"
            or signals.get("ma_crossover") == "bearish"
            or signals.get("bollinger") == "overbought"
            or (not is_uptrend and signals.get("rsi", "") != "oversold")
        )
