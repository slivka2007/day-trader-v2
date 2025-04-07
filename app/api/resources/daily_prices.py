"""Daily Prices API resources.

This module provides API endpoints for managing daily stock prices, including
retrieving, creating, updating, and deleting price records for stocks.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from flask import current_app, request
from flask_jwt_extended import jwt_required
from flask_restx import Model, Namespace, OrderedModel, Resource, fields

from app.models.stock_daily_price import StockDailyPrice

if TYPE_CHECKING:
    from app.models import Stock, StockDailyPrice

from app.api.schemas.daily_price import (
    daily_price_bulk_schema,
    daily_price_delete_schema,
    daily_price_input_schema,
    daily_price_schema,
    daily_prices_schema,
)
from app.services.daily_price_service import DailyPriceService
from app.services.session_manager import SessionManager
from app.services.stock_service import StockService
from app.utils.auth import admin_required
from app.utils.constants import ApiConstants, PaginationConstants
from app.utils.current_datetime import get_current_date
from app.utils.errors import (
    BusinessLogicError,
    ResourceNotFoundError,
    StockPriceError,
    ValidationError,
)

# Create namespace
api = Namespace("daily-prices", description="Daily stock price operations")

# Define API models
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
        "trading_range": fields.Float(description="Trading range (high - low)"),
        "trading_range_percent": fields.Float(
            description="Trading range as percentage",
        ),
        "is_real_data": fields.Boolean(description="If data is from a real source"),
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

# Specialized model for updates where date is not required
daily_price_update_model: Model | OrderedModel = api.model(
    "StockDailyPriceUpdate",
    {
        "open_price": fields.Float(description="Opening price"),
        "high_price": fields.Float(description="Highest price"),
        "low_price": fields.Float(description="Lowest price"),
        "close_price": fields.Float(description="Closing price"),
        "adj_close": fields.Float(description="Adjusted closing price"),
        "volume": fields.Integer(description="Trading volume"),
        "source": fields.String(description="Price data source"),
    },
)

daily_price_delete_model: Model | OrderedModel = api.model(
    "StockDailyPriceDelete",
    {
        "confirm": fields.Boolean(required=True, description="Deletion confirmation"),
        "price_id": fields.Integer(required=True, description="Price record ID"),
    },
)

daily_price_bulk_model: Model | OrderedModel = api.model(
    "StockDailyPriceBulk",
    {
        "stock_id": fields.Integer(required=True, description="Stock ID"),
        "period": fields.String(
            description="Time period (1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)",
            default="1y",
        ),
    },
)

# Pagination model
pagination_model: Model | OrderedModel = api.model(
    "Pagination",
    {
        "page": fields.Integer(description="Current page number"),
        "per_page": fields.Integer(description="Number of items per page"),
        "total_items": fields.Integer(description="Total number of items"),
        "total_pages": fields.Integer(description="Total number of pages"),
        "has_next": fields.Boolean(description="Whether there is a next page"),
        "has_prev": fields.Boolean(description="Whether there is a previous page"),
    },
)

# Daily price list model for paginated responses
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
        "stock_symbol": fields.String(description="Stock symbol", required=False),
        "stock_id": fields.Integer(description="Stock ID", required=False),
    },
)

technical_analysis_model: Model | OrderedModel = api.model(
    "TechnicalAnalysis",
    {
        "has_data": fields.Boolean(description="Whether analysis has data"),
        "message": fields.String(description="Status message or error"),
        "trend": fields.String(description="Current price trend"),
        "moving_averages": fields.Raw(description="Moving averages values"),
        "rsi": fields.Float(description="Relative Strength Index value"),
        "macd": fields.Raw(description="MACD indicators"),
        "bollinger_bands": fields.Raw(description="Bollinger Bands values"),
    },
)


# API route definitions
@api.route("")
class DailyPriceList(Resource):
    """API resource for daily price list operations."""

    @api.doc("list_daily_prices")
    @api.response(200, "Success", daily_price_list_model)
    @api.param(
        "stock_id",
        "Filter by stock ID",
        type=int,
    )
    @api.param(
        "start_date",
        "Start date (YYYY-MM-DD)",
        type=str,
    )
    @api.param(
        "end_date",
        "End date (YYYY-MM-DD)",
        type=str,
    )
    @api.param(
        "page",
        "Page number (pagination)",
        type=int,
        default=1,
    )
    @api.param(
        "per_page",
        "Items per page",
        type=int,
        default=PaginationConstants.DEFAULT_PER_PAGE,
    )
    def get(self) -> any:
        """Get a list of daily price records with optional filtering."""
        try:
            # Parse query parameters
            stock_id: int | None = request.args.get("stock_id", type=int)
            start_date_str: str | None = request.args.get("start_date")
            end_date_str: str | None = request.args.get("end_date")
            page: int = request.args.get(
                "page",
                default=1,
                type=int,
            )
            per_page: int = request.args.get(
                "per_page",
                default=PaginationConstants.DEFAULT_PER_PAGE,
                type=int,
            )

            # Convert date strings to date objects
            start_date: date | None = None
            end_date: date | None = None
            try:
                if start_date_str:
                    start_date = date.fromisoformat(start_date_str)
                if end_date_str:
                    end_date = date.fromisoformat(end_date_str)
            except ValueError:
                return {
                    "error": True,
                    "message": StockPriceError.INVALID_DATE_FORMAT,
                }, ApiConstants.HTTP_BAD_REQUEST

            # Use the service to get filtered and paginated data
            with SessionManager() as session:
                # Get paginated and filtered prices
                paginated_result: dict[str, any] = (
                    DailyPriceService.get_filtered_daily_prices(
                        session,
                        filters={
                            "stock_id": stock_id,
                            "price_date_min": start_date,
                            "price_date_max": end_date,
                        }
                        if any([stock_id, start_date, end_date])
                        else None,
                        page=page,
                        per_page=per_page,
                    )
                )

                # Serialize data
                prices_data: list[dict[str, any]] = daily_prices_schema.dump(
                    paginated_result["items"],
                )

                # Format the response with consistent structure
                result: dict[str, any] = {
                    "items": prices_data,
                    "pagination": paginated_result["pagination"],
                }

                # Add stock information if filtered by stock_id
                if stock_id:
                    stock: Stock = StockService.get_or_404(session, stock_id)
                    result["stock_id"] = stock_id
                    result["stock_symbol"] = stock.symbol

                return result, ApiConstants.HTTP_OK

        except ValidationError as e:
            return {
                "error": True,
                "message": str(e),
            }, ApiConstants.HTTP_BAD_REQUEST
        except ResourceNotFoundError as e:
            return {
                "error": True,
                "message": str(e),
            }, ApiConstants.HTTP_NOT_FOUND
        except Exception as e:
            current_app.logger.exception("Error retrieving daily prices")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR

    @api.doc("create_daily_price")
    @api.expect(daily_price_input_model)
    @api.response(201, "Created", daily_price_model)
    @api.response(400, "Validation Error")
    @api.response(404, "Stock Not Found")
    @jwt_required()
    @admin_required
    def post(self) -> any:
        """Create a new daily price record."""
        # Get request data
        json_data: dict[str, any] = request.json or {}

        # Validate input
        try:
            # Validate with schema
            data: dict[str, any] = daily_price_input_schema.load(json_data)
            if not isinstance(data, dict):
                data = data.__dict__

            stock_id: int | None = data.get("stock_id")
            price_date: date | None = data.get("price_date")

            # Validate required fields
            if not stock_id or not price_date:
                missing_field: str = "stock_id" if not stock_id else "price_date"
                return {
                    "error": True,
                    "message": StockPriceError.FIELD_REQUIRED.format(key=missing_field),
                }, ApiConstants.HTTP_BAD_REQUEST

            # Create price record
            with SessionManager() as session:
                result: StockDailyPrice = DailyPriceService.create_daily_price(
                    session,
                    stock_id,
                    price_date,
                    data,
                )
                result_data: dict[str, any] = daily_price_schema.dump(result)

                # Ensure stock_id is included in the response
                if "stock_id" not in result_data:
                    result_data["stock_id"] = stock_id

                return result_data, ApiConstants.HTTP_CREATED

        except ValidationError as e:
            return {
                "error": True,
                "message": "Validation error",
                "validation_errors": e.messages,
            }, ApiConstants.HTTP_BAD_REQUEST
        except ResourceNotFoundError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except BusinessLogicError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except Exception as e:
            current_app.logger.exception("Error creating daily price")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/<int:price_id>")
@api.param("price_id", "Daily price record ID")
class DailyPriceDetail(Resource):
    """API resource for operations on a specific daily price record."""

    @api.doc("get_daily_price")
    @api.response(200, "Success", daily_price_model)
    @api.response(404, "Daily Price Not Found")
    def get(self, price_id: int) -> any:
        """Get a specific daily price record by ID."""
        try:
            with SessionManager() as session:
                price: StockDailyPrice = DailyPriceService.get_daily_price_or_404(
                    session,
                    price_id,
                )
                result: dict[str, any] = daily_price_schema.dump(price)
                # Ensure stock_id is included in the response
                if "stock_id" not in result and price.stock_id:
                    result["stock_id"] = price.stock_id
                return result, ApiConstants.HTTP_OK
        except ResourceNotFoundError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except Exception as e:
            current_app.logger.exception("Error getting daily price")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR

    @api.doc("update_daily_price")
    @api.expect(daily_price_update_model)
    @api.response(200, "Success", daily_price_model)
    @api.response(400, "Validation Error")
    @api.response(404, "Daily Price Not Found")
    @jwt_required()
    @admin_required
    def put(self, price_id: int) -> any:
        """Update a daily price record."""
        try:
            # Get and validate request data
            json_data: dict[str, any] = request.json or {}

            # Validate input (partial validation ok for update)
            data: dict[str, any] = daily_price_input_schema.load(
                json_data,
                partial=True,  # Allow missing required fields for updates
            )

            # Update price record using service
            with SessionManager() as session:
                # Use the service method which handles all validation
                result: StockDailyPrice = DailyPriceService.update_daily_price(
                    session,
                    price_id,
                    data,
                )

                # Serialize and return the updated record
                result_data: dict[str, any] = daily_price_schema.dump(result)

                # Ensure stock_id is included in the response
                if "stock_id" not in result_data and result.stock_id:
                    result_data["stock_id"] = result.stock_id

                return result_data, ApiConstants.HTTP_OK

        except ValidationError as e:
            return {
                "error": True,
                "message": "Validation error",
                "validation_errors": e.messages if hasattr(e, "messages") else str(e),
            }, ApiConstants.HTTP_BAD_REQUEST
        except ResourceNotFoundError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except Exception as e:
            current_app.logger.exception("Error updating daily price")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR

    @api.doc("delete_daily_price")
    @api.expect(daily_price_delete_model)
    @api.response(200, "Success")
    @api.response(400, "Validation Error")
    @api.response(404, "Daily Price Not Found")
    @jwt_required()
    @admin_required
    def delete(self, price_id: int) -> any:
        """Delete a daily price record."""
        try:
            json_data: dict[str, any] = request.json or {}

            # Validate deletion confirmation
            validation: dict[str, any] = daily_price_delete_schema.load(json_data)
            if not validation.get("confirm", False):
                return {
                    "error": True,
                    "message": StockPriceError.CONFIRM_DELETION,
                }, ApiConstants.HTTP_BAD_REQUEST

            # Delete price record
            with SessionManager() as session:
                DailyPriceService.delete_daily_price(session, price_id)
                return {
                    "success": True,
                    "message": f"Daily price with ID {price_id} deleted successfully",
                }, ApiConstants.HTTP_OK

        except ValidationError as e:
            return {
                "error": True,
                "message": "Validation error",
                "validation_errors": e.messages,
            }, ApiConstants.HTTP_BAD_REQUEST
        except ResourceNotFoundError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except BusinessLogicError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except Exception as e:
            current_app.logger.exception("Error deleting daily price")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/stock/<int:stock_id>/latest")
@api.param("stock_id", "Stock ID")
class LatestDailyPrices(Resource):
    """API resource for getting the latest daily prices for a stock."""

    @api.doc("get_latest_daily_prices")
    @api.param("days", "Number of days to retrieve", type=int, default=30)
    @api.response(200, "Success", [daily_price_model])
    @api.response(404, "Stock Not Found")
    def get(self, stock_id: int) -> any:
        """Get the latest daily price records for a stock."""
        try:
            # Parse query parameters
            days: int = request.args.get("days", default=30, type=int)

            # Get prices
            with SessionManager() as session:
                # Verify stock exists
                stock: Stock = StockService.get_or_404(session, stock_id)

                # Get latest prices
                prices: list[StockDailyPrice] = (
                    DailyPriceService.get_latest_daily_prices(
                        session,
                        stock.id,
                        days,
                    )
                )
                result_data: list[dict[str, any]] = daily_prices_schema.dump(prices)

                # Ensure each price item includes stock_id
                for item in result_data:
                    if "stock_id" not in item:
                        item["stock_id"] = stock.id

                # Return a consistent format with other endpoints
                result = {
                    "items": result_data,
                    "stock_id": stock.id,
                    "stock_symbol": stock.symbol,
                    "count": len(prices),
                }
                return result, ApiConstants.HTTP_OK

        except ResourceNotFoundError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except Exception as e:
            current_app.logger.exception("Error getting latest daily prices")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/stock/<int:stock_id>/date-range")
@api.param("stock_id", "Stock ID")
class DailyPriceRange(Resource):
    """API resource for getting daily prices for a specific date range."""

    @api.doc("get_daily_prices_by_date_range")
    @api.param("start_date", "Start date (YYYY-MM-DD)", type=str, required=True)
    @api.param("end_date", "End date (YYYY-MM-DD)", type=str)
    @api.response(200, "Success", [daily_price_model])
    @api.response(400, "Bad Request")
    @api.response(404, "Stock Not Found")
    def get(self, stock_id: int) -> any:
        """Get daily price records for a specific date range."""
        try:
            # Parse query parameters
            start_date_str = request.args.get("start_date")
            end_date_str = request.args.get("end_date")

            if not start_date_str:
                return {
                    "error": True,
                    "message": "Start date is required",
                }, ApiConstants.HTTP_BAD_REQUEST

            # Parse dates
            try:
                start_date = date.fromisoformat(start_date_str)
                end_date = (
                    date.fromisoformat(end_date_str)
                    if end_date_str
                    else get_current_date()
                )
            except ValueError:
                return {
                    "error": True,
                    "message": StockPriceError.INVALID_DATE_FORMAT,
                }, ApiConstants.HTTP_BAD_REQUEST

            # Get prices
            with SessionManager() as session:
                # Verify stock exists
                stock: Stock = StockService.get_or_404(session, stock_id)

                # Get prices for date range
                prices: list[StockDailyPrice] = (
                    DailyPriceService.get_daily_prices_by_date_range(
                        session,
                        stock.id,
                        start_date,
                        end_date,
                    )
                )
                result_data: list[dict[str, any]] = daily_prices_schema.dump(prices)

                # Ensure each price item includes stock_id
                for item in result_data:
                    if "stock_id" not in item:
                        item["stock_id"] = stock.id

                # Return a consistent format with other endpoints
                result = {
                    "items": result_data,
                    "stock_id": stock.id,
                    "stock_symbol": stock.symbol,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "count": len(prices),
                }
                return result, ApiConstants.HTTP_OK

        except ResourceNotFoundError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except Exception as e:
            current_app.logger.exception("Error getting daily prices by date range")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/stock/<int:stock_id>/update")
@api.param("stock_id", "Stock ID")
class UpdateDailyPrices(Resource):
    """API resource for updating daily prices from external sources."""

    @api.doc("update_stock_daily_prices")
    @api.expect(daily_price_bulk_model)
    @api.response(200, "Success")
    @api.response(400, "Bad Request")
    @api.response(404, "Stock Not Found")
    @jwt_required()
    @admin_required
    def post(self, stock_id: int) -> any:
        """Update daily price records for a stock by fetching from external sources."""
        try:
            json_data: dict[str, any] = request.json or {}
            data: dict[str, any] = daily_price_bulk_schema.load(json_data)
            period: str = data.get("period", "1y")

            with SessionManager() as session:
                # Verify stock exists
                stock: Stock = StockService.get_or_404(session, stock_id)

                # Update daily prices
                daily_prices: list[StockDailyPrice] = (
                    DailyPriceService.update_stock_daily_prices(
                        session,
                        stock.id,
                        period,
                    )
                )

                return {
                    "success": True,
                    "message": f"Updated {len(daily_prices)} daily price records",
                    "count": len(daily_prices),
                }, ApiConstants.HTTP_OK

        except ValidationError as e:
            return {
                "error": True,
                "message": "Validation error",
                "validation_errors": e.messages,
            }, ApiConstants.HTTP_BAD_REQUEST
        except ResourceNotFoundError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except BusinessLogicError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except Exception as e:
            current_app.logger.exception("Error updating daily prices")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/stock/<int:stock_id>/latest-update")
@api.param("stock_id", "Stock ID")
class UpdateLatestDailyPrice(Resource):
    """API resource for updating the latest daily price."""

    @api.doc("update_latest_daily_price")
    @api.response(200, "Success", daily_price_model)
    @api.response(404, "Stock Not Found")
    @jwt_required()
    @admin_required
    def post(self, stock_id: int) -> any:
        """Update the latest daily price record for a stock."""
        try:
            with SessionManager() as session:
                # Verify stock exists
                stock: Stock = StockService.get_or_404(session, stock_id)

                # Update latest daily price
                latest_price: StockDailyPrice = (
                    DailyPriceService.update_latest_daily_price(
                        session,
                        stock.id,
                    )
                )
                result: dict[str, any] = daily_price_schema.dump(latest_price)
                return result, ApiConstants.HTTP_OK

        except ResourceNotFoundError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except BusinessLogicError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except Exception as e:
            current_app.logger.exception("Error updating latest daily price")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/stock/<int:stock_id>/analysis")
@api.param("stock_id", "Stock ID")
class PriceAnalysis(Resource):
    """API resource for price analysis."""

    @api.doc("get_price_analysis")
    @api.response(200, "Success", technical_analysis_model)
    @api.response(404, "Stock Not Found")
    def get(self, stock_id: int) -> any:
        """Get comprehensive price analysis for a stock."""
        try:
            with SessionManager() as session:
                # Verify stock exists
                stock: Stock = StockService.get_or_404(session, stock_id)

                # Get price analysis
                analysis: dict[str, any] = DailyPriceService.get_price_analysis(
                    session,
                    stock.id,
                )
                return analysis, ApiConstants.HTTP_OK

        except ResourceNotFoundError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except BusinessLogicError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except Exception as e:
            current_app.logger.exception("Error getting price analysis")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR
