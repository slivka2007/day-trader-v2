"""Intraday Prices API resources.

This module provides API endpoints for managing intraday stock prices,
including retrieving, creating, updating, and deleting intraday price records.
"""

from __future__ import annotations

from datetime import datetime

from flask import current_app, request
from flask_jwt_extended import jwt_required
from flask_restx import Model, Namespace, OrderedModel, Resource, fields

from app.api.schemas.intraday_price import (
    intraday_price_delete_schema,
    intraday_price_input_schema,
    intraday_price_schema,
    intraday_prices_schema,
)
from app.models import IntradayInterval, Stock, StockIntradayPrice
from app.services.intraday_price_service import IntradayPriceService
from app.services.session_manager import SessionManager
from app.services.stock_service import StockService
from app.utils.auth import admin_required
from app.utils.constants import ApiConstants, PaginationConstants
from app.utils.errors import (
    BusinessLogicError,
    ResourceNotFoundError,
    ValidationError,
)

# Create namespace
api = Namespace("intraday-prices", description="Intraday stock price operations")

# Define API models
intraday_price_model: Model | OrderedModel = api.model(
    "IntradayPrice",
    {
        "id": fields.Integer(readonly=True, description="Price record identifier"),
        "stock_id": fields.Integer(description="Stock identifier"),
        "stock_symbol": fields.String(description="Stock symbol"),
        "timestamp": fields.DateTime(description="Price timestamp"),
        "interval": fields.Integer(description="Time interval in minutes"),
        "open_price": fields.Float(description="Opening price"),
        "high_price": fields.Float(description="Highest price during the interval"),
        "low_price": fields.Float(description="Lowest price during the interval"),
        "close_price": fields.Float(description="Closing price"),
        "volume": fields.Integer(description="Trading volume"),
        "source": fields.String(description="Price data source"),
        "change": fields.Float(description="Price change from open to close"),
        "change_percent": fields.Float(description="Percentage price change"),
        "is_real_data": fields.Boolean(
            description="Whether price data is from a real source",
        ),
        "is_delayed": fields.Boolean(description="Whether price data is delayed"),
        "is_real_time": fields.Boolean(description="Whether price data is real-time"),
        "created_at": fields.DateTime(description="Creation timestamp"),
        "updated_at": fields.DateTime(description="Last update timestamp"),
    },
)

intraday_price_input_model: Model | OrderedModel = api.model(
    "IntradayPriceInput",
    {
        "stock_id": fields.Integer(required=True, description="Stock identifier"),
        "timestamp": fields.DateTime(required=True, description="Price timestamp"),
        "interval": fields.Integer(
            default=IntradayInterval.ONE_MINUTE.value,
            description="Time interval in minutes",
        ),
        "open_price": fields.Float(description="Opening price"),
        "high_price": fields.Float(description="Highest price during the interval"),
        "low_price": fields.Float(description="Lowest price during the interval"),
        "close_price": fields.Float(description="Closing price"),
        "volume": fields.Integer(description="Trading volume"),
        "source": fields.String(description="Source of the price data"),
    },
)

intraday_price_delete_model: Model | OrderedModel = api.model(
    "IntradayPriceDelete",
    {
        "confirm": fields.Boolean(required=True, description="Deletion confirmation"),
        "price_id": fields.Integer(required=True, description="Price record ID"),
    },
)

intraday_price_bulk_model: Model | OrderedModel = api.model(
    "IntradayPriceBulk",
    {
        "stock_id": fields.Integer(required=True, description="Stock ID"),
        "interval": fields.String(
            description="Time interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h)",
            default=IntradayPriceService.DEFAULT_INTRADAY_INTERVAL,
        ),
        "period": fields.String(
            description="Time period (1d, 5d, 1mo, 3mo)",
            default=IntradayPriceService.DEFAULT_INTRADAY_PERIOD,
        ),
    },
)

intraday_price_list_model: Model | OrderedModel = api.model(
    "IntradayPriceList",
    {
        "items": fields.List(fields.Nested(intraday_price_model)),
        "pagination": fields.Raw(description="Pagination information"),
        "stock_id": fields.Integer(description="The stock ID"),
        "stock_symbol": fields.String(description="The stock symbol"),
    },
)

update_response_model: Model | OrderedModel = api.model(
    "UpdateResponse",
    {
        "success": fields.Boolean(required=True, description="Update success status"),
        "count": fields.Integer(required=True, description="Number of updated records"),
        "message": fields.String(required=True, description="Update message"),
    },
)


@api.route("")
class IntradayPriceList(Resource):
    """API resource for intraday price list operations."""

    @api.doc("list_intraday_prices")
    @api.response(200, "Success", intraday_price_list_model)
    @api.param(
        "stock_id",
        "Filter by stock ID",
        type=int,
    )
    @api.param(
        "start_time",
        "Start time (YYYY-MM-DD HH:MM:SS)",
        type=str,
    )
    @api.param(
        "end_time",
        "End time (YYYY-MM-DD HH:MM:SS)",
        type=str,
    )
    @api.param(
        "interval",
        "Time interval in minutes (1, 5, 15, 30, 60)",
        type=int,
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
        """Get a list of intraday price records with optional filtering."""
        try:
            # Parse request arguments
            stock_id: int | None = request.args.get("stock_id", type=int)
            interval: int = request.args.get(
                "interval",
                type=int,
                default=IntradayInterval.ONE_MINUTE.value,
            )
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

            # Parse datetime arguments
            start_time = None
            end_time = None
            if "start_time" in request.args:
                try:
                    start_time: datetime = datetime.fromisoformat(
                        request.args["start_time"],
                    )
                except ValueError:
                    return {
                        "error": True,
                        "message": "Invalid start_time format. Expected ISO format "
                        "(YYYY-MM-DD HH:MM:SS).",
                    }, ApiConstants.HTTP_BAD_REQUEST

            if "end_time" in request.args:
                try:
                    end_time: datetime = datetime.fromisoformat(
                        request.args["end_time"],
                    )
                except ValueError:
                    return {
                        "error": True,
                        "message": "Invalid end_time format. Expected ISO format "
                        "(YYYY-MM-DD HH:MM:SS).",
                    }, ApiConstants.HTTP_BAD_REQUEST

            # Build query and apply filters
            with SessionManager() as session:
                # Create filter options dictionary
                filter_options: dict[str, any] = {
                    "stock_id": stock_id,
                    "interval": interval,
                    "start_time": start_time,
                    "end_time": end_time,
                }

                # Use the service instead of direct database queries
                paginated_result: dict[str, any] = (
                    IntradayPriceService.get_intraday_prices(
                        session=session,
                        filter_options=filter_options,
                        page=page,
                        per_page=per_page,
                    )
                )

                # Serialize data
                prices_data: list[dict[str, any]] = intraday_prices_schema.dump(
                    paginated_result["items"],
                    many=True,
                )

                result: dict[str, any] = {
                    "items": prices_data,
                    "pagination": {
                        "page": paginated_result["page"],
                        "per_page": paginated_result["per_page"],
                        "total_items": paginated_result["total"],
                        "total_pages": paginated_result["pages"],
                        "has_next": paginated_result["has_next"],
                        "has_prev": paginated_result["has_prev"],
                    },
                }

                # Add stock information if filtered by stock_id
                if stock_id:
                    stock: Stock | None = StockService.get_by_id(session, stock_id)
                    if stock:
                        result["stock_id"] = stock_id
                        result["stock_symbol"] = stock.symbol

                return result, ApiConstants.HTTP_OK

        except ValidationError as e:
            return {
                "error": True,
                "message": str(e),
            }, ApiConstants.HTTP_BAD_REQUEST
        except Exception as e:
            current_app.logger.exception("Error retrieving intraday prices")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR

    @api.doc("create_intraday_price")
    @api.expect(intraday_price_input_model)
    @api.response(201, "Created", intraday_price_model)
    @api.response(400, "Bad Request")
    @jwt_required()
    def post(self) -> any:
        """Create a new intraday price record."""
        try:
            data: dict[str, any] = request.get_json()

            # Validate input data and get model instance
            price_instance: StockIntradayPrice = intraday_price_input_schema.load(data)

            with SessionManager() as session:
                # Verify stock exists
                stock_id: int = price_instance.stock_id
                if not stock_id:
                    return {
                        "error": True,
                        "message": "Missing required field: stock_id",
                    }, ApiConstants.HTTP_BAD_REQUEST

                # Check if stock exists
                StockService.get_or_404(session, stock_id)

                # Create price record using service
                price: StockIntradayPrice = IntradayPriceService.create_intraday_price(
                    session,
                    stock_id,
                    price_instance.__dict__,  # Convert to dict for the service
                )

                # Serialize and return the created record
                return intraday_price_schema.dump(price), ApiConstants.HTTP_CREATED

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
            current_app.logger.exception("Error creating intraday price")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/<int:price_id>")
class IntradayPriceDetail(Resource):
    """API resource for operations on a specific intraday price record."""

    @api.doc("get_intraday_price")
    @api.response(200, "Success", intraday_price_model)
    @api.response(404, "Intraday price not found")
    def get(self, price_id: int) -> any:
        """Get a specific intraday price record by ID."""
        try:
            with SessionManager() as session:
                # Get price using service
                price: StockIntradayPrice = (
                    IntradayPriceService.get_intraday_price_or_404(session, price_id)
                )

                # Serialize and return the price
                return intraday_price_schema.dump(price), ApiConstants.HTTP_OK

        except ResourceNotFoundError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except Exception as e:
            current_app.logger.exception("Error retrieving intraday price")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR

    @api.doc("update_intraday_price")
    @api.expect(intraday_price_input_model)
    @api.response(200, "Success", intraday_price_model)
    @api.response(404, "Intraday price not found")
    @jwt_required()
    @admin_required
    def put(self, price_id: int) -> any:
        """Update an intraday price record."""
        try:
            data: dict[str, any] = request.get_json()

            # Validate input data and get model instance
            price_instance: StockIntradayPrice = intraday_price_input_schema.load(data)

            with SessionManager() as session:
                # Update price using service
                price: StockIntradayPrice = IntradayPriceService.update_intraday_price(
                    session,
                    price_id,
                    price_instance.__dict__,  # Convert to dict for the service
                )

                # Serialize and return the updated price
                return intraday_price_schema.dump(price), ApiConstants.HTTP_OK

        except ValidationError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except ResourceNotFoundError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except Exception as e:
            current_app.logger.exception("Error updating intraday price")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR

    @api.doc("delete_intraday_price")
    @api.expect(intraday_price_delete_model)
    @api.response(200, "Success")
    @api.response(400, "Bad Request")
    @api.response(404, "Price not found")
    @jwt_required()
    @admin_required
    def delete(self, price_id: int) -> any:
        """Delete an intraday price record."""
        try:
            # Parse and validate delete confirmation
            data: dict[str, any] = request.get_json()
            delete_data: dict[str, any] = intraday_price_delete_schema.load(data)

            if (
                not delete_data.get("confirm", False)
                or delete_data.get("price_id") != price_id
            ):
                return {
                    "error": True,
                    "message": "Delete operation must be confirmed with matching "
                    "price_id",
                }, ApiConstants.HTTP_BAD_REQUEST

            with SessionManager() as session:
                # Delete price using service
                IntradayPriceService.delete_intraday_price(session, price_id)

                return {
                    "success": True,
                    "message": f"Intraday price with ID {price_id} deleted "
                    "successfully",
                }, ApiConstants.HTTP_OK

        except ValidationError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except ResourceNotFoundError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except Exception as e:
            current_app.logger.exception("Error deleting intraday price")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/stock/<int:stock_id>")
class StockIntradayPrices(Resource):
    """API resource for intraday prices of a specific stock."""

    @api.doc("get_stock_intraday_prices")
    @api.response(200, "Success", intraday_price_list_model)
    @api.response(404, "Stock not found")
    @api.param(
        "interval",
        "Time interval in minutes (1, 5, 15, 30, 60)",
        type=int,
        default=IntradayInterval.ONE_MINUTE.value,
    )
    @api.param(
        "limit",
        "Number of prices to return",
        type=int,
        default=PaginationConstants.DEFAULT_PER_PAGE,
    )
    def get(self, stock_id: int) -> any:
        """Get latest intraday prices for a specific stock."""
        try:
            # Parse query parameters
            interval = request.args.get(
                "interval",
                type=int,
                default=IntradayInterval.ONE_MINUTE.value,
            )
            limit = request.args.get(
                "limit",
                type=int,
                default=PaginationConstants.DEFAULT_PER_PAGE,
            )

            with SessionManager() as session:
                # Verify stock exists
                stock = StockService.get_or_404(session, stock_id)

                # Get latest prices using service
                prices = IntradayPriceService.get_latest_intraday_prices(
                    session,
                    stock_id,
                    limit,
                    interval,
                )

                # Serialize data
                prices_data = intraday_prices_schema.dump(prices)
                if not isinstance(prices_data, list):
                    prices_data = [prices_data]

                return {
                    "items": prices_data,
                    "stock_id": stock_id,
                    "stock_symbol": stock.symbol,
                    "count": len(prices),
                }, ApiConstants.HTTP_OK

        except ResourceNotFoundError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except Exception as e:
            current_app.logger.exception("Error retrieving stock intraday prices")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/stock/<int:stock_id>/time-range")
class StockIntradayPricesByTimeRange(Resource):
    """API resource for retrieving intraday prices by time range for a stock."""

    @api.doc("get_intraday_prices_by_time_range")
    @api.response(200, "Success", intraday_price_list_model)
    @api.response(404, "Stock not found")
    @api.param("start_time", "Start time (YYYY-MM-DD HH:MM:SS)", required=True)
    @api.param("end_time", "End time (YYYY-MM-DD HH:MM:SS)", required=True)
    @api.param(
        "interval",
        "Time interval in minutes (1, 5, 15, 30, 60)",
        type=int,
        default=IntradayInterval.ONE_MINUTE.value,
    )
    def get(self, stock_id: int) -> any:
        """Get intraday prices for a stock within a time range."""
        try:
            # Validate required parameters
            if "start_time" not in request.args or "end_time" not in request.args:
                missing_params: list[str] = []
                if "start_time" not in request.args:
                    missing_params.append("start_time")
                if "end_time" not in request.args:
                    missing_params.append("end_time")
                return {
                    "error": True,
                    "message": f"Missing required parameter(s): "
                    f"{', '.join(missing_params)}",
                }, ApiConstants.HTTP_BAD_REQUEST

            # Parse time parameters
            start_time: datetime | None = None
            end_time: datetime | None = None
            try:
                start_time = datetime.fromisoformat(request.args["start_time"])
                end_time = datetime.fromisoformat(request.args["end_time"])
            except ValueError:
                return {
                    "error": True,
                    "message": "Invalid time format. Expected ISO format "
                    "(YYYY-MM-DD HH:MM:SS).",
                }, ApiConstants.HTTP_BAD_REQUEST

            # Get the interval parameter
            interval: int = request.args.get(
                "interval",
                type=int,
                default=IntradayInterval.ONE_MINUTE.value,
            )

            with SessionManager() as session:
                # Verify stock exists
                stock: Stock = StockService.get_or_404(session, stock_id)

                # Get prices by time range using the service
                prices: list[StockIntradayPrice] = (
                    IntradayPriceService.get_intraday_prices_by_time_range(
                        session,
                        stock_id,
                        start_time,
                        end_time,
                        interval,
                    )
                )

                # Serialize the data
                prices_data: list[dict[str, any]] = intraday_prices_schema.dump(prices)

                return {
                    "items": prices_data,
                    "stock_id": stock_id,
                    "stock_symbol": stock.symbol,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "interval": interval,
                    "count": len(prices),
                }, ApiConstants.HTTP_OK

        except ResourceNotFoundError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except ValidationError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except Exception as e:
            current_app.logger.exception(
                "Error retrieving intraday prices by time range",
            )
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/stock/<int:stock_id>/update")
class UpdateIntradayPrices(Resource):
    """API resource for updating intraday prices from external sources."""

    @api.doc("update_stock_intraday_prices")
    @api.response(200, "Success", update_response_model)
    @api.response(404, "Stock not found")
    @api.param(
        "interval",
        "Time interval in minutes",
        type=str,
        default=IntradayPriceService.DEFAULT_INTRADAY_INTERVAL,
    )
    @api.param(
        "period",
        "Time period for data",
        type=str,
        default=IntradayPriceService.DEFAULT_INTRADAY_PERIOD,
    )
    @jwt_required()
    @admin_required
    def post(self, stock_id: int) -> any:
        """Update intraday prices for a stock from external sources."""
        try:
            # Parse query parameters
            interval: str = request.args.get(
                "interval",
                type=str,
                default=IntradayPriceService.DEFAULT_INTRADAY_INTERVAL,
            )
            period: str = request.args.get(
                "period",
                type=str,
                default=IntradayPriceService.DEFAULT_INTRADAY_PERIOD,
            )

            with SessionManager() as session:
                # Verify stock exists
                StockService.get_or_404(session, stock_id)

                # Update prices using service
                updated_prices: list[StockIntradayPrice] = (
                    IntradayPriceService.update_stock_intraday_prices(
                        session,
                        stock_id,
                        interval,
                        period,
                    )
                )

                return {
                    "success": True,
                    "count": len(updated_prices),
                    "message": f"Updated {len(updated_prices)} intraday price records",
                }, ApiConstants.HTTP_OK

        except ResourceNotFoundError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except ValidationError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except BusinessLogicError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except Exception as e:
            current_app.logger.exception("Error updating intraday prices")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/stock/<int:stock_id>/update/latest")
class UpdateLatestIntradayPrice(Resource):
    """API resource for updating the latest intraday price."""

    @api.doc("update_latest_intraday_price")
    @api.response(200, "Success", intraday_price_model)
    @api.response(404, "Stock not found")
    @jwt_required()
    @admin_required
    def post(self, stock_id: int) -> any:
        """Update latest intraday price for a stock from external sources."""
        try:
            with SessionManager() as session:
                # Verify stock exists
                stock: Stock = StockService.get_or_404(session, stock_id)

                # Update latest price using service
                price: StockIntradayPrice = (
                    IntradayPriceService.update_latest_intraday_price(
                        session,
                        stock_id,
                    )
                )

                return {
                    "success": True,
                    "message": f"Updated latest intraday price for {stock.symbol}",
                    "price": intraday_price_schema.dump(price),
                }, ApiConstants.HTTP_OK

        except ResourceNotFoundError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except BusinessLogicError as e:
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except Exception as e:
            current_app.logger.exception("Error updating latest intraday price")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR
