"""Daily price service for managing StockDailyPrice model operations.

This service encapsulates all database interactions for the StockDailyPrice model,
providing a clean API for daily stock price data management operations.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import and_, select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.api.schemas.stock_price import daily_price_schema
from app.models.enums import PriceSource
from app.models.stock import Stock
from app.models.stock_daily_price import StockDailyPrice
from app.services.data_providers.yfinance_provider import (
    get_daily_data,
    get_latest_daily_price,
)
from app.services.events import EventService
from app.utils.current_datetime import get_current_date, get_current_datetime
from app.utils.errors import (
    APIError,
    BusinessLogicError,
    ResourceNotFoundError,
    StockError,
    StockPriceError,
    ValidationError,
)

# Set up logging
logger: logging.Logger = logging.getLogger(__name__)


class DailyPriceService:
    """Service for daily stock price model operations."""

    # YFinance integration constants
    DEFAULT_DAILY_PERIOD: ClassVar[str] = "1y"
    VALID_DAILY_PERIODS: ClassVar[list[str]] = [
        "1mo",
        "3mo",
        "6mo",
        "1y",
        "2y",
        "5y",
        "10y",
        "ytd",
        "max",
    ]

    @staticmethod
    def _raise_not_found(price_id: int, price_type: str = "Daily price record") -> None:
        """Raise a ResourceNotFoundError for a price record."""
        raise ResourceNotFoundError(
            resource_type=price_type,
            resource_id=price_id,
        )

    @staticmethod
    def _raise_business_error(
        message: str,
        original_error: Exception | None = None,
    ) -> None:
        """Raise a BusinessLogicError with optional original error."""
        raise BusinessLogicError(message) from (
            original_error if original_error else BusinessLogicError(message)
        )

    @staticmethod
    def _raise_validation_error(message: str) -> None:
        """Raise a ValidationError with the given message."""
        raise StockPriceError(message)

    @staticmethod
    def update_stock_daily_prices(
        session: Session,
        stock_id: int,
        period: str = DEFAULT_DAILY_PERIOD,
    ) -> list[StockDailyPrice]:
        """Update daily price records for a stock by fetching data from Yahoo Finance.

        Args:
            session: Database session
            stock_id: Stock ID
            period: Time period to fetch data for (default: '1y')
                   Options: '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max'

        Returns:
            List of created or updated StockDailyPrice instances

        Raises:
            ResourceNotFoundError: If stock not found
            StockPriceError: If period is invalid
            BusinessLogicError: For other business logic errors
            APIError: If there's an error fetching data from Yahoo Finance

        """
        try:
            # Validate period
            if period not in DailyPriceService.VALID_DAILY_PERIODS:
                DailyPriceService._raise_validation_error(
                    f"Invalid period: {period}. Valid options are: "
                    f"{', '.join(DailyPriceService.VALID_DAILY_PERIODS)}",
                )

            # Verify stock exists and get symbol
            stock: Stock | None = session.execute(
                select(Stock).where(Stock.id == stock_id),
            ).scalar_one_or_none()
            if not stock:
                DailyPriceService._raise_not_found(stock_id, "Stock")

            # Fetch daily data from Yahoo Finance
            daily_data: list[dict[str, any]] = get_daily_data(stock.symbol, period)
            if not daily_data:
                logger.warning("No daily data returned for %s", stock.symbol)
                return []

            # Convert YFinance data format to our model format
            price_data: list[dict[str, any]] = [
                {
                    "price_date": item["date"],
                    "open_price": item["open"],
                    "high_price": item["high"],
                    "low_price": item["low"],
                    "close_price": item["close"],
                    "adj_close": item["adjusted_close"],
                    "volume": item["volume"],
                    "source": PriceSource.HISTORICAL.value,
                }
                for item in daily_data
            ]

            # Bulk import the price data
            return DailyPriceService.bulk_import_daily_prices(
                session,
                stock_id,
                price_data,
            )

        except (StockError, APIError):
            logger.exception(
                "Error updating daily prices for stock %s",
                stock_id,
            )
            session.rollback()
            raise
        except Exception as e:
            logger.exception("Error updating daily prices for stock %s", stock_id)
            session.rollback()
            DailyPriceService._raise_business_error(
                f"Could not update daily prices: {e!s}",
                e,
            )

    @staticmethod
    def update_latest_daily_price(
        session: Session,
        stock_id: int,
    ) -> StockDailyPrice:
        """Update the latest daily price record for a stock.

        This method fetches the latest daily price data from Yahoo Finance and updates
        the database. It also handles the conversion of YFinance data format to our
        model format.

        Args:
            session: Database session
            stock_id: Stock ID

        Returns:
            Created or updated StockDailyPrice instance

        Raises:
            ResourceNotFoundError: If stock not found
            BusinessLogicError: For other business logic errors
            APIError: If there's an error fetching data from Yahoo Finance

        """
        try:
            # Verify stock exists and get symbol
            stock: Stock | None = session.execute(
                select(Stock).where(Stock.id == stock_id),
            ).scalar_one_or_none()
            if not stock:
                DailyPriceService._raise_not_found(stock_id, "Stock")

            # Fetch latest daily price from Yahoo Finance
            price_data: dict[str, any] = get_latest_daily_price(stock.symbol)
            if not price_data:
                DailyPriceService._raise_business_error(
                    APIError.NO_DAILY_PRICE_DATA_ERROR + f" for {stock.symbol}",
                )

            # Check if price already exists for this date
            existing: StockDailyPrice | None = (
                DailyPriceService.get_daily_price_by_date(
                    session,
                    stock_id,
                    price_data["date"],
                )
            )

            if existing:
                # Update existing price record
                data: dict[str, any] = {
                    "open_price": price_data["open"],
                    "high_price": price_data["high"],
                    "low_price": price_data["low"],
                    "close_price": price_data["close"],
                    "adj_close": price_data["adjusted_close"],
                    "volume": price_data["volume"],
                    "source": PriceSource.HISTORICAL.value,
                }
                return DailyPriceService.update_daily_price(session, existing.id, data)
            # Create new price record
            data: dict[str, any] = {
                "open_price": price_data["open"],
                "high_price": price_data["high"],
                "low_price": price_data["low"],
                "close_price": price_data["close"],
                "adj_close": price_data["adjusted_close"],
                "volume": price_data["volume"],
                "source": PriceSource.HISTORICAL.value,
            }
            return DailyPriceService.create_daily_price(
                session,
                stock_id,
                price_data["date"],
                data,
            )

        except (StockError, APIError):
            logger.exception(
                "Error updating latest daily price for stock %s",
                stock_id,
            )
            session.rollback()
            raise
        except Exception as e:
            logger.exception("Error updating latest daily price for stock %s", stock_id)
            session.rollback()
            DailyPriceService._raise_business_error(
                APIError.LATEST_DAILY_PRICE_ERROR + f": {e!s}",
                e,
            )

    # Read operations
    @staticmethod
    def get_daily_price_by_id(
        session: Session,
        price_id: int,
    ) -> StockDailyPrice | None:
        """Get a daily price record by ID.

        Args:
            session: Database session
            price_id: Price record ID to retrieve

        Returns:
            StockDailyPrice instance if found, None otherwise

        """
        return session.execute(
            select(StockDailyPrice).where(StockDailyPrice.id == price_id),
        ).scalar_one_or_none()

    @staticmethod
    def get_daily_price_or_404(session: Session, price_id: int) -> StockDailyPrice:
        """Get a daily price record by ID or raise ResourceNotFoundError.

        Args:
            session: Database session
            price_id: Price record ID to retrieve

        Returns:
            StockDailyPrice instance

        Raises:
            ResourceNotFoundError: If price record not found

        """
        price: StockDailyPrice | None = DailyPriceService.get_daily_price_by_id(
            session,
            price_id,
        )
        if not price:
            DailyPriceService._raise_not_found(price_id)
        return price

    @staticmethod
    def get_daily_price_by_date(
        session: Session,
        stock_id: int,
        price_date: date,
    ) -> StockDailyPrice | None:
        """Get a daily price record by stock ID and date.

        Args:
            session: Database session
            stock_id: Stock ID
            price_date: Date of the price record

        Returns:
            StockDailyPrice instance if found, None otherwise

        """
        return session.execute(
            select(StockDailyPrice).where(
                and_(
                    StockDailyPrice.stock_id == stock_id,
                    StockDailyPrice.price_date == price_date,
                ),
            ),
        ).scalar_one_or_none()

    @staticmethod
    def get_daily_prices_by_date_range(
        session: Session,
        stock_id: int,
        start_date: date,
        end_date: date | None = None,
    ) -> list[StockDailyPrice]:
        """Get daily price records for a date range.

        Args:
            session: Database session
            stock_id: Stock ID
            start_date: Start date (inclusive)
            end_date: End date (inclusive), defaults to today

        Returns:
            List of StockDailyPrice instances

        """
        if end_date is None:
            end_date = get_current_date()

        return session.execute(
            select(StockDailyPrice)
            .where(
                and_(
                    StockDailyPrice.stock_id == stock_id,
                    StockDailyPrice.price_date >= start_date,
                    StockDailyPrice.price_date <= end_date,
                ),
            )
            .order_by(StockDailyPrice.price_date)
            .scalars()
            .all(),
        )

    @staticmethod
    def get_latest_daily_prices(
        session: Session,
        stock_id: int,
        days: int = 30,
    ) -> list[StockDailyPrice]:
        """Get the latest daily price records for a stock.

        Args:
            session: Database session
            stock_id: Stock ID
            days: Number of days to look back

        Returns:
            List of StockDailyPrice instances, most recent first

        """
        end_date: date = get_current_date()
        start_date: date = end_date - timedelta(days=days)

        return session.execute(
            select(StockDailyPrice)
            .where(
                and_(
                    StockDailyPrice.stock_id == stock_id,
                    StockDailyPrice.price_date >= start_date,
                    StockDailyPrice.price_date <= end_date,
                ),
            )
            .order_by(StockDailyPrice.price_date.desc())
            .scalars()
            .all(),
        )

    # Write operations
    @staticmethod
    def create_daily_price(
        session: Session,
        stock_id: int,
        price_date: date,
        data: dict[str, any],
    ) -> StockDailyPrice:
        """Create a new daily price record.

        Args:
            session: Database session
            stock_id: Stock ID
            price_date: Date of the price record
            data: Price data

        Returns:
            Created StockDailyPrice instance

        Raises:
            ValidationError: If required data is missing or invalid
            ResourceNotFoundError: If stock not found
            BusinessLogicError: For other business logic errors

        """
        try:
            # Verify stock exists
            stock: Stock | None = session.execute(
                select(Stock).where(Stock.id == stock_id),
            ).scalar_one_or_none()
            if not stock:
                DailyPriceService._raise_not_found(stock_id, "Stock")

            # Check if price already exists for this date
            existing: StockDailyPrice | None = (
                DailyPriceService.get_daily_price_by_date(
                    session,
                    stock_id,
                    price_date,
                )
            )
            if existing:
                DailyPriceService._raise_validation_error(
                    f"Price record already exists for stock ID {stock_id} on "
                    f"{price_date}",
                )

            # Validate price data
            if "high_price" in data and "low_price" in data:
                if data["high_price"] < data["low_price"]:
                    DailyPriceService._raise_validation_error(
                        "High price cannot be less than low price",
                    )
                else:
                    # Create the data dict including date and stock_id
                    create_data: dict[str, any] = {
                        "stock_id": stock_id,
                        "price_date": price_date,
                    }
                    create_data.update(data)
            else:
                # Create the data dict including date and stock_id
                create_data: dict[str, any] = {
                    "stock_id": stock_id,
                    "price_date": price_date,
                }
                create_data.update(data)

            # Create price record
            price_record: StockDailyPrice = StockDailyPrice.from_dict(create_data)
            session.add(price_record)
            session.commit()

            # Prepare response data
            price_data: dict[str, any] = daily_price_schema.dump(price_record)

            # Emit WebSocket event
            EventService.emit_price_update(
                action="created",
                price_data=(
                    price_data if isinstance(price_data, dict) else price_data[0]
                ),
                stock_symbol=str(stock.symbol),
            )

        except Exception as e:
            logger.exception("Error creating daily price")
            session.rollback()
            if isinstance(e, (ValidationError, ResourceNotFoundError)):
                raise
            DailyPriceService._raise_business_error(
                f"Could not create daily price record: {e!s}",
                e,
            )
        return price_record

    @staticmethod
    def update_daily_price(
        session: Session,
        price_id: int,
        data: dict[str, any],
    ) -> StockDailyPrice:
        """Update a daily price record.

        Args:
            session: Database session
            price_id: Price record ID to update
            data: Updated price data

        Returns:
            Updated StockDailyPrice instance

        Raises:
            ResourceNotFoundError: If price record not found
            ValidationError: If invalid data is provided
            BusinessLogicError: For other business logic errors

        """
        try:
            # Get price record
            price_record: StockDailyPrice = DailyPriceService.get_daily_price_or_404(
                session,
                price_id,
            )

            # Define which fields can be updated
            allowed_fields: set[str] = {
                "open_price",
                "high_price",
                "low_price",
                "close_price",
                "adj_close",
                "volume",
                "source",
            }

            # Validate price data if provided
            if "high_price" in data and "low_price" in data:
                if data["high_price"] < data["low_price"]:
                    DailyPriceService._raise_validation_error(
                        "High price cannot be less than low price",
                    )
                else:
                    # Use the update_from_dict method
                    updated: bool = price_record.update_from_dict(data, allowed_fields)

            # Only commit if something was updated
            if updated:
                price_record.updated_at = get_current_datetime()
                session.commit()

                # Get stock symbol for event
                stock_symbol: str = (
                    str(price_record.stock.symbol) if price_record.stock else "unknown"
                )

                # Prepare response data
                price_data: dict[str, any] = daily_price_schema.dump(price_record)

                # Emit WebSocket event
                EventService.emit_price_update(
                    action="updated",
                    price_data=(
                        price_data if isinstance(price_data, dict) else price_data[0]
                    ),
                    stock_symbol=stock_symbol,
                )

        except Exception as e:
            logger.exception("Error updating daily price")
            session.rollback()
            if isinstance(e, (ResourceNotFoundError, ValidationError)):
                raise
            DailyPriceService._raise_business_error(
                f"Could not update daily price record: {e!s}",
            )
        return price_record

    @staticmethod
    def delete_daily_price(session: Session, price_id: int) -> bool:
        """Delete a daily price record.

        Args:
            session: Database session
            price_id: Price record ID to delete

        Returns:
            True if successful

        Raises:
            ResourceNotFoundError: If price record not found
            BusinessLogicError: For other business logic errors

        """
        try:
            # Get price record
            price_record: StockDailyPrice = DailyPriceService.get_daily_price_or_404(
                session,
                price_id,
            )

            # Get stock symbol for event
            stock_symbol: str = (
                price_record.stock.symbol if price_record.stock else "unknown"
            )

            # Store price data for event
            price_data: dict[str, any] = {
                "id": price_record.id,
                "stock_id": price_record.stock_id,
                "price_date": price_record.price_date.isoformat(),
            }

            # Delete price record
            session.delete(price_record)
            session.commit()

            # Emit WebSocket event
            EventService.emit_price_update(
                action="deleted",
                price_data=price_data,
                stock_symbol=stock_symbol,
            )
        except Exception as e:
            logger.exception("Error deleting daily price")
            session.rollback()
            if isinstance(e, ResourceNotFoundError):
                raise
            DailyPriceService._raise_business_error(
                f"Could not delete daily price record: {e!s}",
            )
        return True

    # Bulk import operations
    @staticmethod
    def _validate_daily_price_data(item: dict[str, any]) -> None:
        """Validate a single daily price data item."""
        if "price_date" not in item:
            DailyPriceService._raise_validation_error(
                "Each price data item must include a 'price_date'",
            )

        if (
            "high_price" in item
            and "low_price" in item
            and item["high_price"] < item["low_price"]
        ):
            date_str: str = item["price_date"]
            DailyPriceService._raise_validation_error(
                f"High price cannot be less than low price for date {date_str}",
            )

    @staticmethod
    def _create_daily_price_record(
        session: Session,
        stock_id: int,
        item: dict[str, any],
    ) -> StockDailyPrice | None:
        """Create a single daily price record."""
        # Parse date if it's a string
        price_date: date = item["price_date"]
        if isinstance(price_date, str):
            try:
                from datetime import datetime

                price_date = datetime.strptime(
                    price_date + " +0000",
                    "%Y-%m-%d %z",
                ).date()
            except ValueError:
                DailyPriceService._raise_validation_error(
                    f"Invalid date format: {price_date}. Expected YYYY-MM-DD",
                )

        # Check if price already exists for this date
        existing: StockDailyPrice | None = DailyPriceService.get_daily_price_by_date(
            session,
            stock_id,
            price_date,
        )
        if existing:
            logger.warning(
                "Skipping existing price record for stock ID %s on %s",
                stock_id,
                price_date,
            )
            return None

        # Create data dict
        create_data: dict[str, any] = {
            "stock_id": stock_id,
            "price_date": price_date,
        }
        create_data.update({k: v for k, v in item.items() if k != "price_date"})

        # Create price record
        return StockDailyPrice.from_dict(create_data)

    @staticmethod
    def bulk_import_daily_prices(
        session: Session,
        stock_id: int,
        price_data: list[dict[str, any]],
    ) -> list[StockDailyPrice]:
        """Bulk import daily price records.

        Args:
            session: Database session
            stock_id: Stock ID
            price_data: List of price data dictionaries

        Returns:
            List of created StockDailyPrice instances

        Raises:
            ResourceNotFoundError: If stock not found
            ValidationError: If price data is invalid
            BusinessLogicError: For other business logic errors

        """
        try:
            # Verify stock exists
            stock: Stock | None = session.execute(
                select(Stock).where(Stock.id == stock_id),
            ).scalar_one_or_none()
            if not stock:
                DailyPriceService._raise_not_found(stock_id, "Stock")

            # Validate all price data first
            for item in price_data:
                DailyPriceService._validate_daily_price_data(item)

            # Create price records
            created_records: list[StockDailyPrice] = []
            for item in price_data:
                price_record = DailyPriceService._create_daily_price_record(
                    session,
                    stock_id,
                    item,
                )
                if price_record:
                    session.add(price_record)
                    created_records.append(price_record)

            session.commit()

            # Emit events for created records
            for record in created_records:
                dumped_data: dict[str, any] = daily_price_schema.dump(record)
                EventService.emit_price_update(
                    action="created",
                    price_data=(
                        dumped_data if isinstance(dumped_data, dict) else dumped_data[0]
                    ),
                    stock_symbol=stock.symbol,
                )

        except Exception as e:
            logger.exception("Error bulk importing daily prices")
            session.rollback()
            if isinstance(e, (ValidationError, ResourceNotFoundError)):
                raise
            DailyPriceService._raise_business_error(
                f"Could not bulk import daily prices: {e!s}",
                e,
            )
        return created_records
