"""Intraday price service for managing StockIntradayPrice model operations.

This service encapsulates all database interactions for the StockIntradayPrice model,
providing a clean API for intraday stock price data management operations.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import and_, select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.api.schemas.stock_price import intraday_price_schema
from app.models.enums import IntradayInterval, PriceSource
from app.models.stock import Stock
from app.models.stock_intraday_price import StockIntradayPrice
from app.services.data_providers.yfinance_provider import (
    get_intraday_data,
    get_latest_price,
)
from app.services.events import EventService
from app.utils.current_datetime import get_current_datetime
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


class IntradayPriceService:
    """Service for intraday stock price model operations."""

    # YFinance integration constants
    DEFAULT_INTRADAY_INTERVAL: ClassVar[str] = "1m"
    DEFAULT_INTRADAY_PERIOD: ClassVar[str] = "1d"
    VALID_INTRADAY_INTERVALS: ClassVar[list[str]] = [
        "1m",
        "2m",
        "5m",
        "15m",
        "30m",
        "60m",
        "90m",
        "1h",
    ]
    VALID_INTRADAY_PERIODS: ClassVar[list[str]] = [
        "1d",
        "5d",
        "1mo",
        "3mo",
    ]

    # Mapping of YFinance intervals to our internal interval values
    INTERVAL_MAPPING: ClassVar[dict[str, int]] = {
        "1m": IntradayInterval.ONE_MINUTE.value,
        "2m": 2,
        "5m": IntradayInterval.FIVE_MINUTES.value,
        "15m": IntradayInterval.FIFTEEN_MINUTES.value,
        "30m": IntradayInterval.THIRTY_MINUTES.value,
        "60m": IntradayInterval.ONE_HOUR.value,
        "90m": 90,
        "1h": IntradayInterval.ONE_HOUR.value,
    }

    @staticmethod
    def _raise_not_found(
        price_id: int,
        price_type: str = "Intraday price record",
    ) -> None:
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
    def update_stock_intraday_prices(
        session: Session,
        stock_id: int,
        interval: str = DEFAULT_INTRADAY_INTERVAL,
        period: str = DEFAULT_INTRADAY_PERIOD,
    ) -> list[StockIntradayPrice]:
        """Update intraday price records for a stock.

        This method fetches intraday price data from Yahoo Finance and updates the
        database. It also handles the conversion of YFinance data format to our model
        format.

        Args:
            session: Database session
            stock_id: Stock ID
            interval: Time interval between data points (default: '1m')
                    Options: '1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h'
            period: Time period to fetch data for (default: '1d')
                   Options: '1d', '5d', '1mo', '3mo'

        Returns:
            List of created StockIntradayPrice instances

        Raises:
            ResourceNotFoundError: If stock not found
            StockPriceError: If interval or period is invalid
            BusinessLogicError: For other business logic errors
            APIError: If there's an error fetching data from Yahoo Finance

        """
        try:
            # Validate interval
            if interval not in IntradayPriceService.VALID_INTRADAY_INTERVALS:
                IntradayPriceService._raise_validation_error(
                    f"Invalid interval: {interval}. Valid options are: "
                    f"{', '.join(IntradayPriceService.VALID_INTRADAY_INTERVALS)}",
                )

            # Validate period
            if period not in IntradayPriceService.VALID_INTRADAY_PERIODS:
                IntradayPriceService._raise_validation_error(
                    f"Invalid period: {period}. Valid options are: "
                    f"{', '.join(IntradayPriceService.VALID_INTRADAY_PERIODS)}",
                )

            # Verify stock exists and get symbol
            stock: Stock | None = session.execute(
                select(Stock).where(Stock.id == stock_id),
            ).scalar_one_or_none()
            if not stock:
                IntradayPriceService._raise_not_found(stock_id, "Stock")

            # Fetch intraday data from Yahoo Finance
            intraday_data: list[dict[str, any]] = get_intraday_data(
                stock.symbol,
                interval=interval,
                period=period,
            )
            if not intraday_data:
                logger.warning("No intraday data returned for %s", stock.symbol)
                return []

            # Get the corresponding interval value from our mapping
            interval_value: int = IntradayPriceService.INTERVAL_MAPPING.get(interval, 1)

            # Convert YFinance data format to our model format
            price_data: list[dict[str, any]] = [
                {
                    "timestamp": item["timestamp"],
                    "interval": interval_value,
                    "open_price": item["open"],
                    "high_price": item["high"],
                    "low_price": item["low"],
                    "close_price": item["close"],
                    "volume": item["volume"],
                    "source": PriceSource.DELAYED.value,
                }
                for item in intraday_data
            ]

            # Bulk import the price data
            return IntradayPriceService.bulk_import_intraday_prices(
                session,
                stock_id,
                price_data,
            )

        except (StockError, APIError):
            logger.exception(
                "Error updating intraday prices for stock %s",
                stock_id,
            )
            session.rollback()
            raise
        except Exception as e:
            logger.exception("Error updating intraday prices for stock %s", stock_id)
            session.rollback()
            IntradayPriceService._raise_business_error(
                f"Could not update intraday prices: {e!s}",
                e,
            )

    @staticmethod
    def update_latest_intraday_price(
        session: Session,
        stock_id: int,
    ) -> StockIntradayPrice:
        """Update the latest intraday price record for a stock.

        This method fetches the latest intraday price data from Yahoo Finance and
        updates the database. It also handles the conversion of YFinance data format
        to our model format.

        Args:
            session: Database session
            stock_id: Stock ID

        Returns:
            Created or updated StockIntradayPrice instance

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
                IntradayPriceService._raise_not_found(stock_id, "Stock")

            # Fetch latest price from Yahoo Finance
            price_data: dict[str, any] = get_latest_price(stock.symbol)
            if not price_data:
                IntradayPriceService._raise_business_error(
                    APIError.NO_PRICE_DATA_ERROR + f" for {stock.symbol}",
                )

            # Check if price already exists for this timestamp
            existing: StockIntradayPrice | None = (
                IntradayPriceService.get_intraday_price_by_timestamp(
                    session,
                    stock_id,
                    price_data["timestamp"],
                    interval=IntradayInterval.ONE_MINUTE.value,
                )
            )

            if existing:
                # Update existing price record
                data: dict[str, any] = {
                    "open_price": price_data["open"],
                    "high_price": price_data["high"],
                    "low_price": price_data["low"],
                    "close_price": price_data["close"],
                    "volume": price_data["volume"],
                    "source": PriceSource.REAL_TIME.value,
                }
                return IntradayPriceService.update_intraday_price(
                    session,
                    existing.id,
                    data,
                )
            # Create new price record
            data: dict[str, any] = {
                "open_price": price_data["open"],
                "high_price": price_data["high"],
                "low_price": price_data["low"],
                "close_price": price_data["close"],
                "volume": price_data["volume"],
                "source": PriceSource.REAL_TIME.value,
            }
            return IntradayPriceService.create_intraday_price(
                session,
                stock_id,
                price_data["timestamp"],
                IntradayInterval.ONE_MINUTE.value,
                data,
            )

        except (StockError, APIError):
            logger.exception(
                "Error updating latest intraday price for stock %s",
                stock_id,
            )
            session.rollback()
            raise
        except Exception as e:
            logger.exception(
                "Error updating latest intraday price for stock %s",
                stock_id,
            )
            session.rollback()
            IntradayPriceService._raise_business_error(
                APIError.LATEST_PRICE_ERROR + f": {e!s}",
                e,
            )

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
        price: StockIntradayPrice | None = (
            IntradayPriceService.get_intraday_price_by_id(
                session,
                price_id,
            )
        )
        if not price:
            IntradayPriceService._raise_not_found(price_id)
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
            select(StockIntradayPrice).where(
                and_(
                    StockIntradayPrice.stock_id == stock_id,
                    StockIntradayPrice.timestamp == timestamp,
                    StockIntradayPrice.interval == interval,
                ),
            ),
        ).scalar_one_or_none()

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
                IntradayPriceService._raise_not_found(stock_id, "Stock")

            # Check if price already exists for this timestamp & interval
            existing: StockIntradayPrice | None = (
                IntradayPriceService.get_intraday_price_by_timestamp(
                    session,
                    stock_id,
                    timestamp,
                    interval,
                )
            )
            if existing:
                IntradayPriceService._raise_validation_error(
                    f"Price record already exists for stock ID {stock_id} at "
                    f"{timestamp} with interval {interval}",
                )

            # Validate price data
            if (
                "high_price" in data
                and "low_price" in data
                and data["high_price"] < data["low_price"]
            ):
                IntradayPriceService._raise_validation_error(
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
            IntradayPriceService._raise_business_error(
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
            price_record: StockIntradayPrice = (
                IntradayPriceService.get_intraday_price_or_404(
                    session,
                    price_id,
                )
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
                    IntradayPriceService._raise_validation_error(
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
            IntradayPriceService._raise_business_error(
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
            price_record: StockIntradayPrice = (
                IntradayPriceService.get_intraday_price_or_404(
                    session,
                    price_id,
                )
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
            IntradayPriceService._raise_business_error(
                f"Could not delete intraday price record: {e!s}",
            )
        return True

    # Bulk import operations
    @staticmethod
    def _validate_intraday_price_data(item: dict[str, any]) -> None:
        """Validate a single intraday price data item."""
        if "timestamp" not in item:
            IntradayPriceService._raise_validation_error(
                "Each price data item must include a 'timestamp'",
            )

        if (
            "high_price" in item
            and "low_price" in item
            and item["high_price"] < item["low_price"]
        ):
            time_str: str = item["timestamp"]
            IntradayPriceService._raise_validation_error(
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
                IntradayPriceService._raise_validation_error(
                    f"Invalid timestamp format: {timestamp}",
                )

        # Get interval, default to 1 minute
        interval: int = item.get("interval", 1)

        # Check if price already exists for this timestamp & interval
        existing: StockIntradayPrice | None = (
            IntradayPriceService.get_intraday_price_by_timestamp(
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
        """Bulk import intraday price records.

        Args:
            session: Database session
            stock_id: Stock ID
            price_data: List of price data dictionaries

        Returns:
            List of created StockIntradayPrice instances

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
                IntradayPriceService._raise_not_found(stock_id, "Stock")

            # Validate all price data first
            for item in price_data:
                IntradayPriceService._validate_intraday_price_data(item)

            # Create price records
            created_records: list[StockIntradayPrice] = []
            for item in price_data:
                price_record: StockIntradayPrice | None = (
                    IntradayPriceService._create_intraday_price_record(
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
            IntradayPriceService._raise_business_error(
                f"Could not bulk import intraday prices: {e!s}",
                e,
            )

        return created_records
