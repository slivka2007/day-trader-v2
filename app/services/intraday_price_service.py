"""Intraday price service for managing StockIntradayPrice model operations.

This service encapsulates all database interactions for the StockIntradayPrice model,
providing a clean API for intraday stock price data management operations.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import Select, and_, select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


from app.api.schemas.intraday_price import intraday_price_schema
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
from app.utils.query_utils import apply_pagination

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

    # Helper methods for error handling
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
        """Get intraday prices for a stock in a given time range.

        Args:
            session: Database session
            stock_id: Stock ID
            start_time: Start timestamp
            end_time: End timestamp (defaults to current time)
            interval: Time interval in minutes

        Returns:
            List of StockIntradayPrice instances

        """
        if end_time is None:
            end_time = get_current_datetime()

        query = (
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
        )

        # Execute the query and return all results
        result = session.execute(query).all()
        return [row[0] for row in result]

    @staticmethod
    def get_latest_intraday_prices(
        session: Session,
        stock_id: int,
        limit: int = 100,
        interval: int | None = None,
    ) -> list[StockIntradayPrice]:
        """Get latest intraday prices for a stock.

        Args:
            session: Database session
            stock_id: Stock ID
            limit: Maximum number of prices to return
            interval: Optional time interval filter

        Returns:
            List of StockIntradayPrice records ordered by timestamp

        """
        # Build query
        query: Select[tuple[StockIntradayPrice]] = select(StockIntradayPrice).where(
            StockIntradayPrice.stock_id == stock_id,
        )

        # Apply interval filter if specified
        if interval is not None:
            query = query.where(StockIntradayPrice.interval == interval)

        # Order by timestamp descending (newest first) and limit results
        query = query.order_by(
            StockIntradayPrice.timestamp.desc(),
        ).limit(limit)

        # Execute query
        result: list[StockIntradayPrice] = session.execute(query).scalars().all()
        return result

    # Write operations
    @staticmethod
    def create_intraday_price(
        session: Session,
        stock_id: int,
        data: dict[str, any],
    ) -> StockIntradayPrice:
        """Create a new intraday price record.

        Args:
            session: Database session
            stock_id: Stock ID
            data: Dictionary containing intraday price data

        Returns:
            Created StockIntradayPrice instance

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

            # Validate required fields
            timestamp: datetime = data.get("timestamp")

            # Create intraday price record
            intraday_price = StockIntradayPrice(
                stock_id=stock_id,
                timestamp=timestamp,
                interval=data.get("interval", IntradayInterval.ONE_MINUTE.value),
                open_price=data.get("open_price"),
                high_price=data.get("high_price"),
                low_price=data.get("low_price"),
                close_price=data.get("close_price"),
                volume=data.get("volume"),
                source=data.get("source", PriceSource.DELAYED.value),
            )

            # Add to session and commit
            session.add(intraday_price)
            session.commit()

            # Emit event
            dumped_data = intraday_price_schema.dump(intraday_price)
            EventService.emit_price_update(
                action="created",
                price_data=dumped_data,
                stock_symbol=stock.symbol,
                is_intraday=True,
            )

        except Exception as e:
            logger.exception("Error creating intraday price")
            session.rollback()
            if isinstance(e, (ValidationError, ResourceNotFoundError)):
                raise
            IntradayPriceService._raise_business_error(
                f"Could not create intraday price: {e!s}",
                e,
            )
        return intraday_price

    @staticmethod
    def _update_price_fields(price: StockIntradayPrice, data: dict[str, any]) -> None:
        """Update fields of a price record with provided data.

        Args:
            price: StockIntradayPrice instance to update
            data: Dictionary containing updated price data

        """
        # Update fields if provided in data
        if "timestamp" in data:
            price.timestamp = data["timestamp"]
        if "interval" in data:
            price.interval = data["interval"]
        if "open_price" in data:
            price.open_price = data["open_price"]
        if "high_price" in data:
            price.high_price = data["high_price"]
        if "low_price" in data:
            price.low_price = data["low_price"]
        if "close_price" in data:
            price.close_price = data["close_price"]
        if "volume" in data:
            price.volume = data["volume"]
        if "source" in data:
            price.source = data["source"]

    @staticmethod
    def update_intraday_price(
        session: Session,
        price_id: int,
        data: dict[str, any],
    ) -> StockIntradayPrice:
        """Update an existing intraday price record.

        Args:
            session: Database session
            price_id: Price record ID
            data: Dictionary containing updated price data

        Returns:
            Updated StockIntradayPrice instance

        Raises:
            ResourceNotFoundError: If price record not found
            ValidationError: If update data is invalid
            BusinessLogicError: For other business logic errors

        """
        try:
            # Get existing price record
            price: StockIntradayPrice | None = (
                IntradayPriceService.get_intraday_price_or_404(
                    session,
                    price_id,
                )
            )

            # Update fields with provided data
            IntradayPriceService._update_price_fields(price, data)

            # Commit changes
            session.commit()

            # Emit event
            dumped_data = intraday_price_schema.dump(price)
            EventService.emit_price_update(
                action="updated",
                price_data=dumped_data,
                stock_symbol=price.stock.symbol,
                is_intraday=True,
            )

        except Exception as e:
            logger.exception("Error updating intraday price")
            session.rollback()
            if isinstance(e, (ValidationError, ResourceNotFoundError)):
                raise
            IntradayPriceService._raise_business_error(
                f"Could not update intraday price: {e!s}",
                e,
            )
        return price

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

    # External data update operations
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

            # Create data dictionary
            data: dict[str, any] = {
                "open_price": price_data["open"],
                "high_price": price_data["high"],
                "low_price": price_data["low"],
                "close_price": price_data["close"],
                "volume": price_data["volume"],
                "source": PriceSource.REAL_TIME.value,
            }

            if existing:
                # Update existing price record
                return IntradayPriceService.update_intraday_price(
                    session,
                    existing.id,
                    data,
                )
            # Create new price record
            return IntradayPriceService.create_intraday_price(
                session,
                stock_id,
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

    # Bulk import helper methods
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

    # Other query methods
    @staticmethod
    def get_intraday_prices(
        session: Session,
        filter_options: dict[str, any] | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, any]:
        """Get intraday prices with filtering and pagination.

        Args:
            session: Database session
            filter_options: Dictionary of filter options:
                - stock_id: Optional stock ID to filter by
                - interval: Optional interval to filter by
                - start_time: Optional start time to filter by
                - end_time: Optional end time to filter by
            page: Page number for pagination
            per_page: Items per page

        Returns:
            Paginated query result with intraday prices

        """
        # Initialize filter options
        filter_options = filter_options or {}

        # Build query using SQLAlchemy 2.0 style
        stmt = select(StockIntradayPrice)

        # Apply filters
        stock_id = filter_options.get("stock_id")
        interval = filter_options.get("interval")
        start_time = filter_options.get("start_time")
        end_time = filter_options.get("end_time")

        if stock_id:
            stmt = stmt.where(StockIntradayPrice.stock_id == stock_id)
        if interval:
            stmt = stmt.where(StockIntradayPrice.interval == interval)
        if start_time:
            stmt = stmt.where(StockIntradayPrice.timestamp >= start_time)
        if end_time:
            stmt = stmt.where(StockIntradayPrice.timestamp <= end_time)

        # Add ordering
        stmt = stmt.order_by(StockIntradayPrice.timestamp.desc())

        # Apply pagination
        pagination_info = apply_pagination(stmt, page, per_page)

        # Execute query and get results
        items = [row[0] for row in session.execute(pagination_info["query"]).all()]

        # Calculate total count for pagination
        from sqlalchemy import func

        count_stmt = select(func.count()).select_from(StockIntradayPrice)

        # Apply the same filters to the count query
        if stock_id:
            count_stmt = count_stmt.where(StockIntradayPrice.stock_id == stock_id)
        if interval:
            count_stmt = count_stmt.where(StockIntradayPrice.interval == interval)
        if start_time:
            count_stmt = count_stmt.where(StockIntradayPrice.timestamp >= start_time)
        if end_time:
            count_stmt = count_stmt.where(StockIntradayPrice.timestamp <= end_time)

        total = session.execute(count_stmt).scalar() or 0
        total_pages = (total + per_page - 1) // per_page if total > 0 else 0

        return {
            "items": items,
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        }

    # Combined price operations
    @staticmethod
    def update_all_prices(
        session: Session,
        stock_id: int,
        daily_period: str = "1y",  # Default from DailyPriceService
        intraday_interval: str = DEFAULT_INTRADAY_INTERVAL,
        intraday_period: str = DEFAULT_INTRADAY_PERIOD,
    ) -> dict[str, any]:
        """Update all price records (daily and intraday) for a stock.

        Args:
            session: Database session
            stock_id: Stock ID
            daily_period: Time period for daily data
            intraday_interval: Time interval for intraday data
            intraday_period: Time period for intraday data

        Returns:
            Dictionary with results for each operation

        Raises:
            ResourceNotFoundError: If stock not found
            BusinessLogicError: For other business logic errors

        """
        from app.services.daily_price_service import DailyPriceService

        result: dict[str, any] = {
            "daily_prices": None,
            "intraday_prices": None,
            "latest_daily_price": None,
            "latest_intraday_price": None,
        }

        # Update daily prices
        try:
            daily_prices = DailyPriceService.update_stock_daily_prices(
                session,
                stock_id,
                daily_period,
            )
            result["daily_prices"] = {
                "success": True,
                "count": len(daily_prices),
            }
        except Exception as e:
            logger.exception("Error updating daily prices")
            result["daily_prices"] = {
                "success": False,
                "error": str(e),
            }

        # Update intraday prices
        try:
            intraday_prices: list[StockIntradayPrice] = (
                IntradayPriceService.update_stock_intraday_prices(
                    session,
                    stock_id,
                    intraday_interval,
                    intraday_period,
                )
            )
            result["intraday_prices"] = {
                "success": True,
                "count": len(intraday_prices),
            }
        except Exception as e:
            logger.exception("Error updating intraday prices")
            result["intraday_prices"] = {
                "success": False,
                "error": str(e),
            }

        # Update latest daily price
        try:
            latest_daily = DailyPriceService.update_latest_daily_price(
                session,
                stock_id,
            )
            result["latest_daily_price"] = {
                "success": True,
                "date": latest_daily.price_date.isoformat(),
            }
        except Exception as e:
            logger.exception("Error updating latest daily price")
            result["latest_daily_price"] = {
                "success": False,
                "error": str(e),
            }

        # Update latest intraday price
        try:
            latest_intraday: StockIntradayPrice = (
                IntradayPriceService.update_latest_intraday_price(
                    session,
                    stock_id,
                )
            )
            result["latest_intraday_price"] = {
                "success": True,
                "timestamp": latest_intraday.timestamp.isoformat(),
            }
        except Exception as e:
            logger.exception("Error updating latest intraday price")
            result["latest_intraday_price"] = {
                "success": False,
                "error": str(e),
            }

        return result
