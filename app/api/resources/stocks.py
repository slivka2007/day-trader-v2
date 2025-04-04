"""Stock API resources.

This module contains the API resources for the stock model.
"""

from __future__ import annotations

from flask import current_app, request
from flask_jwt_extended import jwt_required
from flask_restx import Model, Namespace, OrderedModel, Resource, fields
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.schemas.stock import stock_input_schema, stock_schema, stocks_schema
from app.models import Stock
from app.services.session_manager import SessionManager
from app.services.stock_service import StockService
from app.utils.auth import admin_required
from app.utils.constants import ApiConstants, PaginationConstants
from app.utils.errors import (
    BusinessLogicError,
    StockError,
    ValidationError,
)
from app.utils.query_utils import apply_filters, apply_pagination

# Create namespace
api: Namespace = Namespace("stocks", description="Stock operations")

# Define API models
stock_model: Model | OrderedModel = api.model(
    "Stock",
    {
        "id": fields.Integer(readonly=True, description="Stock identifier"),
        "symbol": fields.String(required=True, description="Stock ticker symbol"),
        "name": fields.String(description="Company name"),
        "is_active": fields.Boolean(description="Whether the stock is active"),
        "sector": fields.String(description="Industry sector"),
        "description": fields.String(description="Stock description"),
        "created_at": fields.DateTime(description="Creation timestamp"),
        "updated_at": fields.DateTime(description="Last update timestamp"),
    },
)

stock_input_model: Model | OrderedModel = api.model(
    "StockInput",
    {
        "symbol": fields.String(required=True, description="Stock ticker symbol"),
        "name": fields.String(description="Company name"),
        "is_active": fields.Boolean(description="Whether the stock is active"),
        "sector": fields.String(description="Industry sector"),
        "description": fields.String(description="Stock description"),
    },
)

# Add pagination model
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

# Add paginated list model
stock_list_model: Model | OrderedModel = api.model(
    "StockList",
    {
        "items": fields.List(fields.Nested(stock_model), description="List of stocks"),
        "pagination": fields.Nested(
            pagination_model,
            description="Pagination information",
        ),
    },
)

# Add search results model
stock_search_model: Model | OrderedModel = api.model(
    "StockSearchResults",
    {
        "results": fields.List(
            fields.Nested(stock_model),
            description="List of matching stocks",
        ),
        "count": fields.Integer(description="Number of results returned"),
    },
)


def _raise_validation_error(message: str, errors: dict | None = None) -> None:
    """Raise a validation error with consistent formatting."""
    raise ValidationError(message, errors=errors)


def _raise_integrity_error(symbol: str) -> None:
    """Raise an error when a stock with the same symbol already exists."""
    raise BusinessLogicError(StockError.SYMBOL_EXISTS.format(symbol))


def _raise_business_error(message: str) -> None:
    """Raise a business logic error with consistent formatting."""
    raise BusinessLogicError(message)


@api.route("/")
class StockList(Resource):
    """Resource for managing the collection of stocks."""

    @api.doc(
        "list_stocks",
        params={
            "page": f"Page number (default: {PaginationConstants.DEFAULT_PAGE})",
            "page_size": (
                f"Number of items per page (default: "
                f"{PaginationConstants.DEFAULT_PER_PAGE}, "
                f"max: {PaginationConstants.MAX_PER_PAGE})"
            ),
            "symbol": "Filter by symbol (exact match)",
            "symbol_like": "Filter by symbol (partial match)",
            "is_active": "Filter by active status (true/false)",
            "sector": "Filter by sector",
            "sort": "Sort field (e.g., symbol, name)",
            "order": "Sort order (asc or desc, default: asc)",
        },
    )
    @api.marshal_with(stock_list_model)
    @api.response(ApiConstants.HTTP_OK, "Success")
    def get(self) -> tuple[dict, int]:
        """Get all stocks with filtering and pagination."""
        with SessionManager() as session:
            # Get base query
            stocks: list[Stock] = (
                session.execute(
                    select(Stock).where(Stock.is_active),
                )
                .scalars()
                .all()
            )

            # Apply filters
            stocks = apply_filters(stocks, Stock)

            # Apply pagination
            result: dict[str, any] = apply_pagination(
                stocks,
                default_page_size=PaginationConstants.DEFAULT_PER_PAGE,
            )

            # Serialize the results
            result["items"] = stocks_schema.dump(result["items"])

            return result, ApiConstants.HTTP_OK

    @api.doc("create_stock")
    @api.expect(stock_input_model)
    @api.marshal_with(stock_model)
    @api.response(ApiConstants.HTTP_CREATED, "Stock created successfully")
    @api.response(ApiConstants.HTTP_BAD_REQUEST, "Invalid input")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_FORBIDDEN, "Admin privileges required")
    @api.response(ApiConstants.HTTP_CONFLICT, "Stock with this symbol already exists")
    @jwt_required()
    @admin_required
    def post(self) -> tuple[dict, int]:
        """Create a new stock. Requires admin privileges."""
        data: dict[str, any] = request.json

        # Validate input data
        try:
            validated_data: dict[str, any] = stock_input_schema.load(data or {})
        except ValidationError as err:
            _raise_validation_error("Invalid stock data", errors=err.to_dict())

        with SessionManager() as session:
            try:
                # Create the stock using the StockService
                stock: Stock = StockService.create_stock(
                    session=session,
                    data=validated_data,
                )

                return stock_schema.dump(stock), ApiConstants.HTTP_CREATED

            except ValidationError as err:
                current_app.logger.exception("Validation error creating stock")
                raise err from err
            except IntegrityError:
                current_app.logger.exception("Stock with symbol already exists")
                _raise_integrity_error(validated_data.get("symbol"))
            except Exception as err:
                current_app.logger.exception("Error creating stock")
                raise ValidationError(str(err)) from err


@api.route("/<int:id>")
@api.param("id", "The stock identifier")
@api.response(ApiConstants.HTTP_NOT_FOUND, "Stock not found")
class StockResource(Resource):
    """Resource for managing individual stocks."""

    @api.doc("get_stock")
    @api.marshal_with(stock_model)
    @api.response(ApiConstants.HTTP_OK, "Success")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Stock not found")
    def get(self, stock_id: int) -> tuple[dict, int]:
        """Get a stock by ID."""
        with SessionManager() as session:
            stock: Stock = StockService.get_or_404(session, stock_id)
            return stock_schema.dump(stock), ApiConstants.HTTP_OK

    @api.doc("update_stock")
    @api.expect(stock_input_model)
    @api.marshal_with(stock_model)
    @api.response(ApiConstants.HTTP_OK, "Stock updated successfully")
    @api.response(ApiConstants.HTTP_BAD_REQUEST, "Invalid input")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_FORBIDDEN, "Admin privileges required")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Stock not found")
    @jwt_required()
    @admin_required
    def put(self, stock_id: int) -> tuple[dict, int]:
        """Update a stock. Requires admin privileges."""
        data: dict[str, any] = request.json

        # Validate input data
        try:
            validated_data: dict[str, any] = stock_input_schema.load(
                data or {},
                partial=True,
            )
        except ValidationError as err:
            _raise_validation_error("Invalid stock data", errors=err.to_dict())

        with SessionManager() as session:
            # Get the stock
            stock: Stock = StockService.get_or_404(session, stock_id)

            try:
                # Update the stock using StockService
                result: Stock = StockService.update_stock(
                    session,
                    stock,
                    validated_data,
                )
                return stock_schema.dump(result), ApiConstants.HTTP_OK

            except ValidationError as err:
                current_app.logger.exception("Validation error updating stock")
                raise err from err
            except Exception as err:
                current_app.logger.exception("Error updating stock")
                raise ValidationError(str(err)) from err

    @api.doc("delete_stock")
    @api.response(ApiConstants.HTTP_NO_CONTENT, "Stock deleted")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_FORBIDDEN, "Admin privileges required")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Stock not found")
    @api.response(ApiConstants.HTTP_CONFLICT, "Cannot delete stock with dependencies")
    @jwt_required()
    @admin_required
    def delete(self, stock_id: int) -> tuple[str, int]:
        """Delete a stock. Requires admin privileges."""
        with SessionManager() as session:
            # Get the stock
            stock: Stock = StockService.get_or_404(session, stock_id)

            try:
                # Delete the stock using StockService
                StockService.delete_stock(session, stock)

            except BusinessLogicError as err:
                current_app.logger.exception("Business logic error deleting stock")
                raise err from err
            except Exception as err:
                current_app.logger.exception("Error deleting stock")
                raise ValidationError(str(err)) from err
        return "", ApiConstants.HTTP_NO_CONTENT


@api.route("/symbol/<string:symbol>")
@api.param("symbol", "The stock symbol")
@api.response(ApiConstants.HTTP_NOT_FOUND, "Stock not found")
class StockBySymbol(Resource):
    """Resource for retrieving stocks by symbol."""

    @api.doc("get_stock_by_symbol")
    @api.marshal_with(stock_model)
    @api.response(ApiConstants.HTTP_OK, "Success")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Stock not found")
    def get(self, symbol: str) -> tuple[dict, int]:
        """Get a stock by symbol."""
        with SessionManager() as session:
            stock = StockService.find_by_symbol_or_404(session, symbol)
            return stock_schema.dump(stock), ApiConstants.HTTP_OK


@api.route("/search")
class StockSearch(Resource):
    """Resource for searching stocks."""

    @api.doc(
        "search_stocks",
        params={
            "q": "Search query string (searches in symbol and name)",
            "limit": "Maximum number of results to return (default: 10)",
        },
    )
    @api.marshal_with(stock_search_model)
    @api.response(ApiConstants.HTTP_OK, "Success")
    def get(self) -> tuple[dict, int]:
        """Search for stocks by symbol or name."""
        query = request.args.get("q", "")
        limit = min(int(request.args.get("limit", 10)), 50)  # Cap at 50 results

        with SessionManager() as session:
            stocks = StockService.search_stocks(session, query, limit)
            results = stocks_schema.dump(stocks)

            return {"results": results, "count": len(results)}, ApiConstants.HTTP_OK


@api.route("/<int:id>/toggle-active")
@api.param("id", "The stock identifier")
@api.response(ApiConstants.HTTP_NOT_FOUND, "Stock not found")
class StockToggleActive(Resource):
    """Resource for toggling a stock's active status."""

    @api.doc("toggle_stock_active")
    @api.marshal_with(stock_model)
    @api.response(ApiConstants.HTTP_OK, "Stock status toggled")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_FORBIDDEN, "Admin privileges required")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Stock not found")
    @jwt_required()
    @admin_required
    def post(self, stock_id: int) -> tuple[dict, int]:
        """Toggle the active status of a stock. Requires admin privileges."""
        with SessionManager() as session:
            # Get the stock
            stock: Stock = StockService.get_or_404(session, stock_id)

            try:
                # Toggle active status using StockService
                result: Stock = StockService.toggle_active(session, stock)
                return stock_schema.dump(result), ApiConstants.HTTP_OK

            except ValidationError as err:
                current_app.logger.exception("Validation error toggling stock status")
                raise err from err
            except Exception as err:
                current_app.logger.exception("Error toggling stock active status")
                raise ValidationError(str(err)) from err
