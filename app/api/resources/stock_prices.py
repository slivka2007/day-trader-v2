"""Stock Prices API resources.

This module provides API endpoints for managing stock prices, including daily and
intraday price data. It includes endpoints for retrieving, creating, updating, and
deleting price records for stocks.

The module uses the Flask-RESTx framework for building the API and the
Flask-JWT-Extended library for handling JWT authentication.

"""

from __future__ import annotations

from datetime import datetime
from typing import NoReturn

from flask import current_app, request
from flask_jwt_extended import jwt_required
from flask_restx import Model, Namespace, OrderedModel, Resource, fields

from app.api.schemas.stock_price import (
    daily_price_input_schema,
    daily_price_schema,
    daily_prices_schema,
    intraday_price_input_schema,
    intraday_price_schema,
    intraday_prices_schema,
)
from app.models import Stock, StockDailyPrice, StockIntradayPrice
from app.models.enums import IntradayInterval
from app.services.price_service import PriceService
from app.services.session_manager import SessionManager
from app.services.stock_service import StockService
from app.utils.auth import admin_required
from app.utils.constants import ApiConstants, PaginationConstants
from app.utils.current_datetime import TIMEZONE, get_current_datetime
from app.utils.errors import (
    BusinessLogicError,
    ResourceNotFoundError,
    StockPriceError,
    ValidationError,
)
from app.utils.query_utils import apply_filters, apply_pagination

# Create namespace
api = Namespace("prices", description="Stock price operations")

# Define API models for daily prices
daily_price_model: Model | OrderedModel = api.model(
    "StockDailyPrice",
    {
        "id": fields.Integer(readonly=True, description="Price record identifier"),
        "stock_id": fields.Integer(description="Stock identifier"),
        "price_date": fields.Date(description="Price date"),
        "open_price": fields.Float(description="Opening price"),
        "high_price": fields.Float(description="High price"),
        "low_price": fields.Float(description="Low price"),
        "close_price": fields.Float(description="Closing price"),
        "adj_close": fields.Float(description="Adjusted closing price"),
        "volume": fields.Integer(description="Trading volume"),
        "source": fields.String(description="Price data source"),
        "change": fields.Float(description="Price change (close - open)"),
        "change_percent": fields.Float(description="Percentage price change"),
        "stock_symbol": fields.String(description="Stock symbol"),
        "created_at": fields.DateTime(description="Creation timestamp"),
        "updated_at": fields.DateTime(description="Last update timestamp"),
    },
)

daily_price_input_model: Model | OrderedModel = api.model(
    "StockDailyPriceInput",
    {
        "price_date": fields.Date(required=True, description="Trading date"),
        "open_price": fields.Float(description="Opening price"),
        "high_price": fields.Float(description="Highest price"),
        "low_price": fields.Float(description="Lowest price"),
        "close_price": fields.Float(description="Closing price"),
        "adj_close": fields.Float(description="Adjusted closing price"),
        "volume": fields.Integer(description="Trading volume"),
        "source": fields.String(description="Price data source"),
    },
)

# Define API models for intraday prices
intraday_price_model: Model | OrderedModel = api.model(
    "StockIntradayPrice",
    {
        "id": fields.Integer(readonly=True, description="Price record identifier"),
        "stock_id": fields.Integer(description="Stock identifier"),
        "timestamp": fields.DateTime(description="Price timestamp"),
        "interval": fields.Integer(description="Time interval in minutes"),
        "open_price": fields.Float(description="Opening price"),
        "high_price": fields.Float(description="High price"),
        "low_price": fields.Float(description="Low price"),
        "close_price": fields.Float(description="Closing price"),
        "volume": fields.Integer(description="Trading volume"),
        "source": fields.String(description="Price data source"),
        "change": fields.Float(description="Price change (close - open)"),
        "change_percent": fields.Float(description="Percentage price change"),
        "stock_symbol": fields.String(description="Stock symbol"),
        "created_at": fields.DateTime(description="Creation timestamp"),
        "updated_at": fields.DateTime(description="Last update timestamp"),
    },
)

intraday_price_input_model: Model | OrderedModel = api.model(
    "StockIntradayPriceInput",
    {
        "timestamp": fields.DateTime(required=True, description="Trading timestamp"),
        "interval": fields.Integer(description="Time interval in minutes"),
        "open_price": fields.Float(description="Opening price"),
        "high_price": fields.Float(description="Highest price"),
        "low_price": fields.Float(description="Lowest price"),
        "close_price": fields.Float(description="Closing price"),
        "volume": fields.Integer(description="Trading volume"),
        "source": fields.String(description="Price data source"),
    },
)

# Add pagination models
pagination_model: Model | OrderedModel = api.model(
    "Pagination",
    {
        "page": fields.Integer(description="Current page number"),
        "page_size": fields.Integer(description="Number of items per page"),
        "total_items": fields.Integer(description="Total number of items"),
        "total_pages": fields.Integer(description="Total number of pages"),
        "has_next": fields.Boolean(description="Whether there is a next page"),
        "has_prev": fields.Boolean(description="Whether there is a previous page"),
    },
)

daily_price_list_model: Model | OrderedModel = api.model(
    "DailyPriceList",
    {
        "items": fields.List(
            fields.Nested(daily_price_model),
            description="List of daily prices",
        ),
        "pagination": fields.Nested(
            pagination_model,
            description="Pagination information",
        ),
        "stock_symbol": fields.String(description="Stock symbol"),
        "stock_id": fields.Integer(description="Stock ID"),
    },
)

intraday_price_list_model: Model | OrderedModel = api.model(
    "IntradayPriceList",
    {
        "items": fields.List(
            fields.Nested(intraday_price_model),
            description="List of intraday prices",
        ),
        "pagination": fields.Nested(
            pagination_model,
            description="Pagination information",
        ),
        "stock_symbol": fields.String(description="Stock symbol"),
        "stock_id": fields.Integer(description="Stock ID"),
    },
)


def _validate_price_date(price_date_value: str | datetime.date | None) -> datetime.date:
    """Validate and convert price date value."""
    if not price_date_value:
        _raise_missing_date()

    if isinstance(price_date_value, str):
        try:
            return (
                datetime.strptime(price_date_value, "%Y-%m-%d")
                .astimezone(TIMEZONE)
                .date()
            )
        except ValueError as err:
            _raise_invalid_date_format(err)

    # Check if date is in the future
    current_date: datetime.date = get_current_datetime().date()
    if price_date_value > current_date:
        _raise_future_date(price_date_value)

    return price_date_value


def _raise_missing_date() -> NoReturn:
    raise ValidationError(StockPriceError.MISSING_PRICE_DATE)


def _raise_invalid_date_format(err: Exception) -> NoReturn:
    raise ValidationError(StockPriceError.INVALID_DATE_FORMAT) from err


def _raise_future_date(date_value: datetime.date) -> NoReturn:
    raise ValidationError(StockPriceError.FUTURE_DATE.format(date_value))


def _raise_missing_interval() -> NoReturn:
    raise ValidationError(StockPriceError.MISSING_PRICE_INTERVAL)


def _validate_timestamp(timestamp_value: str | datetime | None) -> datetime:
    """Validate and convert timestamp value with timezone."""
    if not timestamp_value:
        _raise_missing_timestamp()

    if isinstance(timestamp_value, str):
        try:
            # Add timezone info if not already present
            naive_timestamp: datetime = datetime.fromisoformat(
                timestamp_value.replace("Z", "+00:00"),
            )
            if naive_timestamp.tzinfo is None:
                return naive_timestamp.replace(tzinfo=TIMEZONE)
            timestamp_value = naive_timestamp
        except ValueError as err:
            _raise_invalid_datetime_format(err)

    # If we got a datetime object directly, ensure it has timezone
    if hasattr(timestamp_value, "tzinfo") and timestamp_value.tzinfo is None:
        return timestamp_value.replace(tzinfo=TIMEZONE)

    # Check if timestamp is in the future
    current_time: datetime = get_current_datetime()
    if timestamp_value > current_time:
        _raise_future_timestamp(timestamp_value)

    return timestamp_value


def _raise_missing_timestamp() -> NoReturn:
    raise ValidationError(StockPriceError.MISSING_PRICE_TIMESTAMP)


def _raise_invalid_datetime_format(err: Exception) -> NoReturn:
    raise ValidationError(StockPriceError.INVALID_DATETIME_FORMAT) from err


def _raise_future_timestamp(timestamp_value: datetime) -> NoReturn:
    raise ValidationError(StockPriceError.FUTURE_TIMESTAMP.format(timestamp_value))


def _raise_invalid_interval(interval: int) -> NoReturn:
    raise ValidationError(
        StockPriceError.INVALID_INTERVAL.format(
            IntradayInterval.get_name(interval),
        ),
    )


@api.route("/daily/stocks/<int:stock_id>")
@api.param("stock_id", "The stock identifier")
@api.response(ApiConstants.HTTP_NOT_FOUND, "Stock not found")
class StockDailyPrices(Resource):
    """Resource for daily price data for a specific stock."""

    @api.doc(
        "get_daily_prices",
        params={
            "page": f"Page number (default: {PaginationConstants.DEFAULT_PAGE})",
            "page_size": (
                f"Number of items per page (default: "
                f"{PaginationConstants.DEFAULT_PER_PAGE}, "
                f"max: {PaginationConstants.MAX_PER_PAGE})"
            ),
            "start_date": "Filter by start date (format: YYYY-MM-DD)",
            "end_date": "Filter by end date (format: YYYY-MM-DD)",
            "sort": "Sort field (e.g., price_date)",
            "order": "Sort order (asc or desc, default: desc for dates)",
        },
    )
    @api.marshal_with(daily_price_list_model)
    @api.response(ApiConstants.HTTP_OK, "Success")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Stock not found")
    def get(self, stock_id: int) -> dict[str, any]:
        """Get daily price data for a specific stock with filtering and pagination."""
        with SessionManager() as session:
            # Verify stock exists
            stock: Stock = StockService.get_or_404(session, stock_id)

            # Parse date filters
            start_date: any = None
            end_date: any = None

            if "start_date" in request.args:
                try:
                    start_date = _validate_price_date(request.args["start_date"])
                except ValueError as err:
                    raise ValidationError(StockPriceError.INVALID_DATE_FORMAT) from err

            if "end_date" in request.args:
                try:
                    end_date = _validate_price_date(request.args["end_date"])
                except ValueError as err:
                    raise ValidationError(StockPriceError.INVALID_DATE_FORMAT) from err

            # Get price data using the service
            if start_date or end_date:
                daily_prices: list[StockDailyPrice] = (
                    PriceService.get_daily_prices_by_date_range(
                        session=session,
                        stock_id=stock_id,
                        start_date=(
                            start_date or datetime.astimezone(TIMEZONE).min.date()
                        ),
                        end_date=end_date,
                    )
                )
            else:
                # Default to getting the last 30 days of prices
                daily_prices = PriceService.get_latest_daily_prices(
                    session=session,
                    stock_id=stock_id,
                )

            # Apply additional filters
            daily_prices = apply_filters(daily_prices, StockDailyPrice)

            # Default sort by date descending if not specified
            if "sort" not in request.args:
                daily_prices = sorted(
                    daily_prices,
                    key=lambda x: x.price_date,
                    reverse=True,
                )

            # Apply pagination
            result: dict[str, any] = apply_pagination(
                daily_prices,
                default_page_size=PaginationConstants.DEFAULT_PER_PAGE,
            )

            # Add stock information to response
            result["stock_symbol"] = stock.symbol
            result["stock_id"] = stock_id

            # Serialize the results
            result["items"] = daily_prices_schema.dump(result["items"])

            return result

    @api.doc("create_daily_price")
    @api.expect(daily_price_input_model)
    @api.marshal_with(daily_price_model)
    @api.response(ApiConstants.HTTP_CREATED, "Price record created")
    @api.response(ApiConstants.HTTP_BAD_REQUEST, "Invalid input")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Stock not found")
    @api.response(
        ApiConstants.HTTP_CONFLICT,
        "Price record already exists for this date",
    )
    @jwt_required()
    @admin_required
    def post(self, stock_id: int) -> tuple[dict[str, any], int]:
        """Add a new daily price record for a stock. Requires admin privileges."""
        data: dict[str, any] = request.json

        try:
            # Validate and load input data
            data_dict: dict[str, any] = data if isinstance(data, dict) else {}
            validated_data: dict[str, any] = daily_price_input_schema.load(data_dict)

            with SessionManager() as session:
                # Parse the price date
                price_date: datetime.date | None = None
                if validated_data and "price_date" in validated_data:
                    price_date = _validate_price_date(validated_data.get("price_date"))

                if not price_date:
                    _raise_missing_date()

                # Create the price record using the service
                price_record: StockDailyPrice = PriceService.create_daily_price(
                    session=session,
                    stock_id=stock_id,
                    price_date=price_date,
                    data=data_dict,
                )

                return daily_price_schema.dump(price_record), ApiConstants.HTTP_CREATED

        except ValidationError as e:
            current_app.logger.exception(
                "Validation error creating price record",
            )
            raise e from e
        except ResourceNotFoundError as e:
            raise e from e
        except BusinessLogicError as e:
            current_app.logger.exception("Business logic error")
            raise e from e
        except Exception as e:
            current_app.logger.exception("Error creating price record")
            raise ValidationError(str(e)) from e


@api.route("/intraday/stocks/<int:stock_id>")
@api.param("stock_id", "The stock identifier")
@api.response(ApiConstants.HTTP_NOT_FOUND, "Stock not found")
class StockIntradayPrices(Resource):
    """Resource for intraday price data for a specific stock."""

    @api.doc(
        "get_intraday_prices",
        params={
            "page": f"Page number (default: {PaginationConstants.DEFAULT_PAGE})",
            "page_size": (
                f"Number of items per page (default: "
                f"{PaginationConstants.DEFAULT_PER_PAGE}, "
                f"max: {PaginationConstants.MAX_PER_PAGE})"
            ),
            "start_time": "Filter by start timestamp (format: YYYY-MM-DD HH:MM:SS)",
            "end_time": "Filter by end timestamp (format: YYYY-MM-DD HH:MM:SS)",
            "interval": "Filter by interval in minutes (1, 5, 15, 30, 60)",
            "sort": "Sort field (e.g., timestamp)",
            "order": "Sort order (asc or desc, default: desc for timestamps)",
        },
    )
    @api.marshal_with(intraday_price_list_model)
    @api.response(ApiConstants.HTTP_OK, "Success")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Stock not found")
    def get(self, stock_id: int) -> dict[str, any]:
        """Get intraday price data for a specific stock.

        Args:
            stock_id (int): The stock identifier

        Returns:
            dict: A dictionary containing the intraday price data

        """
        with SessionManager() as session:
            # Verify stock exists
            stock: Stock = StockService.get_or_404(session, stock_id)

            # Parse timestamp filters
            start_time = None
            end_time = None
            interval_val = IntradayInterval.ONE_MINUTE.value

            if "start_time" in request.args:
                try:
                    start_time = _validate_timestamp(request.args["start_time"])
                except ValueError as err:
                    raise ValidationError(
                        StockPriceError.INVALID_DATETIME_FORMAT,
                    ) from err

            if "end_time" in request.args:
                try:
                    end_time = _validate_timestamp(request.args["end_time"])
                except ValueError as err:
                    raise ValidationError(
                        StockPriceError.INVALID_DATETIME_FORMAT,
                    ) from err

            # Apply interval filter if provided
            if "interval" in request.args:
                try:
                    interval_val = int(request.args["interval"])
                    if interval_val not in IntradayInterval.valid_values():
                        _raise_invalid_interval(interval_val)
                except ValueError as err:
                    raise ValidationError(StockPriceError.INVALID_INTERVAL) from err

            # Get price data using the service
            if start_time or end_time:
                intraday_prices = PriceService.get_intraday_prices_by_time_range(
                    session=session,
                    stock_id=stock_id,
                    start_time=start_time or datetime.min.replace(tzinfo=TIMEZONE),
                    end_time=end_time,
                    interval=interval_val,
                )
            else:
                # Default to getting the last 8 hours of prices
                intraday_prices = PriceService.get_latest_intraday_prices(
                    session=session,
                    stock_id=stock_id,
                    interval=interval_val,
                )

            # Apply additional filters
            intraday_prices = apply_filters(intraday_prices, StockIntradayPrice)

            # Default sort by timestamp descending if not specified
            if "sort" not in request.args:
                intraday_prices = sorted(
                    intraday_prices,
                    key=lambda x: x.timestamp,
                    reverse=True,
                )

            # Apply pagination
            result: dict[str, any] = apply_pagination(
                intraday_prices,
                default_page_size=PaginationConstants.DEFAULT_PER_PAGE,
            )

            # Add stock information to response
            result["stock_symbol"] = stock.symbol
            result["stock_id"] = stock_id

            # Serialize the results
            result["items"] = intraday_prices_schema.dump(result["items"])

            return result

    @api.doc("create_intraday_price")
    @api.expect(intraday_price_input_model)
    @api.marshal_with(intraday_price_model)
    @api.response(ApiConstants.HTTP_CREATED, "Price record created")
    @api.response(ApiConstants.HTTP_BAD_REQUEST, "Invalid input")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_FORBIDDEN, "Admin privileges required")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Stock not found")
    @api.response(
        ApiConstants.HTTP_CONFLICT,
        "Price record already exists for this timestamp and interval",
    )
    @jwt_required()
    @admin_required
    def post(self, stock_id: int) -> tuple[dict[str, any], int]:
        """Add a new intraday price record for a stock. Requires admin privileges."""
        data: dict[str, any] = request.json

        try:
            # Validate and load input data
            data_dict: dict[str, any] = data if isinstance(data, dict) else {}
            validated_data: dict[str, any] = intraday_price_input_schema.load(data_dict)

            with SessionManager() as session:
                # Parse the timestamp
                timestamp: datetime.datetime | None = None
                if validated_data and "timestamp" in validated_data:
                    timestamp = _validate_timestamp(validated_data.get("timestamp"))
                else:
                    _raise_missing_timestamp()

                # Get the interval
                interval: int | None = (
                    validated_data.get("interval") if validated_data else None
                )
                if not interval:
                    _raise_missing_interval()

                # Validate interval
                if interval not in IntradayInterval.valid_values():
                    _raise_invalid_interval(interval)

                # Create the intraday price record using the service
                price_record: StockIntradayPrice = PriceService.create_intraday_price(
                    session=session,
                    stock_id=stock_id,
                    timestamp=timestamp,
                    interval=interval,
                    data=data_dict,
                )

                return intraday_price_schema.dump(
                    price_record,
                ), ApiConstants.HTTP_CREATED

        except ValidationError as err:
            current_app.logger.exception("Validation error creating price record")
            raise err from err
        except ResourceNotFoundError as err:
            raise err from err
        except BusinessLogicError as err:
            current_app.logger.exception("Business logic error")
            raise err from err
        except Exception as err:
            current_app.logger.exception("Error creating price record")
            raise ValidationError(str(err)) from err


@api.route("/daily/<int:price_id>")
@api.param("price_id", "The daily price record identifier")
@api.response(ApiConstants.HTTP_NOT_FOUND, "Price record not found")
class DailyPriceItem(Resource):
    """Resource for managing individual daily price records."""

    @api.doc("get_daily_price")
    @api.marshal_with(daily_price_model)
    @api.response(ApiConstants.HTTP_OK, "Success")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Price record not found")
    def get(self, price_id: int) -> dict[str, any]:
        """Get a daily price record by ID."""
        with SessionManager() as session:
            # Use the service to get the price record
            price: StockDailyPrice = PriceService.get_daily_price_or_404(
                session,
                price_id,
            )
            return daily_price_schema.dump(price)

    @api.doc("update_daily_price")
    @api.expect(daily_price_input_model)
    @api.marshal_with(daily_price_model)
    @api.response(ApiConstants.HTTP_OK, "Price record updated")
    @api.response(ApiConstants.HTTP_BAD_REQUEST, "Invalid input")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_FORBIDDEN, "Admin privileges required")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Price record not found")
    @jwt_required()
    @admin_required
    def put(self, price_id: int) -> tuple[dict[str, any], int]:
        """Update a daily price record. Requires admin privileges."""
        data: dict[str, any] = request.json

        # Don't allow changing date or stock
        data_dict: dict[str, any] = data if isinstance(data, dict) else {}
        if data_dict and "price_date" in data_dict:
            del data_dict["price_date"]
        if data_dict and "stock_id" in data_dict:
            del data_dict["stock_id"]

        try:
            with SessionManager() as session:
                # Update the price record using the service
                result: StockDailyPrice = PriceService.update_daily_price(
                    session,
                    price_id,
                    data_dict,
                )
                return daily_price_schema.dump(result)

        except ValidationError as e:
            current_app.logger.exception(
                "Validation error updating price record",
            )
            raise e from e
        except ResourceNotFoundError as e:
            raise e from e
        except BusinessLogicError as e:
            current_app.logger.exception("Business logic error")
            raise e from e
        except Exception as e:
            current_app.logger.exception("Error updating price record")
            raise ValidationError(str(e)) from e

    @api.doc("delete_daily_price")
    @api.response(ApiConstants.HTTP_NO_CONTENT, "Price record deleted")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_FORBIDDEN, "Admin privileges required")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Price record not found")
    @jwt_required()
    @admin_required
    def delete(self, price_id: int) -> tuple[str, int]:
        """Delete a daily price record. Requires admin privileges."""
        try:
            with SessionManager() as session:
                # Delete the price record using the service
                PriceService.delete_daily_price(session, price_id)
                return "", ApiConstants.HTTP_NO_CONTENT

        except ResourceNotFoundError as e:
            raise e from e
        except ValidationError as e:
            current_app.logger.exception("Validation error deleting price record")
            raise BusinessLogicError(str(e)) from e
        except BusinessLogicError as e:
            current_app.logger.exception("Business logic error")
            raise e from e
        except Exception as e:
            current_app.logger.exception("Error deleting price record")
            raise BusinessLogicError(str(e)) from e


@api.route("/intraday/<int:price_id>")
@api.param("price_id", "The intraday price record identifier")
@api.response(ApiConstants.HTTP_NOT_FOUND, "Price record not found")
class IntradayPriceItem(Resource):
    """Resource for managing individual intraday price records."""

    @api.doc("get_intraday_price")
    @api.marshal_with(intraday_price_model)
    @api.response(ApiConstants.HTTP_OK, "Success")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Price record not found")
    def get(self, price_id: int) -> dict[str, any]:
        """Get an intraday price record by ID."""
        with SessionManager() as session:
            # Use the service to get the price record
            price: StockIntradayPrice = PriceService.get_intraday_price_or_404(
                session,
                price_id,
            )
            return intraday_price_schema.dump(price)

    @api.doc("update_intraday_price")
    @api.expect(intraday_price_input_model)
    @api.marshal_with(intraday_price_model)
    @api.response(ApiConstants.HTTP_OK, "Price record updated")
    @api.response(ApiConstants.HTTP_BAD_REQUEST, "Invalid input")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_FORBIDDEN, "Admin privileges required")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Price record not found")
    @jwt_required()
    @admin_required
    def put(self, price_id: int) -> tuple[dict[str, any], int]:
        """Update an intraday price record. Requires admin privileges."""
        data: dict[str, any] = request.json

        # Don't allow changing timestamp, interval, or stock
        data_dict: dict[str, any] = data if isinstance(data, dict) else {}
        if data_dict and "timestamp" in data_dict:
            del data_dict["timestamp"]
        if data_dict and "interval" in data_dict:
            del data_dict["interval"]
        if data_dict and "stock_id" in data_dict:
            del data_dict["stock_id"]

        try:
            with SessionManager() as session:
                # Update the price record using the service
                result: StockIntradayPrice = PriceService.update_intraday_price(
                    session,
                    price_id,
                    data_dict,
                )
                return intraday_price_schema.dump(result)

        except ValidationError as e:
            current_app.logger.exception(
                "Validation error updating price record",
            )
            raise e from e
        except ResourceNotFoundError as e:
            raise e from e
        except BusinessLogicError as e:
            current_app.logger.exception("Business logic error")
            raise e from e
        except Exception as e:
            current_app.logger.exception("Error updating price record")
            raise ValidationError(str(e)) from e

    @api.doc("delete_intraday_price")
    @api.response(ApiConstants.HTTP_NO_CONTENT, "Price record deleted")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_FORBIDDEN, "Admin privileges required")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Price record not found")
    @jwt_required()
    @admin_required
    def delete(self, price_id: int) -> tuple[str, int]:
        """Delete an intraday price record. Requires admin privileges."""
        try:
            with SessionManager() as session:
                # Delete the price record using the service
                PriceService.delete_intraday_price(session, price_id)
                return "", ApiConstants.HTTP_NO_CONTENT

        except ResourceNotFoundError as e:
            raise e from e
        except ValidationError as e:
            current_app.logger.exception("Validation error deleting price record")
            raise BusinessLogicError(str(e)) from e
        except BusinessLogicError as e:
            current_app.logger.exception("Business logic error")
            raise e from e
        except Exception as e:
            current_app.logger.exception("Error deleting price record")
            raise BusinessLogicError(str(e)) from e
