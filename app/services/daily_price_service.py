"""Daily price service for managing StockDailyPrice model operations.

This service encapsulates all database interactions for the StockDailyPrice model,
providing a clean API for daily stock price data management operations.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import Select, and_, select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.api.schemas.daily_price import daily_price_schema
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
from app.utils.query_utils import apply_filters, apply_pagination

# Set up logging
logger: logging.Logger = logging.getLogger(__name__)


class DailyPriceService:
    """Service for daily stock price model operations."""

    # YFinance integration constants
    DEFAULT_DAILY_PERIOD: str = "1y"
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

    # Helper methods for error handling
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

        # Use execute and unpack the results properly
        result = session.execute(
            select(StockDailyPrice)
            .where(
                and_(
                    StockDailyPrice.stock_id == stock_id,
                    StockDailyPrice.price_date >= start_date,
                    StockDailyPrice.price_date <= end_date,
                ),
            )
            .order_by(StockDailyPrice.price_date),
        )

        # Extract the StockDailyPrice objects from the result
        # SQLAlchemy 2.0 returns Row objects which need to be unpacked
        return [row[0] for row in result.all()]

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

        # Use execute and unpack the results properly
        result = session.execute(
            select(StockDailyPrice)
            .where(
                and_(
                    StockDailyPrice.stock_id == stock_id,
                    StockDailyPrice.price_date >= start_date,
                    StockDailyPrice.price_date <= end_date,
                ),
            )
            .order_by(StockDailyPrice.price_date.desc()),
        )

        # Extract the StockDailyPrice objects from the result
        # SQLAlchemy 2.0 returns Row objects which need to be unpacked
        return [row[0] for row in result.all()]

    @staticmethod
    def get_filtered_daily_prices(
        session: Session,
        filters: dict[str, any] | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, any]:
        """Get daily prices with filtering and pagination.

        Args:
            session: Database session
            filters: Dictionary of filters, can include stock_id, start_date, end_date
            page: Page number for pagination
            per_page: Items per page

        Returns:
            Dictionary with paginated results and metadata

        """
        # Build base query
        stmt: Select[tuple[StockDailyPrice]] = select(StockDailyPrice)

        # Create filter arguments dictionary
        filter_args: dict[str, any] = filters or {}

        # Apply filters using query_utils
        stmt = apply_filters(stmt, StockDailyPrice, filter_args)

        # Add ordering - simply apply the ordering without checking
        stmt = stmt.order_by(StockDailyPrice.price_date.desc())

        # Use query_utils.apply_pagination
        pagination_info: dict[str, any] = apply_pagination(stmt, page, per_page)

        # Create a count query to get total count efficiently
        from sqlalchemy import func

        count_stmt: Select[tuple[int]] = select(func.count()).select_from(
            StockDailyPrice,
        )
        count_stmt = apply_filters(count_stmt, StockDailyPrice, filter_args)

        # Execute count query
        total: int = session.execute(count_stmt).scalar() or 0

        # Execute paginated query
        items: list[StockDailyPrice] = [
            row[0] for row in session.execute(pagination_info["query"]).all()
        ]

        # Calculate pagination metadata
        total_pages: int = (total + per_page - 1) // per_page if total > 0 else 0

        # Create response
        return {
            "items": items,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_items": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        }

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
            if (
                "high_price" in data
                and "low_price" in data
                and data["high_price"] < data["low_price"]
            ):
                DailyPriceService._raise_validation_error(
                    "High price cannot be less than low price",
                )

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
            # Make sure data is a dictionary
            if not isinstance(data, dict):
                data = (
                    {}
                    if data is None
                    else data.__dict__
                    if hasattr(data, "__dict__")
                    else {}
                )

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

            # Validate price data if provided - check dictionary keys
            if (
                "high_price" in data
                and "low_price" in data
                and data["high_price"] is not None
                and data["low_price"] is not None
                and data["high_price"] < data["low_price"]
            ):
                DailyPriceService._raise_validation_error(
                    "High price cannot be less than low price",
                )

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
                    price_data=price_data,
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

    # External data update operations
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

            # Create data dictionary
            data: dict[str, any] = {
                "open_price": price_data["open"],
                "high_price": price_data["high"],
                "low_price": price_data["low"],
                "close_price": price_data["close"],
                "adj_close": price_data["adjusted_close"],
                "volume": price_data["volume"],
                "source": PriceSource.HISTORICAL.value,
            }

            if existing:
                # Update existing price record
                return DailyPriceService.update_daily_price(session, existing.id, data)
            # Create new price record
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

    # Bulk import helper methods
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
                price_record: StockDailyPrice | None = (
                    DailyPriceService._create_daily_price_record(
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

    # Technical analysis methods
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
        prices: list[StockDailyPrice] = (
            DailyPriceService.get_daily_prices_by_date_range(
                session,
                stock_id,
                start_date,
                end_date,
            )
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

        # Use TechnicalAnalysisService for price analysis
        from app.services.technical_analysis_service import TechnicalAnalysisService

        return TechnicalAnalysisService.get_price_analysis(close_prices)

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
        prices: list[StockDailyPrice] = DailyPriceService.get_latest_daily_prices(
            session,
            stock_id,
            days,
        )

        from app.services.technical_analysis_service import TechnicalAnalysisService

        if len(prices) < TechnicalAnalysisService.MIN_DATA_POINTS:
            return False

        # Extract closing prices
        close_prices: list[float] = [
            price.close_price for price in prices if price.close_price is not None
        ]
        close_prices.reverse()  # Change to oldest to newest

        if len(close_prices) < TechnicalAnalysisService.MIN_DATA_POINTS:
            return False

        # Use TechnicalAnalysisService
        return TechnicalAnalysisService.is_price_trending_up(close_prices)

    @staticmethod
    def calculate_moving_averages_for_stock(
        session: Session,
        stock_id: int,
        periods: list[int] | None = None,
    ) -> dict[int, float | None]:
        """Calculate multiple moving averages for a stock.

        Args:
            session: Database session
            stock_id: Stock ID
            periods: List of MA periods to calculate

        Returns:
            Dictionary mapping period to MA value

        """
        from app.services.technical_analysis_service import TechnicalAnalysisService

        if periods is None:
            periods = [
                TechnicalAnalysisService.SHORT_MA_PERIOD,
                TechnicalAnalysisService.MEDIUM_MA_PERIOD,
                TechnicalAnalysisService.LONG_MA_PERIOD,
                TechnicalAnalysisService.EXTENDED_MA_PERIOD,
                TechnicalAnalysisService.MAX_MA_PERIOD,
            ]

        # Get the last 200 days of data (or the maximum period in periods)
        max_period: int = max(periods)
        end_date: date = get_current_date()
        start_date: date = end_date - timedelta(days=max_period * 2)

        # Get prices
        prices: list[StockDailyPrice] = (
            DailyPriceService.get_daily_prices_by_date_range(
                session,
                stock_id,
                start_date,
                end_date,
            )
        )

        # Extract closing prices
        close_prices: list[float] = [
            price.close_price for price in prices if price.close_price is not None
        ]

        # Use TechnicalAnalysisService to calculate MAs
        return TechnicalAnalysisService.calculate_moving_averages(close_prices, periods)

    # Combined price operations
    @staticmethod
    def update_all_prices(
        session: Session,
        stock_id: int,
        daily_period: str = DEFAULT_DAILY_PERIOD,
        intraday_interval: str = "1m",
        intraday_period: str = "1d",
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
        from app.services.intraday_price_service import IntradayPriceService

        result: dict[str, any] = {
            "daily_prices": None,
            "intraday_prices": None,
            "latest_daily_price": None,
            "latest_intraday_price": None,
        }

        # Update daily prices
        try:
            daily_prices: list[StockDailyPrice] = (
                DailyPriceService.update_stock_daily_prices(
                    session,
                    stock_id,
                    daily_period,
                )
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
            intraday_prices = IntradayPriceService.update_stock_intraday_prices(
                session,
                stock_id,
                intraday_interval,
                intraday_period,
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
            latest_daily: StockDailyPrice = DailyPriceService.update_latest_daily_price(
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
            latest_intraday = IntradayPriceService.update_latest_intraday_price(
                session,
                stock_id,
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
