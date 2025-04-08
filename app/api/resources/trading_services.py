"""Trading Services API resources."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from flask import current_app, request
from flask_jwt_extended import jwt_required
from flask_restx import Model, Namespace, OrderedModel, Resource, fields

if TYPE_CHECKING:
    from app.models import Stock, StockDailyPrice, TradingService, User

from app.api.schemas.trading_service import (
    service_create_schema,
    service_schema,
    service_update_schema,
    services_schema,
)
from app.services.backtest_service import BacktestService
from app.services.daily_price_service import DailyPriceService
from app.services.session_manager import SessionManager
from app.services.stock_service import StockService
from app.services.trading_service import TradingServiceService
from app.services.trading_strategy_service import TradingStrategyService
from app.utils.auth import get_current_user, require_ownership
from app.utils.constants import (
    ApiConstants,
    PaginationConstants,
    TradingServiceConstants,
)
from app.utils.current_datetime import get_current_date
from app.utils.errors import (
    AuthorizationError,
    BusinessLogicError,
    ResourceNotFoundError,
    ValidationError,
)
from app.utils.query_utils import apply_pagination


# Helper functions for validation
def validate_service_field(field_name: str) -> None:
    """Validate if a required field is present.

    Args:
        field_name: Name of the required field

    Raises:
        ValidationError: When the field is missing

    """
    raise ValidationError(
        ValidationError.FIELD_REQUIRED.format(key=field_name),
    )


def validate_user_authentication(user: User | None) -> None:
    """Validate if user is authenticated.

    Args:
        user: The user to validate

    Raises:
        AuthorizationError: When user is not authenticated

    """
    if not user:
        raise AuthorizationError(AuthorizationError.NOT_AUTHENTICATED)


def validate_resource_exists(resource: str | None, resource_id: int) -> None:
    """Validate if resource exists.

    Args:
        resource: The resource to validate
        resource_id: ID of the resource

    Raises:
        ResourceNotFoundError: When resource is not found

    """
    if not resource:
        raise ResourceNotFoundError(
            ResourceNotFoundError.NOT_FOUND.format(
                resource_type=resource,
                resource_id=resource_id,
            ),
        )


# Create namespace
api = Namespace("services", description="Trading service operations")

# Define models for Swagger documentation
service_model: Model | OrderedModel = api.model(
    "TradingService",
    {
        "id": fields.Integer(readonly=True, description="The service identifier"),
        "user_id": fields.Integer(description="User owning this service"),
        "name": fields.String(required=True, description="Service name"),
        "description": fields.String(description="Service description"),
        "stock_symbol": fields.String(required=True, description="Stock ticker symbol"),
        "state": fields.String(description="Service state (ACTIVE, INACTIVE, etc.)"),
        "mode": fields.String(description="Trading mode (BUY or SELL)"),
        "is_active": fields.Boolean(description="Whether the service is active"),
        "initial_balance": fields.Float(
            required=True,
            description="Initial fund balance",
        ),
        "current_balance": fields.Float(description="Current fund balance"),
        "minimum_balance": fields.Float(description="Minimum fund balance to maintain"),
        "allocation_percent": fields.Float(
            description="Percentage of funds to allocate per trade",
        ),
        "buy_threshold": fields.Float(description="Buy threshold percentage"),
        "sell_threshold": fields.Float(description="Sell threshold percentage"),
        "stop_loss_percent": fields.Float(description="Stop loss percentage"),
        "take_profit_percent": fields.Float(description="Take profit percentage"),
        "current_shares": fields.Float(description="Current shares owned"),
        "buy_count": fields.Integer(description="Total buy transactions"),
        "sell_count": fields.Integer(description="Total sell transactions"),
        "total_gain_loss": fields.Float(description="Total gain/loss amount"),
        "created_at": fields.DateTime(description="Creation timestamp"),
        "updated_at": fields.DateTime(description="Last update timestamp"),
        "is_profitable": fields.Boolean(
            readonly=True,
            description="Whether the service is profitable",
        ),
        "performance_pct": fields.Float(
            readonly=True,
            description="Performance as percentage of initial balance",
        ),
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
service_list_model: Model | OrderedModel = api.model(
    "ServiceList",
    {
        "items": fields.List(
            fields.Nested(service_model),
            description="List of services",
        ),
        "pagination": fields.Nested(
            pagination_model,
            description="Pagination information",
        ),
    },
)

# Define decision model for buy/sell decision endpoints
decision_model: Model | OrderedModel = api.model(
    "TradingDecision",
    {
        "should_proceed": fields.Boolean(
            required=True,
            description="Whether the trading operation should proceed",
        ),
        "reason": fields.String(required=True, description="Reason for the decision"),
        "timestamp": fields.DateTime(required=True, description="Decision timestamp"),
        "details": fields.Raw(description="Additional details about the decision"),
        "service_id": fields.Integer(description="The trading service identifier"),
        "next_action": fields.String(description="Suggested next action"),
    },
)


@api.route("/")
class ServiceList(Resource):
    """Shows a list of all trading services, and lets you create a new service."""

    @api.doc(
        "list_services",
        params={
            "page": f"Page number (default: {PaginationConstants.DEFAULT_PAGE})",
            "page_size": (
                f"Number of items per page (default: "
                f"{PaginationConstants.DEFAULT_PER_PAGE}, "
                f"max: {PaginationConstants.MAX_PER_PAGE})"
            ),
            "is_active": "Filter by active status (true/false)",
            "stock_symbol": "Filter by stock symbol",
            "sort": "Sort field (e.g., created_at, name)",
            "order": "Sort order (asc or desc, default: asc)",
        },
    )
    @api.marshal_with(service_list_model)
    @api.response(ApiConstants.HTTP_OK, "Success")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @jwt_required()
    def get(self) -> tuple[dict[str, any], int]:
        """List all trading services for the authenticated user."""
        try:
            with SessionManager() as session:
                # Get current user
                user: User | None = get_current_user(session)
                validate_user_authentication(user)

                # Get services using the service layer
                services: list[TradingService] = TradingServiceService.get_by_user(
                    session,
                    user.id,
                )

                # Apply pagination using the utility function
                result: dict[str, any] = apply_pagination(services)

                # Serialize the results
                result["items"] = services_schema.dump(result["items"])

                return result, ApiConstants.HTTP_OK

        except ValidationError as e:
            current_app.logger.warning("Validation error listing services: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except AuthorizationError as e:
            current_app.logger.warning("Authorization error listing services: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except Exception as e:
            current_app.logger.exception("Error retrieving trading services")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR

    @api.doc("create_service")
    @api.expect(
        api.model(
            "ServiceCreate",
            {
                "name": fields.String(required=True, description="Service name"),
                "stock_symbol": fields.String(
                    required=True,
                    description="Stock ticker symbol",
                ),
                "description": fields.String(description="Service description"),
                "initial_balance": fields.Float(
                    required=True,
                    description="Initial fund balance",
                ),
                "minimum_balance": fields.Float(
                    description="Minimum fund balance to maintain",
                ),
                "allocation_percent": fields.Float(
                    description="Percentage of funds to allocate per trade",
                ),
                "buy_threshold": fields.Float(description="Buy threshold percentage"),
                "sell_threshold": fields.Float(description="Sell threshold percentage"),
                "stop_loss_percent": fields.Float(description="Stop loss percentage"),
                "take_profit_percent": fields.Float(
                    description="Take profit percentage",
                ),
                "is_active": fields.Boolean(
                    description="Whether the service is active",
                ),
            },
        ),
    )
    @api.marshal_with(service_model)
    @api.response(ApiConstants.HTTP_CREATED, "Service created")
    @api.response(ApiConstants.HTTP_BAD_REQUEST, "Validation error")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @jwt_required()
    def post(self) -> tuple[dict[str, any], int]:
        """Create a new trading service."""
        try:
            data: dict[str, any] = request.json or {}

            # Validate input data
            validated_data: dict[str, any] = service_create_schema.load(data)

            with SessionManager() as session:
                # Get current user
                user: User | None = get_current_user(session)
                validate_user_authentication(user)

                # Create the service using the service layer
                service: TradingService = TradingServiceService.create_service(
                    session=session,
                    user_id=user.id,
                    data=validated_data,
                )

                return service_schema.dump(service), ApiConstants.HTTP_CREATED

        except ValidationError as e:
            error_messages: dict[str, any] = getattr(e, "messages", {})
            current_app.logger.warning(
                "Validation error in service creation: %s",
                error_messages,
            )
            return {
                "error": True,
                "message": str(e),
                "validation_errors": error_messages,
            }, ApiConstants.HTTP_BAD_REQUEST
        except AuthorizationError as e:
            current_app.logger.warning("Authorization error creating service: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except BusinessLogicError as e:
            current_app.logger.exception("Business logic error creating service")
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except Exception as e:
            current_app.logger.exception("Error creating trading service")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/search")
class ServiceSearch(Resource):
    """Search for trading services by name or stock symbol."""

    @api.doc(
        "search_services",
        params={
            "q": "Search query (name or stock symbol)",
            "page": f"Page number (default: {PaginationConstants.DEFAULT_PAGE})",
            "page_size": (
                f"Number of items per page (default: "
                f"{PaginationConstants.DEFAULT_PER_PAGE}, "
                f"max: {PaginationConstants.MAX_PER_PAGE})"
            ),
        },
    )
    @api.marshal_with(service_list_model)
    @api.response(ApiConstants.HTTP_OK, "Success")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @jwt_required()
    def get(self) -> tuple[dict[str, any], int]:
        """Search trading services by name or stock symbol."""
        try:
            search_query: str = request.args.get("q", "")

            with SessionManager() as session:
                # Get current user
                user: User | None = get_current_user(session)
                validate_user_authentication(user)

                # Search services using the service layer
                services: list[TradingService] = TradingServiceService.search_services(
                    session,
                    user.id,
                    search_query,
                )

                # Apply pagination using the utility function
                result: dict[str, any] = apply_pagination(services)

                # Serialize the results
                result["items"] = services_schema.dump(result["items"])

                return result, ApiConstants.HTTP_OK

        except ValidationError as e:
            current_app.logger.warning("Validation error searching services: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except AuthorizationError as e:
            current_app.logger.warning("Authorization error searching services: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except Exception as e:
            current_app.logger.exception("Error searching trading services")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/<int:service_id>")
@api.param("service_id", "The trading service identifier")
@api.response(ApiConstants.HTTP_NOT_FOUND, "Service not found")
class ServiceItem(Resource):
    """Shows a single trading service."""

    @api.doc("get_service")
    @api.marshal_with(service_model)
    @api.response(ApiConstants.HTTP_OK, "Success")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Service not found")
    @jwt_required()
    @require_ownership("service", id_parameter="service_id")
    def get(self, service_id: int) -> tuple[dict[str, any], int]:
        """Get a trading service by ID."""
        try:
            with SessionManager() as session:
                # Get current user
                user: User | None = get_current_user(session)
                validate_user_authentication(user)

                service: TradingService = TradingServiceService.get_by_id(
                    session,
                    service_id,
                )
                return service_schema.dump(service), ApiConstants.HTTP_OK

        except ResourceNotFoundError as e:
            current_app.logger.warning("Service not found: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except AuthorizationError as e:
            current_app.logger.warning("Authorization error getting service: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except Exception as e:
            current_app.logger.exception("Error retrieving trading service")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR

    @api.doc("update_service")
    @api.expect(
        api.model(
            "ServiceUpdate",
            {
                "name": fields.String(description="Service name"),
                "description": fields.String(description="Service description"),
                "stock_symbol": fields.String(description="Stock ticker symbol"),
                "is_active": fields.Boolean(
                    description="Whether the service is active",
                ),
                "minimum_balance": fields.Float(
                    description="Minimum fund balance to maintain",
                ),
                "allocation_percent": fields.Float(
                    description="Percentage of funds to allocate per trade",
                ),
                "buy_threshold": fields.Float(description="Buy threshold percentage"),
                "sell_threshold": fields.Float(description="Sell threshold percentage"),
                "stop_loss_percent": fields.Float(description="Stop loss percentage"),
                "take_profit_percent": fields.Float(
                    description="Take profit percentage",
                ),
            },
        ),
    )
    @api.marshal_with(service_model)
    @api.response(ApiConstants.HTTP_OK, "Service updated")
    @api.response(ApiConstants.HTTP_BAD_REQUEST, "Validation error")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Service not found")
    @jwt_required()
    @require_ownership("service", id_parameter="service_id")
    def put(self, service_id: int) -> tuple[dict[str, any], int]:
        """Update a trading service."""
        try:
            data: dict[str, any] = request.json or {}

            # Validate input data
            validated_data: dict[str, any] = service_update_schema.load(
                data,
                partial=True,
            )

            with SessionManager() as session:
                # Get current user
                user: User | None = get_current_user(session)
                validate_user_authentication(user)

                # Get service (ownership already verified by decorator)
                service: TradingService = TradingServiceService.get_by_id(
                    session,
                    service_id,
                )

                # Update the service using the service layer
                result: TradingService = TradingServiceService.update_service(
                    session,
                    service,
                    validated_data,
                )
                return service_schema.dump(result), ApiConstants.HTTP_OK

        except ValidationError as e:
            error_messages: dict[str, any] = getattr(e, "messages", {})
            current_app.logger.warning(
                "Validation error updating service: %s",
                error_messages,
            )
            return {
                "error": True,
                "message": str(e),
                "validation_errors": error_messages,
            }, ApiConstants.HTTP_BAD_REQUEST
        except ResourceNotFoundError as e:
            current_app.logger.warning("Service not found: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except AuthorizationError as e:
            current_app.logger.warning("Authorization error updating service: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except BusinessLogicError as e:
            current_app.logger.exception("Business logic error updating service")
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except Exception as e:
            current_app.logger.exception("Error updating trading service")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR

    @api.doc("delete_service")
    @api.response(ApiConstants.HTTP_NO_CONTENT, "Service deleted")
    @api.response(
        ApiConstants.HTTP_BAD_REQUEST,
        "Cannot delete service with dependencies",
    )
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Service not found")
    @jwt_required()
    @require_ownership("service", id_parameter="service_id")
    def delete(self, service_id: int) -> tuple[str | dict[str, any], int]:
        """Delete a trading service."""
        try:
            with SessionManager() as session:
                # Get current user
                user: User | None = get_current_user(session)
                validate_user_authentication(user)

                # Get service (ownership already verified by decorator)
                service: TradingService = TradingServiceService.get_by_id(
                    session,
                    service_id,
                )

                # Delete service using the service layer
                TradingServiceService.delete_service(session, service)
                return "", ApiConstants.HTTP_NO_CONTENT

        except ResourceNotFoundError as e:
            current_app.logger.warning("Service not found: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except AuthorizationError as e:
            current_app.logger.warning("Authorization error deleting service: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except BusinessLogicError as e:
            current_app.logger.exception("Business logic error deleting service")
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except Exception as e:
            current_app.logger.exception("Error deleting trading service")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/<int:service_id>/state")
@api.param("service_id", "The trading service identifier")
@api.response(ApiConstants.HTTP_NOT_FOUND, "Service not found")
class ServiceStateResource(Resource):
    """Resource for changing a service's state."""

    @api.doc("change_service_state")
    @api.expect(
        api.model(
            "StateChange",
            {
                "state": fields.String(
                    required=True,
                    description="New state (ACTIVE, INACTIVE, etc.)",
                ),
            },
        ),
    )
    @api.marshal_with(service_model)
    @api.response(ApiConstants.HTTP_OK, "State changed")
    @api.response(ApiConstants.HTTP_BAD_REQUEST, "Invalid state")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Service not found")
    @jwt_required()
    @require_ownership("service", id_parameter="service_id")
    def put(self, service_id: int) -> tuple[dict[str, any], int]:
        """Change the state of a trading service."""
        try:
            data: dict[str, any] = request.json or {}

            if "state" not in data:
                validate_service_field("state")

            with SessionManager() as session:
                # Get current user
                user: User | None = get_current_user(session)
                validate_user_authentication(user)

                # Get service (ownership already verified by decorator)
                service: TradingService = TradingServiceService.get_by_id(
                    session,
                    service_id,
                )

                # Change service state using the service layer
                result: TradingService = TradingServiceService.change_state(
                    session,
                    service,
                    data["state"],
                )
                return service_schema.dump(result), ApiConstants.HTTP_OK

        except ValidationError as e:
            error_messages: dict[str, any] = getattr(e, "messages", {})
            current_app.logger.warning(
                "Validation error changing service state: %s",
                error_messages,
            )
            return {
                "error": True,
                "message": str(e),
                "validation_errors": error_messages,
            }, ApiConstants.HTTP_BAD_REQUEST
        except ResourceNotFoundError as e:
            current_app.logger.warning("Service not found: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except AuthorizationError as e:
            current_app.logger.warning(
                "Authorization error changing service state: %s",
                e,
            )
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except BusinessLogicError as e:
            current_app.logger.exception("Business logic error changing service state")
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except Exception as e:
            current_app.logger.exception("Error changing service state")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/<int:service_id>/mode")
@api.param("service_id", "The trading service identifier")
@api.response(ApiConstants.HTTP_NOT_FOUND, "Service not found")
class ServiceModeResource(Resource):
    """Resource for changing a service's trading mode."""

    @api.doc("change_service_mode")
    @api.expect(
        api.model(
            "ModeChange",
            {
                "mode": fields.String(
                    required=True,
                    description="New mode (BUY, SELL, etc.)",
                ),
            },
        ),
    )
    @api.marshal_with(service_model)
    @api.response(ApiConstants.HTTP_OK, "Mode changed")
    @api.response(ApiConstants.HTTP_BAD_REQUEST, "Invalid mode")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Service not found")
    @jwt_required()
    @require_ownership("service", id_parameter="service_id")
    def put(self, service_id: int) -> tuple[dict[str, any], int]:
        """Change the trading mode of a service."""
        try:
            data: dict[str, any] = request.json or {}

            if "mode" not in data:
                validate_service_field("mode")

            with SessionManager() as session:
                # Get current user
                user: User | None = get_current_user(session)
                validate_user_authentication(user)

                # Get service (ownership already verified by decorator)
                service: TradingService = TradingServiceService.get_by_id(
                    session,
                    service_id,
                )

                # Change service mode using the service layer
                result: TradingService = TradingServiceService.change_mode(
                    session,
                    service,
                    data["mode"],
                )
                return service_schema.dump(result), ApiConstants.HTTP_OK

        except ValidationError as e:
            error_messages: dict[str, any] = getattr(e, "messages", {})
            current_app.logger.warning(
                "Validation error changing service mode: %s",
                error_messages,
            )
            return {
                "error": True,
                "message": str(e),
                "validation_errors": error_messages,
            }, ApiConstants.HTTP_BAD_REQUEST
        except ResourceNotFoundError as e:
            current_app.logger.warning("Service not found: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except AuthorizationError as e:
            current_app.logger.warning(
                "Authorization error changing service mode: %s",
                e,
            )
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except BusinessLogicError as e:
            current_app.logger.exception("Business logic error changing service mode")
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except Exception as e:
            current_app.logger.exception("Error changing service mode")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/<int:service_id>/toggle")
@api.param("service_id", "The trading service identifier")
@api.response(ApiConstants.HTTP_NOT_FOUND, "Service not found")
class ServiceToggle(Resource):
    """Resource for toggling a service's active status."""

    @api.doc("toggle_service")
    @api.marshal_with(service_model)
    @api.response(ApiConstants.HTTP_OK, "Service toggled")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Service not found")
    @jwt_required()
    @require_ownership("service", id_parameter="service_id")
    def post(self, service_id: int) -> tuple[dict[str, any], int]:
        """Toggle the active status of a trading service."""
        try:
            with SessionManager() as session:
                # Get current user
                user: User | None = get_current_user(session)
                validate_user_authentication(user)

                # Get service (ownership already verified by decorator)
                service: TradingService = TradingServiceService.get_by_id(
                    session,
                    service_id,
                )

                # Toggle service active status using the service layer
                result: TradingService = TradingServiceService.toggle_active(
                    session,
                    service,
                )
                return service_schema.dump(result), ApiConstants.HTTP_OK

        except ResourceNotFoundError as e:
            current_app.logger.warning("Service not found: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except AuthorizationError as e:
            current_app.logger.warning("Authorization error toggling service: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except BusinessLogicError as e:
            current_app.logger.exception("Business logic error toggling service")
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except Exception as e:
            current_app.logger.exception("Error toggling service status")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/<int:service_id>/check-buy")
@api.param("service_id", "The trading service identifier")
@api.response(ApiConstants.HTTP_NOT_FOUND, "Service not found")
class ServiceCheckBuy(Resource):
    """Check if a trading service should make a buy decision."""

    @api.doc("check_buy_decision")
    @api.marshal_with(decision_model)
    @api.response(ApiConstants.HTTP_OK, "Success")
    @api.response(ApiConstants.HTTP_BAD_REQUEST, "Invalid request")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Service not found")
    @jwt_required()
    @require_ownership("service", id_parameter="service_id")
    def get(self, service_id: int) -> tuple[dict[str, any], int]:
        """Check if a buy decision should be made."""
        try:
            with SessionManager() as session:
                # Get current user
                user: User | None = get_current_user(session)
                validate_user_authentication(user)

                # Get service (ownership already verified by decorator)
                service: TradingService = TradingServiceService.get_by_id(
                    session,
                    service_id,
                )

                # Get current price
                current_price: float = TradingServiceService.get_current_price(
                    session,
                    service.stock_symbol,
                )

                # Get historical prices from Stock Service
                stock: Stock | None = StockService.find_by_symbol(
                    session,
                    service.stock_symbol,
                )
                if not stock:
                    validate_resource_exists(
                        TradingServiceConstants.RESOURCE_STOCK,
                        service.stock_symbol,
                    )
                # Get historical prices from DailyPriceService
                start_date: date = get_current_date() - timedelta(days=90)
                end_date: date = get_current_date()
                daily_prices: list[StockDailyPrice] = (
                    DailyPriceService.get_daily_prices_by_date_range(
                        session,
                        stock.id,
                        start_date,
                        end_date,
                    )
                )

                historical_prices: list[float] = [
                    float(price.close_price) for price in daily_prices
                ]

                # Check buy condition using the TradingStrategyService
                decision: dict[str, any] = TradingStrategyService.check_buy_condition(
                    service,
                    current_price,
                    historical_prices,
                )
                return decision, ApiConstants.HTTP_OK

        except ResourceNotFoundError as e:
            current_app.logger.warning("Service not found: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except AuthorizationError as e:
            current_app.logger.warning(
                "Authorization error checking buy condition: %s",
                e,
            )
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except BusinessLogicError as e:
            current_app.logger.exception("Business logic error checking buy condition")
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except Exception as e:
            current_app.logger.exception("Error checking buy condition")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/<int:service_id>/check-sell")
@api.param("service_id", "The trading service identifier")
@api.response(ApiConstants.HTTP_NOT_FOUND, "Service not found")
class ServiceCheckSell(Resource):
    """Check if a trading service should make a sell decision."""

    @api.doc("check_sell_decision")
    @api.marshal_with(decision_model)
    @api.response(ApiConstants.HTTP_OK, "Success")
    @api.response(ApiConstants.HTTP_BAD_REQUEST, "Invalid request")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Service not found")
    @jwt_required()
    @require_ownership("service", id_parameter="service_id")
    def get(self, service_id: int) -> tuple[dict[str, any], int]:
        """Check if a sell decision should be made."""
        try:
            with SessionManager() as session:
                # Get current user
                user: User | None = get_current_user(session)
                validate_user_authentication(user)

                # Get service (ownership already verified by decorator)
                service: TradingService = TradingServiceService.get_by_id(
                    session,
                    service_id,
                )

                # Get current price
                current_price: float = TradingServiceService.get_current_price(
                    session,
                    service.stock_symbol,
                )

                # Get historical prices from Stock Service
                stock: Stock | None = StockService.find_by_symbol(
                    session,
                    service.stock_symbol,
                )
                if not stock:
                    validate_resource_exists(
                        TradingServiceConstants.RESOURCE_STOCK,
                        service.stock_symbol,
                    )

                # Get historical prices from DailyPriceService
                start_date: date = get_current_date() - timedelta(days=90)
                end_date: date = get_current_date()
                daily_prices: list[StockDailyPrice] = (
                    DailyPriceService.get_daily_prices_by_date_range(
                        session,
                        stock.id,
                        start_date,
                        end_date,
                    )
                )

                historical_prices: list[float] = [
                    float(price.close_price) for price in daily_prices
                ]

                # Check sell condition using the TradingStrategyService
                decision: dict[str, any] = TradingStrategyService.check_sell_condition(
                    service,
                    current_price,
                    historical_prices,
                )
                return decision, ApiConstants.HTTP_OK

        except ResourceNotFoundError as e:
            current_app.logger.warning("Service not found: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except AuthorizationError as e:
            current_app.logger.warning(
                "Authorization error checking sell condition: %s",
                e,
            )
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except BusinessLogicError as e:
            current_app.logger.exception("Business logic error checking sell condition")
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except Exception as e:
            current_app.logger.exception("Error checking sell condition")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/<int:service_id>/backtest")
@api.param("service_id", "The trading service identifier")
@api.response(ApiConstants.HTTP_NOT_FOUND, "Service not found")
class ServiceBacktest(Resource):
    """Run a backtest for a trading service."""

    @api.doc(
        "backtest_service",
        params={
            "days": "Number of days to backtest (default: 90)",
        },
    )
    @api.response(ApiConstants.HTTP_OK, "Success")
    @api.response(ApiConstants.HTTP_BAD_REQUEST, "Invalid request")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Service not found")
    @jwt_required()
    @require_ownership("service", id_parameter="service_id")
    def post(self, service_id: int) -> tuple[dict[str, any], int]:
        """Run a backtest for a trading service."""
        try:
            days: int = request.args.get("days", 90, type=int)

            with SessionManager() as session:
                # Get current user
                user: User | None = get_current_user(session)
                validate_user_authentication(user)

                # Get service (ownership already verified by decorator)
                service: TradingService = TradingServiceService.get_by_id(
                    session,
                    service_id,
                )

                # Run backtest using the BacktestService
                backtest_results: dict[str, any] = BacktestService.backtest_strategy(
                    session,
                    service.id,
                    days,
                )
                return backtest_results, ApiConstants.HTTP_OK

        except ResourceNotFoundError as e:
            current_app.logger.warning("Service not found: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except AuthorizationError as e:
            current_app.logger.warning("Authorization error running backtest: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except BusinessLogicError as e:
            current_app.logger.warning("Business logic error running backtest: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except Exception as e:
            current_app.logger.exception("Error running backtest")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/<int:service_id>/execute-strategy")
@api.param("service_id", "The trading service identifier")
@api.response(ApiConstants.HTTP_NOT_FOUND, "Service not found")
class ServiceExecuteStrategy(Resource):
    """Execute trading strategy for a service."""

    @api.doc("execute_strategy")
    @api.response(ApiConstants.HTTP_OK, "Success")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Service not found")
    @jwt_required()
    @require_ownership("service", id_parameter="service_id")
    def post(self, service_id: int) -> tuple[dict[str, any], int]:
        """Execute trading strategy for a service."""
        try:
            with SessionManager() as session:
                # Get current user
                user: User | None = get_current_user(session)
                validate_user_authentication(user)

                # Get service (ownership already verified by decorator)
                service: TradingService = TradingServiceService.get_by_id(
                    session,
                    service_id,
                )

                # Execute strategy using the TradingStrategyService
                result: dict[str, any] = (
                    TradingStrategyService.execute_trading_strategy(
                        session,
                        service.id,
                    )
                )
                return result, ApiConstants.HTTP_OK

        except ResourceNotFoundError as e:
            current_app.logger.warning("Service not found: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except AuthorizationError as e:
            current_app.logger.warning(
                "Authorization error executing strategy: %s",
                e,
            )
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except BusinessLogicError as e:
            current_app.logger.warning(
                "Business logic error executing strategy: %s",
                e,
            )
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except Exception as e:
            current_app.logger.exception("Error executing trading strategy")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR
