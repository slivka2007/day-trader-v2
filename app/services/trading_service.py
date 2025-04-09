"""Trading Service service for managing TradingService model operations.

This service encapsulates all database interactions for the TradingService model,
providing a clean API for trading service management operations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import and_, or_

if TYPE_CHECKING:
    from app.models.stock import Stock

from app.api.schemas.trading_service import service_schema
from app.models.enums import ServiceState, TradingMode
from app.models.trading_service import TradingService
from app.services.events import EventService
from app.services.stock_service import StockService
from app.utils.constants import TradingServiceConstants
from app.utils.current_datetime import get_current_datetime
from app.utils.errors import (
    AuthorizationError,
    BusinessLogicError,
    ResourceNotFoundError,
    TradingServiceError,
    ValidationError,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Set up logging
logger: logging.Logger = logging.getLogger(__name__)


class TradingServiceService:
    """Service for TradingService model operations.

    This class provides methods for managing trading service lifecycle,
    including CRUD operations and service state management.
    """

    # Resource types
    RESOURCE_TRADING_SERVICE: str = TradingServiceConstants.RESOURCE_TRADING_SERVICE
    RESOURCE_STOCK: str = TradingServiceConstants.RESOURCE_STOCK

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
            errors: Optional dictionary of field-specific errors

        Raises:
            ValidationError: Always raised with formatted message and errors

        """
        TradingServiceService._raise_error(
            ValidationError,
            message,
            errors or {},
        )

    @staticmethod
    def _raise_business_error(message: str) -> None:
        """Raise BusinessLogicError with consistent formatting.

        Args:
            message: Error message

        Raises:
            BusinessLogicError: Always raised with formatted message

        """
        TradingServiceService._raise_error(
            BusinessLogicError,
            message,
        )

    @staticmethod
    def _reraise_if_validation_error(e: Exception) -> None:
        """Re-raise if exception is a ValidationError.

        Args:
            e: Exception to check

        Raises:
            ValidationError: If e is a ValidationError

        """
        if isinstance(e, ValidationError):
            raise e

    @staticmethod
    def _reraise_if_known_error(e: Exception) -> None:
        """Re-raise if exception is a known error type.

        Args:
            e: Exception to check

        Raises:
            Exception: If e is a known error type

        """
        if isinstance(
            e,
            (ValidationError, ResourceNotFoundError, BusinessLogicError),
        ):
            raise e

    @staticmethod
    def get_by_id(session: Session, service_id: int) -> TradingService | None:
        """Get a trading service by ID.

        Args:
            session: Database session
            service_id: Trading service ID

        Returns:
            TradingService if found, None otherwise

        """
        return (
            session.query(TradingService)
            .filter(TradingService.id == service_id)
            .first()
        )

    @staticmethod
    def get_or_404(session: Session, service_id: int) -> TradingService:
        """Get a trading service by ID or raise 404.

        Args:
            session: Database session
            service_id: Trading service ID

        Returns:
            TradingService instance

        Raises:
            ResourceNotFoundError: If service not found

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
            List of TradingService instances

        """
        return (
            session.query(TradingService)
            .filter(TradingService.user_id == user_id)
            .order_by(TradingService.created_at.desc())
            .all()
        )

    @staticmethod
    def get_by_stock(session: Session, stock_symbol: str) -> list[TradingService]:
        """Get all trading services for a stock.

        Args:
            session: Database session
            stock_symbol: Stock symbol

        Returns:
            List of TradingService instances

        """
        return (
            session.query(TradingService)
            .filter(TradingService.stock_symbol == stock_symbol.upper())
            .order_by(TradingService.created_at.desc())
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
        return (
            session.query(TradingService)
            .order_by(TradingService.created_at.desc())
            .all()
        )

    @staticmethod
    def check_ownership(session: Session, service_id: int, user_id: int) -> bool:
        """Check if a user owns a trading service.

        Args:
            session: Database session
            service_id: Trading service ID
            user_id: User ID

        Returns:
            True if user owns the service, False otherwise

        """
        service: TradingService | None = TradingServiceService.get_by_id(
            session,
            service_id,
        )
        return bool(service and service.user_id == user_id)

    @staticmethod
    def verify_ownership(
        session: Session,
        service_id: int,
        user_id: int,
    ) -> TradingService:
        """Verify service ownership and return the service.

        Args:
            session: Database session
            service_id: Trading service ID
            user_id: User ID

        Returns:
            TradingService instance

        Raises:
            ResourceNotFoundError: If service not found
            AuthorizationError: If user does not own the service

        """
        service: TradingService = TradingServiceService.get_or_404(
            session,
            service_id,
        )

        if service.user_id != user_id:
            TradingServiceService._raise_error(
                AuthorizationError,
                AuthorizationError.NOT_OWNER.format(
                    resource_type=TradingServiceService.RESOURCE_TRADING_SERVICE,
                    resource_id=service_id,
                ),
            )

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
        # Prepare search criteria
        search_term: str = f"%{query}%"

        # Construct the query
        services: list[TradingService] = (
            session.query(TradingService)
            .filter(
                and_(
                    TradingService.user_id == user_id,
                    or_(
                        TradingService.name.ilike(search_term),
                        TradingService.stock_symbol.ilike(search_term),
                    ),
                ),
            )
            .order_by(TradingService.created_at.desc())
            .all()
        )

        return services

    @staticmethod
    def calculate_performance_pct(session: Session, service: TradingService) -> float:
        """Calculate service performance as percentage of initial balance.

        Args:
            session: Database session
            service: TradingService instance

        Returns:
            Performance percentage

        """
        # Get the current price of the stock
        current_price: float = 0.0

        # Get the stock object
        stock: Stock | None = StockService.find_by_symbol(
            session,
            service.stock_symbol,
        )

        if stock:
            current_price = StockService.get_latest_price(session, stock) or 0.0

        # Calculate current portfolio value (balance + value of shares)
        portfolio_value: float = service.current_balance
        if service.current_shares > 0 and current_price > 0:
            portfolio_value += service.current_shares * current_price

        # Calculate performance as percentage of initial balance
        if service.initial_balance > 0:
            return (
                (portfolio_value - service.initial_balance) / service.initial_balance
            ) * 100
        return 0.0

    @staticmethod
    def update_service_attributes(
        service: TradingService,
        data: dict[str, any],
        allowed_fields: set[str] | None = None,
    ) -> bool:
        """Update trading service attributes.

        Args:
            service: TradingService instance
            data: Dictionary of attributes to update
            allowed_fields: Optional set of field names that are allowed to be updated

        Returns:
            True if any attributes were updated, False otherwise

        """
        if allowed_fields is None:
            allowed_fields = {
                "name",
                "description",
                "stock_symbol",
                "is_active",
                "minimum_balance",
                "allocation_percent",
                "buy_threshold",
                "sell_threshold",
                "stop_loss_percent",
                "take_profit_percent",
            }

        updated: bool = False

        for field, value in data.items():
            if (
                field in allowed_fields
                and hasattr(service, field)
                and getattr(service, field) != value
            ):
                setattr(service, field, value)
                updated = True

        if updated:
            service.updated_at = get_current_datetime()

        return updated

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
            data: Service data

        Returns:
            Created TradingService instance

        Raises:
            ValidationError: If validation fails
            BusinessLogicError: If business rules are violated

        """
        try:
            # Validate required fields
            required_fields: dict[str, str] = {
                "name": "Name",
                "stock_symbol": "Stock Symbol",
                "initial_balance": "Initial Balance",
            }

            for field, display_name in required_fields.items():
                if field not in data or not data[field]:
                    TradingServiceService._raise_validation_error(
                        TradingServiceError.FIELD_REQUIRED.format(key=display_name),
                    )

            # Get or validate stock
            stock_symbol: str = data["stock_symbol"].upper()
            stock: Stock | None = StockService.find_by_symbol(
                session,
                stock_symbol,
            )

            if not stock:
                # Stock doesn't exist, create it
                stock = StockService.create_stock(session, stock_symbol)

            stock_id: int = stock.id

            # Validate initial balance
            initial_balance: float = float(data["initial_balance"])

            if initial_balance <= 0:
                TradingServiceService._raise_validation_error(
                    TradingServiceError.INITIAL_BALANCE.format(
                        key="initial_balance",
                        value=initial_balance,
                    ),
                )

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
        """Update a trading service.

        Args:
            session: Database session
            service: TradingService instance
            data: Dictionary of attributes to update

        Returns:
            Updated TradingService instance

        Raises:
            ValidationError: If validation fails
            BusinessLogicError: If business rules are violated

        """
        try:
            # Check for stock symbol change
            if data.get("stock_symbol"):
                new_symbol: str = data["stock_symbol"].upper()

                if new_symbol != service.stock_symbol:
                    # Validate that we can change the stock symbol
                    if service.current_shares > 0:
                        TradingServiceService._raise_business_error(
                            TradingServiceError.CANT_CHANGE_SYMBOL_WITH_SHARES,
                        )

                    # Get or create the stock
                    stock: Stock | None = StockService.find_by_symbol(
                        session,
                        new_symbol,
                    )

                    if not stock:
                        # Stock doesn't exist, create it
                        stock = StockService.create_stock(session, new_symbol)

                    # Update stock_id
                    service.stock_id = stock.id
                    service.stock_symbol = new_symbol

                    # Remove stock_symbol from data to avoid duplicate update
                    del data["stock_symbol"]

            # Update allowed fields
            updated: bool = TradingServiceService.update_service_attributes(
                service,
                data,
            )

            if updated:
                session.commit()

                # Prepare response data
                service_data: dict[str, any] = service_schema.dump(service)

                # Emit WebSocket events
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
            TradingServiceService._reraise_if_known_error(e)
            TradingServiceService._raise_validation_error(
                TradingServiceError.UPDATE_SERVICE.format(e),
            )

        return service

    @staticmethod
    def toggle_active(session: Session, service: TradingService) -> TradingService:
        """Toggle the active status of a trading service.

        Args:
            session: Database session
            service: TradingService instance

        Returns:
            Updated TradingService instance

        Raises:
            ValidationError: If validation fails

        """
        try:
            # Toggle is_active flag
            service.is_active = not service.is_active
            service.updated_at = get_current_datetime()
            session.commit()

            # Prepare response data
            service_data: dict[str, any] = service_schema.dump(service)

            # Emit WebSocket event
            EventService.emit_service_update(
                action="toggled",
                service_data=(
                    service_data if isinstance(service_data, dict) else service_data[0]
                ),
                service_id=service.id,
            )

        except Exception as e:
            logger.exception("Error toggling trading service")
            session.rollback()
            TradingServiceService._raise_validation_error(
                TradingServiceError.TOGGLE_ERROR.format(e),
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
            ValidationError: If validation fails
            BusinessLogicError: If business rules are violated

        """
        try:
            # Validate state
            try:
                ServiceState(new_state)  # This will raise ValueError if invalid
            except ValueError:
                TradingServiceService._raise_validation_error(
                    TradingServiceError.INVALID_STATE,
                    {"state": [f"Invalid state: {new_state}"]},
                )

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
            new_mode: New trading mode value

        Returns:
            Updated TradingService instance

        Raises:
            ValidationError: If validation fails
            BusinessLogicError: If business rules are violated

        """
        try:
            # Validate mode
            try:
                TradingMode(new_mode)  # This will raise ValueError if invalid
            except ValueError:
                TradingServiceService._raise_validation_error(
                    TradingServiceError.INVALID_MODE,
                    {"mode": [f"Invalid mode: {new_mode}"]},
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
            if service.has_dependencies:
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
                TradingServiceError.DELETE_SERVICE.format(e),
            )
        return True

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
            stock: Stock | None = StockService.find_by_symbol(
                session,
                stock_symbol.upper(),
            )

            if not stock:
                return 0.0

            # Use the stock's latest price
            return StockService.get_latest_price(session, stock) or 0.0
        except Exception:
            logger.exception("Error getting current price for stock")
            return 0.0

    @staticmethod
    def execute_service_action(
        session: Session,
        service_id: int,
        action: str,
    ) -> dict[str, any]:
        """Execute a trading action for a service.

        This is a dispatcher method that delegates to the appropriate
        strategy service method.

        Args:
            session: Database session
            service_id: Trading service ID
            action: Action to execute (e.g., "buy", "sell", "execute_strategy")

        Returns:
            Dictionary with action results

        """
        from app.services.trading_strategy_service import TradingStrategyService

        # Get the service
        service: TradingService = TradingServiceService.get_or_404(
            session,
            service_id,
        )

        # Delegate to appropriate strategy method
        if action in ["buy", "sell"]:
            return TradingStrategyService.check_price_conditions(
                session,
                service,
                action,
            )
        if action == "execute_strategy":
            return TradingStrategyService.execute_trading_strategy(
                session,
                service_id,
            )
        return {
            "success": False,
            "message": f"Unknown action: {action}",
            "action": "none",
        }
