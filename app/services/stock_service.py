"""Stock service for managing Stock model operations.

This service encapsulates all database interactions for the Stock model,
providing a clean API for stock management operations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import or_, select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.api.schemas.stock import stock_schema
from app.models.stock import Stock
from app.models.stock_daily_price import StockDailyPrice
from app.services.events import EventService
from app.utils.current_datetime import get_current_datetime
from app.utils.errors import BusinessLogicError, ResourceNotFoundError, ValidationError

# Set up logging
logger: logging.Logger = logging.getLogger(__name__)


class StockService:
    """Service for Stock model operations."""

    @staticmethod
    def _raise_not_found(resource_id: any, resource_type: str = "Stock") -> None:
        """Raise a ResourceNotFoundError."""
        raise ResourceNotFoundError(resource_type, resource_id)

    @staticmethod
    def _raise_validation_error(
        message: str,
        original_error: Exception | None = None,
    ) -> None:
        """Raise a ValidationError with optional original error."""
        if original_error:
            raise ValidationError(message) from original_error
        raise ValidationError(message)

    @staticmethod
    def _raise_business_error(
        message: str,
        original_error: Exception | None = None,
    ) -> None:
        """Raise a BusinessLogicError with optional original error."""
        if original_error:
            raise BusinessLogicError(message) from original_error
        raise BusinessLogicError(message)

    # Read operations
    @staticmethod
    def find_by_symbol(session: Session, symbol: str) -> Stock | None:
        """Find a stock by symbol.

        Args:
            session: Database session
            symbol: Stock symbol to search for (case-insensitive)

        Returns:
            Stock instance if found, None otherwise

        """
        if not symbol:
            return None

        return session.execute(
            select(Stock).where(Stock.symbol == symbol.upper()),
        ).scalar_one_or_none()

    @staticmethod
    def find_by_symbol_or_404(session: Session, symbol: str) -> Stock:
        """Find a stock by symbol or raise ResourceNotFoundError.

        Args:
            session: Database session
            symbol: Stock symbol to search for (case-insensitive)

        Returns:
            Stock instance

        Raises:
            ResourceNotFoundError: If stock not found

        """
        stock: Stock | None = StockService.find_by_symbol(session, symbol)
        if not stock:
            error_id: str = f"symbol '{symbol.upper()}'"
            StockService._raise_not_found(error_id, "Stock")
        return stock

    @staticmethod
    def get_by_id(session: Session, stock_id: int) -> Stock | None:
        """Get a stock by ID.

        Args:
            session: Database session
            stock_id: Stock ID to retrieve

        Returns:
            Stock instance if found, None otherwise

        """
        return session.execute(
            select(Stock).where(Stock.id == stock_id),
        ).scalar_one_or_none()

    @staticmethod
    def get_or_404(session: Session, stock_id: int) -> Stock:
        """Get a stock by ID or raise ResourceNotFoundError.

        Args:
            session: Database session
            stock_id: Stock ID to retrieve

        Returns:
            Stock instance

        Raises:
            ResourceNotFoundError: If stock not found

        """
        stock: Stock | None = StockService.get_by_id(session, stock_id)
        if not stock:
            StockService._raise_not_found(stock_id)
        return stock

    @staticmethod
    def get_all(session: Session) -> list[Stock]:
        """Get all stocks.

        Args:
            session: Database session

        Returns:
            List of Stock instances

        """
        return session.execute(select(Stock)).scalars().all()

    # Write operations
    @staticmethod
    def create_stock(session: Session, data: dict[str, any]) -> Stock:
        """Create a new stock.

        Args:
            session: Database session
            data: Stock data dictionary

        Returns:
            Created stock instance

        Raises:
            ValidationError: If required fields are missing or invalid

        """
        try:
            # Validate required fields
            if "symbol" not in data or not data["symbol"]:
                error_msg = "Stock symbol is required"
                StockService._raise_validation_error(error_msg)

            # Check if symbol already exists
            existing: Stock | None = StockService.find_by_symbol(
                session,
                data["symbol"],
            )
            if existing:
                error_msg = (
                    f"Stock with symbol '{data['symbol'].upper()}' already exists"
                )
                StockService._raise_validation_error(error_msg)

            # Ensure symbol is uppercase
            if "symbol" in data:
                data["symbol"] = data["symbol"].upper()

            # Create stock instance
            stock: Stock = Stock.from_dict(data)
            session.add(stock)
            session.commit()

            # Prepare response data
            stock_data: dict[str, any] = stock_schema.dump(stock)

            # Emit WebSocket event
            EventService.emit_stock_update(
                action="created",
                stock_data=(
                    stock_data if isinstance(stock_data, dict) else stock_data[0]
                ),
                stock_symbol=stock.symbol,
            )

        except Exception as e:
            logger.exception("Error creating stock")
            session.rollback()
            if isinstance(e, ValidationError):
                raise
            error_msg: str = f"Could not create stock: {e!s}"
            StockService._raise_validation_error(error_msg, e)
        return stock

    @staticmethod
    def update_stock(session: Session, stock: Stock, data: dict[str, any]) -> Stock:
        """Update stock attributes.

        Args:
            session: Database session
            stock: Stock instance to update
            data: Dictionary of attributes to update

        Returns:
            Updated stock instance

        Raises:
            ValidationError: If invalid data is provided

        """
        from app.services.events import EventService

        try:
            # Define which fields can be updated
            allowed_fields: set[str] = {"name", "is_active", "sector", "description"}

            # Don't allow symbol to be updated
            data.pop("symbol", None)

            # Update the stock attributes
            updated: bool = StockService.update_stock_attributes(
                stock,
                data,
                allowed_fields,
            )

            # Only emit event if something was updated
            if updated:
                stock.updated_at = get_current_datetime()
                session.commit()

                # Prepare response data
                stock_data: dict[str, any] = stock_schema.dump(stock)

                # Emit WebSocket event
                EventService.emit_stock_update(
                    action="updated",
                    stock_data=(
                        stock_data if isinstance(stock_data, dict) else stock_data[0]
                    ),
                    stock_symbol=str(stock.symbol),
                )

        except Exception as e:
            logger.exception("Error updating stock")
            session.rollback()
            if isinstance(e, ValidationError):
                raise
            error_msg: str = f"Could not update stock: {e!s}"
            StockService._raise_validation_error(error_msg, e)
        return stock

    @staticmethod
    def update_stock_attributes(
        stock: Stock,
        data: dict[str, any],
        allowed_fields: set[str] | None = None,
    ) -> bool:
        """Update stock attributes directly without committing to the database.

        Args:
            stock: Stock instance to update
            data: Dictionary of attributes to update
            allowed_fields: Set of field names that are allowed to be updated

        Returns:
            True if any fields were updated, False otherwise

        """
        return stock.update_from_dict(data, allowed_fields)

    @staticmethod
    def change_active_status(
        session: Session,
        stock: Stock,
        *,
        is_active: bool,
    ) -> Stock:
        """Change the active status of the stock.

        Args:
            session: Database session
            stock: Stock instance
            is_active: New active status (keyword-only argument)

        Returns:
            Updated stock instance

        """
        try:
            # Only update if status is changing
            if stock.is_active != is_active:
                stock.is_active = is_active
                stock.updated_at = get_current_datetime()
                session.commit()

                # Prepare response data
                stock_data: dict[str, any] = stock_schema.dump(stock)

                # Emit WebSocket event
                EventService.emit_stock_update(
                    action="status_changed",
                    stock_data=(
                        stock_data if isinstance(stock_data, dict) else stock_data[0]
                    ),
                    stock_symbol=str(stock.symbol),
                )

        except Exception as e:
            logger.exception("Error changing stock status")
            session.rollback()
            error_msg: str = f"Could not change stock status: {e!s}"
            StockService._raise_validation_error(error_msg, e)
        return stock

    @staticmethod
    def toggle_active(session: Session, stock: Stock) -> Stock:
        """Toggle the active status of the stock.

        Args:
            session: Database session
            stock: Stock instance

        Returns:
            Updated stock instance

        """
        return StockService.change_active_status(
            session,
            stock,
            is_active=not stock.is_active,
        )

    @staticmethod
    def delete_stock(session: Session, stock: Stock) -> bool:
        """Delete a stock if it has no dependencies.

        Args:
            session: Database session
            stock: Stock instance to delete

        Returns:
            True if stock was deleted, False otherwise

        Raises:
            BusinessLogicError: If stock has dependencies

        """
        try:
            # Check for dependencies
            if stock.has_dependencies():
                error_msg = (
                    f"Cannot delete stock '{stock.symbol}' because it has associated "
                    f"trading services or transactions"
                )
                StockService._raise_business_error(error_msg)

            # Store symbol for event
            symbol: str = stock.symbol

            # Delete the stock
            session.delete(stock)
            session.commit()

            # Emit WebSocket event
            EventService.emit_stock_update(
                action="deleted",
                stock_data={"symbol": symbol},
                stock_symbol=symbol,
            )

        except Exception as e:
            logger.exception("Error deleting stock")
            session.rollback()
            if isinstance(e, BusinessLogicError):
                raise
            error_msg: str = f"Could not delete stock: {e!s}"
            StockService._raise_validation_error(error_msg, e)
        return True

    @staticmethod
    def get_latest_price(session: Session, stock: Stock) -> float | None:
        """Get the latest price for a stock.

        Args:
            session: Database session
            stock: Stock instance

        Returns:
            Latest closing price if available, None otherwise

        """
        if not stock.daily_prices:
            return None

        # Query to get the most recent price
        latest_price: StockDailyPrice | None = session.execute(
            select(StockDailyPrice)
            .where(StockDailyPrice.stock_id == stock.id)
            .order_by(StockDailyPrice.price_date.desc()),
        ).scalar_one_or_none()

        return (
            latest_price.close_price
            if latest_price and latest_price.close_price is not None
            else None
        )

    @staticmethod
    def search_stocks(session: Session, query: str, limit: int = 10) -> list[Stock]:
        """Search for stocks by symbol or name.

        Args:
            session: Database session
            query: Search query string
            limit: Maximum number of results to return

        Returns:
            List of matching Stock instances

        """
        if not query:
            return []

        # Search by symbol or name (case insensitive)
        search_term: str = f"%{query}%"
        return (
            session.execute(
                select(Stock)
                .where(
                    or_(Stock.symbol.ilike(search_term), Stock.name.ilike(search_term)),
                )
                .limit(limit),
            )
            .scalars()
            .all()
        )
