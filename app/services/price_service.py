"""Price service for managing StockDailyPrice and StockIntradayPrice model operations.

This service encapsulates all database interactions for the price models,
providing a clean API for stock price data management operations.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import and_, select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Import Base from the shared location

from app.api.schemas.stock_price import (
    daily_price_schema,
    intraday_price_schema,
)
from app.models.stock import Stock
from app.models.stock_daily_price import StockDailyPrice
from app.models.stock_intraday_price import StockIntradayPrice
from app.services.events import EventService
from app.utils.current_datetime import get_current_date, get_current_datetime
from app.utils.errors import BusinessLogicError, ResourceNotFoundError, ValidationError

# Set up logging
logger: logging.Logger = logging.getLogger(__name__)


class PriceService:
    """Service for stock price model operations."""

    # Constants for technical analysis
    MIN_DATA_POINTS: int = 5
    SHORT_MA_PERIOD: int = 5
    MEDIUM_MA_PERIOD: int = 10
    LONG_MA_PERIOD: int = 20
    EXTENDED_MA_PERIOD: int = 50
    MAX_MA_PERIOD: int = 200

    # RSI constants
    RSI_OVERSOLD: int = 30
    RSI_OVERBOUGHT: int = 70
    RSI_MIN_PERIODS: int = 15

    # Constants for default periods
    DEFAULT_MA_PERIOD: int = 20
    DEFAULT_BB_PERIOD: int = 20

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
        raise ValidationError(message)

    #
    # Daily Price Operations
    #

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
        price: StockDailyPrice | None = PriceService.get_daily_price_by_id(
            session,
            price_id,
        )
        if not price:
            PriceService._raise_not_found(price_id)
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
                PriceService._raise_not_found(stock_id, "Stock")

            # Check if price already exists for this date
            existing: StockDailyPrice | None = PriceService.get_daily_price_by_date(
                session,
                stock_id,
                price_date,
            )
            if existing:
                PriceService._raise_validation_error(
                    f"Price record already exists for stock ID {stock_id} on "
                    f"{price_date}",
                )

            # Validate price data
            if "high_price" in data and "low_price" in data:
                if data["high_price"] < data["low_price"]:
                    PriceService._raise_validation_error(
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
            PriceService._raise_business_error(
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
            price_record: StockDailyPrice = PriceService.get_daily_price_or_404(
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
                    PriceService._raise_validation_error(
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
            PriceService._raise_business_error(
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
            price_record: StockDailyPrice = PriceService.get_daily_price_or_404(
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
            PriceService._raise_business_error(
                f"Could not delete daily price record: {e!s}",
            )
        return True

    #
    # Intraday Price Operations
    #

    # Read operations
    @staticmethod
    def get_intraday_price_by_id(
        session: Session,
        price_id: int,
    ) -> StockIntradayPrice | None:
        """Get an intraday price record by ID.

        Args:
            session: Database session
            price_id: Price record ID to retrieve

        Returns:
            StockIntradayPrice instance if found, None otherwise

        """
        return session.execute(
            select(StockIntradayPrice).where(StockIntradayPrice.id == price_id),
        ).scalar_one_or_none()

    @staticmethod
    def get_intraday_price_or_404(
        session: Session,
        price_id: int,
    ) -> StockIntradayPrice:
        """Get an intraday price record by ID or raise ResourceNotFoundError.

        Args:
            session: Database session
            price_id: Price record ID to retrieve

        Returns:
            StockIntradayPrice instance

        Raises:
            ResourceNotFoundError: If price record not found

        """
        price: StockIntradayPrice | None = PriceService.get_intraday_price_by_id(
            session,
            price_id,
        )
        if not price:
            PriceService._raise_not_found(price_id, "Intraday price record")
        return price

    @staticmethod
    def get_intraday_price_by_timestamp(
        session: Session,
        stock_id: int,
        timestamp: datetime,
        interval: int = 1,
    ) -> StockIntradayPrice | None:
        """Get an intraday price record by stock ID and timestamp.

        Args:
            session: Database session
            stock_id: Stock ID
            timestamp: Timestamp of the price record
            interval: Time interval in minutes

        Returns:
            StockIntradayPrice instance if found, None otherwise

        """
        return session.execute(
            select(StockIntradayPrice)
            .where(
                and_(
                    StockIntradayPrice.stock_id == stock_id,
                    StockIntradayPrice.timestamp == timestamp,
                    StockIntradayPrice.interval == interval,
                ),
            )
            .scalars()
            .one_or_none(),
        )

    @staticmethod
    def get_intraday_prices_by_time_range(
        session: Session,
        stock_id: int,
        start_time: datetime,
        end_time: datetime | None = None,
        interval: int = 1,
    ) -> list[StockIntradayPrice]:
        """Get intraday price records for a time range.

        Args:
            session: Database session
            stock_id: Stock ID
            start_time: Start timestamp (inclusive)
            end_time: End timestamp (inclusive), defaults to now
            interval: Time interval in minutes

        Returns:
            List of StockIntradayPrice instances

        """
        if end_time is None:
            end_time = get_current_datetime()

        return session.execute(
            select(StockIntradayPrice)
            .where(
                and_(
                    StockIntradayPrice.stock_id == stock_id,
                    StockIntradayPrice.timestamp >= start_time,
                    StockIntradayPrice.timestamp <= end_time,
                    StockIntradayPrice.interval == interval,
                ),
            )
            .order_by(StockIntradayPrice.timestamp)
            .scalars()
            .all(),
        )

    @staticmethod
    def get_latest_intraday_prices(
        session: Session,
        stock_id: int,
        hours: int = 8,
        interval: int = 1,
    ) -> list[StockIntradayPrice]:
        """Get the latest intraday price records for a stock.

        Args:
            session: Database session
            stock_id: Stock ID
            hours: Number of hours to look back
            interval: Time interval in minutes

        Returns:
            List of StockIntradayPrice instances, most recent first

        """
        end_time: datetime = get_current_datetime()
        start_time: datetime = end_time - timedelta(hours=hours)

        return session.execute(
            select(StockIntradayPrice)
            .where(
                and_(
                    StockIntradayPrice.stock_id == stock_id,
                    StockIntradayPrice.timestamp >= start_time,
                    StockIntradayPrice.timestamp <= end_time,
                    StockIntradayPrice.interval == interval,
                ),
            )
            .order_by(StockIntradayPrice.timestamp.desc())
            .scalars()
            .all(),
        )

    # Write operations
    @staticmethod
    def create_intraday_price(
        session: Session,
        stock_id: int,
        timestamp: datetime,
        interval: int,
        data: dict[str, any],
    ) -> StockIntradayPrice:
        """Create a new intraday price record.

        Args:
            session: Database session
            stock_id: Stock ID
            timestamp: Timestamp of the price record
            interval: Time interval in minutes
            data: Price data

        Returns:
            Created StockIntradayPrice instance

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
                PriceService._raise_not_found(stock_id, "Stock")

            # Check if price already exists for this timestamp & interval
            existing: StockIntradayPrice | None = (
                PriceService.get_intraday_price_by_timestamp(
                    session,
                    stock_id,
                    timestamp,
                    interval,
                )
            )
            if existing:
                PriceService._raise_validation_error(
                    f"Price record already exists for stock ID {stock_id} at "
                    f"{timestamp} with interval {interval}",
                )

            # Validate price data
            if (
                "high_price" in data
                and "low_price" in data
                and data["high_price"] < data["low_price"]
            ):
                PriceService._raise_validation_error(
                    "High price cannot be less than low price",
                )
            else:
                # Create the data dict including timestamp, interval and stock_id
                create_data: dict[str, any] = {
                    "stock_id": stock_id,
                    "timestamp": timestamp,
                    "interval": interval,
                }
                create_data.update(data)

            # Create price record
            price_record: StockIntradayPrice = StockIntradayPrice.from_dict(create_data)
            session.add(price_record)
            session.commit()

            # Prepare response data
            price_data: dict[str, any] = intraday_price_schema.dump(price_record)

            # Emit WebSocket event
            EventService.emit_price_update(
                action="created",
                price_data=(
                    price_data if isinstance(price_data, dict) else price_data[0]
                ),
                stock_symbol=stock.symbol,
            )

        except Exception as e:
            logger.exception("Error creating intraday price")
            session.rollback()
            if isinstance(e, (ValidationError, ResourceNotFoundError)):
                raise
            PriceService._raise_business_error(
                f"Could not create intraday price record: {e!s}",
            )
        return price_record

    @staticmethod
    def update_intraday_price(
        session: Session,
        price_id: int,
        data: dict[str, any],
    ) -> StockIntradayPrice:
        """Update an intraday price record.

        Args:
            session: Database session
            price_id: Price record ID to update
            data: Updated price data

        Returns:
            Updated StockIntradayPrice instance

        Raises:
            ResourceNotFoundError: If price record not found
            ValidationError: If invalid data is provided
            BusinessLogicError: For other business logic errors

        """
        try:
            # Get price record
            price_record: StockIntradayPrice = PriceService.get_intraday_price_or_404(
                session,
                price_id,
            )

            # Define which fields can be updated
            allowed_fields: set[str] = {
                "open_price",
                "high_price",
                "low_price",
                "close_price",
                "volume",
                "source",
            }

            # Validate price data if provided
            if "high_price" in data and "low_price" in data:
                if data["high_price"] < data["low_price"]:
                    PriceService._raise_validation_error(
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
                    price_record.stock.symbol if price_record.stock else "unknown"
                )

                # Prepare response data
                price_data: dict[str, any] = intraday_price_schema.dump(price_record)

                # Emit WebSocket event
                EventService.emit_price_update(
                    action="updated",
                    price_data=(
                        price_data if isinstance(price_data, dict) else price_data[0]
                    ),
                    stock_symbol=stock_symbol,
                )

        except Exception as e:
            logger.exception("Error updating intraday price")
            session.rollback()
            if isinstance(e, (ResourceNotFoundError, ValidationError)):
                raise
            PriceService._raise_business_error(
                f"Could not update intraday price record: {e!s}",
            )
        return price_record

    @staticmethod
    def delete_intraday_price(session: Session, price_id: int) -> bool:
        """Delete an intraday price record.

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
            price_record: StockIntradayPrice = PriceService.get_intraday_price_or_404(
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
                "timestamp": price_record.timestamp.isoformat(),
            }

            # Delete price record
            session.delete(price_record)
            session.commit()

            # Emit WebSocket event
            EventService.emit_price_update(
                action="deleted",
                price_data=(
                    price_data if isinstance(price_data, dict) else price_data[0]
                ),
                stock_symbol=stock_symbol,
            )

        except Exception as e:
            logger.exception("Error deleting intraday price")
            session.rollback()
            if isinstance(e, ResourceNotFoundError):
                raise
            PriceService._raise_business_error(
                f"Could not delete intraday price record: {e!s}",
            )
        return True

    # Bulk import operations
    @staticmethod
    def _validate_daily_price_data(item: dict[str, any]) -> None:
        """Validate a single daily price data item."""
        if "price_date" not in item:
            PriceService._raise_validation_error(
                "Each price data item must include a 'price_date'",
            )

        if (
            "high_price" in item
            and "low_price" in item
            and item["high_price"] < item["low_price"]
        ):
            date_str: str = item["price_date"]
            PriceService._raise_validation_error(
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
                price_date = datetime.strptime(
                    price_date + " +0000",
                    "%Y-%m-%d %z",
                ).date()
            except ValueError:
                PriceService._raise_validation_error(
                    f"Invalid date format: {price_date}. Expected YYYY-MM-DD",
                )

        # Check if price already exists for this date
        existing: StockDailyPrice | None = PriceService.get_daily_price_by_date(
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
        """Bulk import daily price records."""
        try:
            # Verify stock exists
            stock: Stock | None = session.execute(
                select(Stock).where(Stock.id == stock_id),
            ).scalar_one_or_none()
            if not stock:
                PriceService._raise_not_found(stock_id, "Stock")

            # Validate all price data first
            for item in price_data:
                PriceService._validate_daily_price_data(item)

            # Create price records
            created_records: list[StockDailyPrice] = []
            for item in price_data:
                price_record = PriceService._create_daily_price_record(
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
            PriceService._raise_business_error(
                f"Could not bulk import daily prices: {e!s}",
                e,
            )
        return created_records

    @staticmethod
    def _validate_intraday_price_data(item: dict[str, any]) -> None:
        """Validate a single intraday price data item."""
        if "timestamp" not in item:
            PriceService._raise_validation_error(
                "Each price data item must include a 'timestamp'",
            )

        if (
            "high_price" in item
            and "low_price" in item
            and item["high_price"] < item["low_price"]
        ):
            time_str: str = item["timestamp"]
            PriceService._raise_validation_error(
                f"High price cannot be less than low price for timestamp {time_str}",
            )

    @staticmethod
    def _create_intraday_price_record(
        session: Session,
        stock_id: int,
        item: dict[str, any],
    ) -> StockIntradayPrice | None:
        """Create a single intraday price record."""
        # Parse timestamp if it's a string
        timestamp: datetime = item["timestamp"]
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.strptime(
                    timestamp + " +0000",
                    "%Y-%m-%d %H:%M:%S %z",
                )
            except ValueError:
                PriceService._raise_validation_error(
                    f"Invalid timestamp format: {timestamp}",
                )

        # Get interval, default to 1 minute
        interval: int = item.get("interval", 1)

        # Check if price already exists for this timestamp & interval
        existing: StockIntradayPrice | None = (
            PriceService.get_intraday_price_by_timestamp(
                session,
                stock_id,
                timestamp,
                interval,
            )
        )
        if existing:
            logger.warning(
                "Skipping existing intraday price record for stock ID %s at %s",
                stock_id,
                timestamp,
            )
            return None

        # Create data dict
        create_data: dict[str, any] = {
            "stock_id": stock_id,
            "timestamp": timestamp,
            "interval": interval,
        }
        create_data.update(
            {k: v for k, v in item.items() if k not in ["timestamp", "interval"]},
        )

        # Create price record
        return StockIntradayPrice.from_dict(create_data)

    @staticmethod
    def bulk_import_intraday_prices(
        session: Session,
        stock_id: int,
        price_data: list[dict[str, any]],
    ) -> list[StockIntradayPrice]:
        """Bulk import intraday price records."""
        try:
            # Verify stock exists
            stock: Stock | None = session.execute(
                select(Stock).where(Stock.id == stock_id),
            ).scalar_one_or_none()
            if not stock:
                PriceService._raise_not_found(stock_id, "Stock")

            # Validate all price data first
            for item in price_data:
                PriceService._validate_intraday_price_data(item)

            # Create price records
            created_records: list[StockIntradayPrice] = []
            for item in price_data:
                price_record: StockIntradayPrice | None = (
                    PriceService._create_intraday_price_record(
                        session,
                        stock_id,
                        item,
                    )
                )
                if price_record:
                    session.add(price_record)
                    created_records.append(price_record)

            session.commit()

            # Emit events for created records
            for record in created_records:
                dumped_data: dict[str, any] = intraday_price_schema.dump(record)
                EventService.emit_price_update(
                    action="created",
                    price_data=(
                        dumped_data if isinstance(dumped_data, dict) else dumped_data[0]
                    ),
                    stock_symbol=stock.symbol,
                )

        except Exception as e:
            logger.exception("Error bulk importing intraday prices")
            session.rollback()
            if isinstance(e, (ValidationError, ResourceNotFoundError)):
                raise
            PriceService._raise_business_error(
                f"Could not bulk import intraday prices: {e!s}",
                e,
            )

        return created_records

    # Technical Indicators for Trading Decisions
    @staticmethod
    def calculate_simple_moving_average(
        prices: list[float],
        period: int = DEFAULT_MA_PERIOD,
    ) -> float | None:
        """Calculate simple moving average for a list of prices.

        Args:
            prices: List of prices (oldest to newest)
            period: SMA period

        Returns:
            SMA value if enough data points available, None otherwise

        """
        if len(prices) < period:
            return None

        return sum(prices[-period:]) / period

    @staticmethod
    def calculate_moving_averages_for_stock(
        session: Session,
        stock_id: int,
        periods: list[int] = [5, 10, 20, 50, 200] | [],
    ) -> dict[int, float | None]:
        """Calculate multiple moving averages for a stock.

        Args:
            session: Database session
            stock_id: Stock ID
            periods: List of MA periods to calculate

        Returns:
            Dictionary mapping period to MA value

        """
        # Get the last 200 days of data (or the maximum period in periods)
        max_period: int = max(periods)
        end_date: date = get_current_date()
        start_date: date = end_date - timedelta(days=max_period * 2)

        # Get prices
        prices: list[StockDailyPrice] = PriceService.get_daily_prices_by_date_range(
            session,
            stock_id,
            start_date,
            end_date,
        )

        # Extract closing prices
        close_prices: list[float] = [
            price.close_price for price in prices if price.close_price is not None
        ]

        # Calculate MAs for each period
        result: dict[int, float | None] = {}
        for period in periods:
            result[period] = PriceService.calculate_simple_moving_average(
                close_prices,
                period,
            )

        return result

    @staticmethod
    def calculate_rsi(prices: list[float], period: int = 14) -> float | None:
        """Calculate Relative Strength Index (RSI) for a list of prices.

        Args:
            prices: List of prices (oldest to newest)
            period: RSI period

        Returns:
            RSI value if enough data points available, None otherwise

        """
        if len(prices) < period + 1:
            return None

        # Calculate price changes
        changes: list[float] = [
            prices[i + 1] - prices[i] for i in range(len(prices) - 1)
        ]

        # Separate gains and losses
        gains: list[float] = [max(0, change) for change in changes]
        losses: list[float] = [max(0, -change) for change in changes]

        # Calculate average gain and loss
        avg_gain: float = sum(gains[-period:]) / period
        avg_loss: float = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0

        rs: float = avg_gain / avg_loss
        rsi: float = 100 - (100 / (1 + rs))

        return rsi

    @staticmethod
    def calculate_bollinger_bands(
        prices: list[float],
        period: int = DEFAULT_BB_PERIOD,
        num_std: float = 2.0,
    ) -> dict[str, float | None]:
        """Calculate Bollinger Bands for a list of prices.

        Args:
            prices: List of prices (oldest to newest)
            period: Period for SMA calculation
            num_std: Number of standard deviations for bands

        Returns:
            Dictionary with 'upper', 'middle', and 'lower' band values

        """
        if len(prices) < period:
            return {"upper": None, "middle": None, "lower": None}

        # Calculate SMA
        sma: float | None = PriceService.calculate_simple_moving_average(prices, period)

        # Early return if SMA is None
        if sma is None:
            return {"upper": None, "middle": None, "lower": None}

        # Calculate standard deviation
        recent_prices: list[float] = prices[-period:]
        std_dev: float = (
            sum((price - sma) ** 2 for price in recent_prices) / period
        ) ** 0.5

        # Calculate bands
        upper_band: float = sma + (std_dev * num_std)
        lower_band: float = sma - (std_dev * num_std)

        return {"upper": upper_band, "middle": sma, "lower": lower_band}

    @staticmethod
    def is_price_trending_up(session: Session, stock_id: int, days: int = 10) -> bool:
        """Determine if a stock price is trending upward.

        Args:
            session: Database session
            stock_id: Stock ID
            days: Number of days to analyze

        Returns:
            True if price is trending up, False otherwise

        """
        prices: list[StockDailyPrice] = PriceService.get_latest_daily_prices(
            session,
            stock_id,
            days,
        )

        if len(prices) < PriceService.MIN_DATA_POINTS:  # Need at least 5 data points
            return False

        # Extract closing prices
        close_prices: list[float] = [
            price.close_price for price in prices if price.close_price is not None
        ]
        close_prices.reverse()  # Change to oldest to newest

        if len(close_prices) < PriceService.MIN_DATA_POINTS:
            return False

        # Calculate 5-day and 10-day MAs
        ma5: float | None = PriceService.calculate_simple_moving_average(
            close_prices,
            PriceService.SHORT_MA_PERIOD,
        )

        if len(close_prices) >= PriceService.MEDIUM_MA_PERIOD:
            ma10: float | None = PriceService.calculate_simple_moving_average(
                close_prices,
                PriceService.MEDIUM_MA_PERIOD,
            )
            # 5-day MA above 10-day MA suggests uptrend
            return ma5 is not None and ma10 is not None and ma5 > ma10
        # If not enough data for 10-day MA, check if recent prices are above 5-day
        # MA
        return ma5 is not None and close_prices[-1] > ma5

    @staticmethod
    def _calculate_price_changes(close_prices: list[float]) -> dict[str, float]:
        """Calculate price changes over different periods."""
        price_changes: dict[str, float] = {}
        periods: list[int] = [1, 5, 10, 30, 90]
        for period in periods:
            if len(close_prices) > period:
                change: float = (
                    (close_prices[-1] - close_prices[-(period + 1)])
                    / close_prices[-(period + 1)]
                    * 100
                )
                price_changes[f"{period}_day"] = change
        return price_changes

    @staticmethod
    def _analyze_signals(
        rsi: float | None,
        moving_averages: dict[int, float | None],
        bollinger_bands: dict[str, float | None],
        latest_price: float | None,
    ) -> dict[str, str]:
        """Analyze trading signals from technical indicators."""
        signals: dict[str, str] = {}

        if rsi is not None:
            if rsi < PriceService.RSI_OVERSOLD:
                signals["rsi"] = "oversold"
            elif rsi > PriceService.RSI_OVERBOUGHT:
                signals["rsi"] = "overbought"
            else:
                signals["rsi"] = "neutral"

        if (
            PriceService.SHORT_MA_PERIOD in moving_averages
            and PriceService.LONG_MA_PERIOD in moving_averages
        ):
            if (
                moving_averages[PriceService.SHORT_MA_PERIOD]
                > moving_averages[PriceService.LONG_MA_PERIOD]
            ):
                signals["ma_crossover"] = "bullish"
            else:
                signals["ma_crossover"] = "bearish"

        if (
            bollinger_bands
            and bollinger_bands["upper"] is not None
            and latest_price is not None
        ):
            if latest_price > bollinger_bands["upper"]:
                signals["bollinger"] = "overbought"
            elif (
                bollinger_bands["lower"] is not None
                and latest_price < bollinger_bands["lower"]
            ):
                signals["bollinger"] = "oversold"
            else:
                signals["bollinger"] = "neutral"

        return signals

    @staticmethod
    def get_price_analysis(session: Session, stock_id: int) -> dict[str, any]:
        """Get comprehensive price analysis for trading decisions.

        Args:
            session: Database session
            stock_id: Stock ID

        Returns:
            Dictionary with various technical indicators and analysis results

        """
        # Get recent price data
        end_date: date = get_current_date()
        start_date: date = end_date - timedelta(days=200)
        prices: list[StockDailyPrice] = PriceService.get_daily_prices_by_date_range(
            session,
            stock_id,
            start_date,
            end_date,
        )

        if not prices:
            return {
                "has_data": False,
                "message": "No price data available for analysis",
            }

        close_prices: list[float] = [
            p.close_price for p in prices if p.close_price is not None
        ]
        if not close_prices:
            return {
                "has_data": False,
                "message": "No closing price data available for analysis",
            }

        latest_price: float = close_prices[-1]

        # Calculate technical indicators
        ma_periods: list[int] = [
            PriceService.SHORT_MA_PERIOD,
            PriceService.MEDIUM_MA_PERIOD,
            PriceService.LONG_MA_PERIOD,
            PriceService.EXTENDED_MA_PERIOD,
            PriceService.MAX_MA_PERIOD,
        ]
        moving_averages: dict[int, float | None] = {
            period: PriceService.calculate_simple_moving_average(close_prices, period)
            for period in ma_periods
            if len(close_prices) >= period
        }

        rsi: float | None = (
            PriceService.calculate_rsi(close_prices)
            if len(close_prices) >= PriceService.RSI_MIN_PERIODS
            else None
        )
        bollinger_bands: dict[str, float | None] = (
            PriceService.calculate_bollinger_bands(close_prices)
            if len(close_prices) >= PriceService.DEFAULT_BB_PERIOD
            else {"upper": None, "middle": None, "lower": None}
        )

        # Compile analysis
        analysis: dict[str, any] = {
            "has_data": True,
            "latest_price": latest_price,
            "moving_averages": moving_averages,
            "rsi": rsi,
            "bollinger_bands": bollinger_bands,
            "is_uptrend": moving_averages.get(
                PriceService.SHORT_MA_PERIOD,
            )
            > moving_averages.get(
                PriceService.LONG_MA_PERIOD,
            )
            if (
                PriceService.SHORT_MA_PERIOD in moving_averages
                and PriceService.LONG_MA_PERIOD in moving_averages
            )
            else None,
            "price_changes": PriceService._calculate_price_changes(close_prices),
            "analysis_date": get_current_date().isoformat(),
            "signals": PriceService._analyze_signals(
                rsi,
                moving_averages,
                bollinger_bands,
                latest_price,
            ),
        }

        return analysis
