"""Trading Services API resources."""

from __future__ import annotations

from typing import cast

from flask import current_app, request
from flask_jwt_extended import jwt_required
from flask_restx import Model, Namespace, OrderedModel, Resource, fields
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.schemas.trading_service import (
    service_create_schema,
    service_schema,
    service_update_schema,
    services_schema,
)
from app.models import TradingService, User
from app.services.session_manager import SessionManager
from app.services.trading_service import TradingServiceService
from app.utils.auth import get_current_user, require_ownership
from app.utils.errors import AuthorizationError, BusinessLogicError, ValidationError
from app.utils.query_utils import apply_filters, apply_pagination

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
    """Shows a list of all trading services, and lets you create a new service"""

    @api.doc(
        "list_services",
        params={
            "page": "Page number (default: 1)",
            "page_size": "Number of items per page (default: 20, max: 100)",
            "is_active": "Filter by active status (true/false)",
            "stock_symbol": "Filter by stock symbol",
            "sort": "Sort field (e.g., created_at, name)",
            "order": "Sort order (asc or desc, default: asc)",
        },
    )
    @api.marshal_with(service_list_model)
    @api.response(200, "Success")
    @api.response(401, "Unauthorized")
    @jwt_required()
    def get(self) -> tuple[dict[str, any], int]:
        """List all trading services for the authenticated user"""
        with SessionManager() as session:
            # Get current user
            user: User | None = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")

            # Get base query for user's services
            query: list[TradingService] = (
                (
                    session.execute(
                        select(TradingService).where(TradingService.user_id == user.id),
                    )
                )
                .scalars()
                .all()
            )

            # Apply filters
            query = apply_filters(query, TradingService)

            # Apply pagination
            result: dict[str, any] = apply_pagination(query)

            # Serialize the results
            result["items"] = services_schema.dump(result["items"])

            return result

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
    @api.response(201, "Service created")
    @api.response(400, "Validation error")
    @api.response(401, "Unauthorized")
    @jwt_required()
    def post(self):
        """Create a new trading service"""
        data = request.json or {}  # Use empty dict if request.json is None
        try:
            validated_data = service_create_schema.load(data)
        except ValidationError as err:
            error_messages = getattr(err, "messages", {})
            current_app.logger.warning(
                f"Validation error in service creation: {error_messages}",
            )
            raise ValidationError("Invalid service data", errors=error_messages)

        with SessionManager() as session:
            # Get current user
            user = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")

            try:
                # Create the service using the service layer
                service = TradingServiceService.create_service(
                    session=session,
                    user_id=user.id.scalar(),
                    data=cast("dict[str, any]", validated_data),
                )

                return service_schema.dump(service), 201

            except ValidationError as e:
                current_app.logger.warning(
                    f"Validation error creating service: {e!s}",
                )
                raise
            except BusinessLogicError as e:
                current_app.logger.error(f"Business logic error: {e!s}")
                raise
            except IntegrityError as e:
                current_app.logger.error(f"Database integrity error: {e!s}")
                raise BusinessLogicError(
                    "Could not create service due to database constraints",
                )
            except Exception as e:
                current_app.logger.error(f"Unexpected error creating service: {e!s}")
                raise BusinessLogicError(f"Could not create service: {e!s}")


@api.route("/search")
class ServiceSearch(Resource):
    """Search for trading services by name or stock symbol"""

    @api.doc(
        "search_services",
        params={
            "q": "Search query (name or stock symbol)",
            "page": "Page number (default: 1)",
            "page_size": "Number of items per page (default: 20, max: 100)",
        },
    )
    @api.marshal_with(service_list_model)
    @api.response(200, "Success")
    @api.response(401, "Unauthorized")
    @jwt_required()
    def get(self):
        """Search trading services by name or stock symbol"""
        search_query = request.args.get("q", "")

        with SessionManager() as session:
            # Get current user
            user = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")

            # Search services using the service layer
            services = TradingServiceService.search_services(
                session,
                user.id.scalar(),
                search_query,
            )

            # Apply pagination using the utility function
            result = apply_pagination(services)

            # Serialize the results
            result["items"] = services_schema.dump(result["items"])

            return result


@api.route("/<int:id>")
@api.param("id", "The trading service identifier")
@api.response(404, "Service not found")
class ServiceItem(Resource):
    """Shows a single trading service"""

    @api.doc("get_service")
    @api.marshal_with(service_model)
    @api.response(200, "Success")
    @api.response(401, "Unauthorized")
    @api.response(404, "Service not found")
    @jwt_required()
    @require_ownership("service")
    def get(self, id):
        """Get a trading service by ID"""
        with SessionManager() as session:
            # Get current user
            user = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")

            # Verify ownership and get service
            service = TradingServiceService.verify_ownership(
                session,
                id,
                user.id.scalar(),
            )
            return service_schema.dump(service)

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
    @api.response(200, "Service updated")
    @api.response(400, "Validation error")
    @api.response(401, "Unauthorized")
    @api.response(404, "Service not found")
    @jwt_required()
    @require_ownership("service")
    def put(self, id):
        """Update a trading service"""
        data = request.json or {}  # Use empty dict if request.json is None

        # Validate input data
        try:
            validated_data = service_update_schema.load(data, partial=True)
        except ValidationError as err:
            error_messages = getattr(err, "messages", {})
            current_app.logger.warning(
                f"Validation error in service update: {error_messages}",
            )
            raise ValidationError("Invalid service data", errors=error_messages)

        with SessionManager() as session:
            # Get current user
            user = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")

            # Verify ownership and get service
            service = TradingServiceService.verify_ownership(
                session,
                id,
                user.id.scalar(),
            )

            try:
                # Update the service using the service layer
                result = TradingServiceService.update_service(
                    session,
                    service,
                    cast("dict[str, any]", validated_data),
                )
                return service_schema.dump(result)

            except ValidationError as e:
                current_app.logger.warning(
                    f"Validation error updating service: {e!s}",
                )
                raise
            except BusinessLogicError as e:
                current_app.logger.error(f"Business logic error: {e!s}")
                raise
            except Exception as e:
                current_app.logger.error(f"Error updating service: {e!s}")
                raise BusinessLogicError(f"Could not update service: {e!s}")

    @api.doc("delete_service")
    @api.response(204, "Service deleted")
    @api.response(400, "Cannot delete service with dependencies")
    @api.response(401, "Unauthorized")
    @api.response(404, "Service not found")
    @jwt_required()
    @require_ownership("service")
    def delete(self, id):
        """Delete a trading service"""
        with SessionManager() as session:
            # Get current user
            user = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")

            # Verify ownership and get service
            service = TradingServiceService.verify_ownership(
                session,
                id,
                user.id.scalar(),
            )

            try:
                # Delete service using the service layer
                TradingServiceService.delete_service(session, service)
                return "", 204

            except BusinessLogicError as e:
                current_app.logger.warning(
                    f"Business logic error deleting service: {e!s}",
                )
                raise
            except Exception as e:
                current_app.logger.error(f"Unexpected error deleting service: {e!s}")
                raise BusinessLogicError(f"Could not delete service: {e!s}")


@api.route("/<int:id>/state")
@api.param("id", "The trading service identifier")
@api.response(404, "Service not found")
class ServiceStateResource(Resource):
    """Resource for changing a service's state"""

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
    @api.response(200, "State changed")
    @api.response(400, "Invalid state")
    @api.response(401, "Unauthorized")
    @api.response(404, "Service not found")
    @jwt_required()
    @require_ownership("service")
    def put(self, id):
        """Change the state of a trading service"""
        data = request.json or {}

        if "state" not in data:
            raise ValidationError(
                "Missing required field",
                errors={"state": ["Field is required"]},
            )

        with SessionManager() as session:
            # Get current user
            user = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")

            # Verify ownership and get service
            service = TradingServiceService.verify_ownership(
                session,
                id,
                user.id.scalar(),
            )

            try:
                # Change service state using the service layer
                result = TradingServiceService.change_state(
                    session,
                    service,
                    data["state"],
                )
                return service_schema.dump(result)

            except ValidationError as e:
                current_app.logger.warning(
                    f"Validation error changing service state: {e!s}",
                )
                raise
            except BusinessLogicError as e:
                current_app.logger.error(f"Business logic error: {e!s}")
                raise
            except Exception as e:
                current_app.logger.error(f"Error changing service state: {e!s}")
                raise BusinessLogicError(f"Could not change service state: {e!s}")


@api.route("/<int:id>/mode")
@api.param("id", "The trading service identifier")
@api.response(404, "Service not found")
class ServiceModeResource(Resource):
    """Resource for changing a service's trading mode"""

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
    @api.response(200, "Mode changed")
    @api.response(400, "Invalid mode")
    @api.response(401, "Unauthorized")
    @api.response(404, "Service not found")
    @jwt_required()
    @require_ownership("service")
    def put(self, id):
        """Change the trading mode of a service"""
        data = request.json or {}

        if "mode" not in data:
            raise ValidationError(
                "Missing required field",
                errors={"mode": ["Field is required"]},
            )

        with SessionManager() as session:
            # Get current user
            user = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")

            # Verify ownership and get service
            service = TradingServiceService.verify_ownership(
                session,
                id,
                user.id.scalar(),
            )

            try:
                # Change service mode using the service layer
                result = TradingServiceService.change_mode(
                    session,
                    service,
                    data["mode"],
                )
                return service_schema.dump(result)

            except ValidationError as e:
                current_app.logger.warning(
                    f"Validation error changing service mode: {e!s}",
                )
                raise
            except BusinessLogicError as e:
                current_app.logger.error(f"Business logic error: {e!s}")
                raise
            except Exception as e:
                current_app.logger.error(f"Error changing service mode: {e!s}")
                raise BusinessLogicError(f"Could not change service mode: {e!s}")


@api.route("/<int:id>/toggle")
@api.param("id", "The trading service identifier")
@api.response(404, "Service not found")
class ServiceToggle(Resource):
    """Resource for toggling a service's active status"""

    @api.doc("toggle_service")
    @api.response(200, "Service toggled")
    @api.response(401, "Unauthorized")
    @api.response(404, "Service not found")
    @jwt_required()
    @require_ownership("service")
    def post(self, id):
        """Toggle the active status of a trading service"""
        with SessionManager() as session:
            # Get current user
            user = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")

            # Verify ownership and get service
            service = TradingServiceService.verify_ownership(
                session,
                id,
                user.id.scalar(),
            )

            try:
                # Toggle service active status using the service layer
                result = TradingServiceService.toggle_active(session, service)
                return service_schema.dump(result)

            except BusinessLogicError as e:
                current_app.logger.error(f"Business logic error: {e!s}")
                raise
            except Exception as e:
                current_app.logger.error(f"Error toggling service: {e!s}")
                raise BusinessLogicError(f"Could not toggle service: {e!s}")


@api.route("/<int:id>/check-buy")
@api.param("id", "The trading service identifier")
@api.response(404, "Service not found")
class ServiceCheckBuy(Resource):
    """Check if a trading service should make a buy decision"""

    @api.doc("check_buy_decision")
    @api.marshal_with(decision_model)
    @api.response(200, "Success")
    @api.response(400, "Invalid request")
    @api.response(401, "Unauthorized")
    @api.response(404, "Service not found")
    @jwt_required()
    @require_ownership("service")
    def get(self, id):
        """Check if a buy decision should be made"""
        with SessionManager() as session:
            # Get current user
            user = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")

            # Verify ownership and get service
            service = TradingServiceService.verify_ownership(
                session,
                id,
                user.id.scalar(),
            )

            try:
                # Get current price
                current_price = TradingServiceService.get_current_price(
                    session,
                    service.stock_symbol.scalar(),
                )

                # Check buy condition using the service layer
                decision = TradingServiceService.check_buy_condition(
                    session,
                    service,
                    current_price,
                )
                return decision

            except BusinessLogicError as e:
                current_app.logger.error(f"Business logic error: {e!s}")
                raise
            except Exception as e:
                current_app.logger.error(f"Error checking buy condition: {e!s}")
                raise BusinessLogicError(f"Could not check buy condition: {e!s}")


@api.route("/<int:id>/check-sell")
@api.param("id", "The trading service identifier")
@api.response(404, "Service not found")
class ServiceCheckSell(Resource):
    """Check if a trading service should make a sell decision"""

    @api.doc("check_sell_decision")
    @api.marshal_with(decision_model)
    @api.response(200, "Success")
    @api.response(400, "Invalid request")
    @api.response(401, "Unauthorized")
    @api.response(404, "Service not found")
    @jwt_required()
    @require_ownership("service")
    def get(self, id):
        """Check if a sell decision should be made"""
        with SessionManager() as session:
            # Get current user
            user = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")

            # Verify ownership and get service
            service = TradingServiceService.verify_ownership(
                session,
                id,
                user.id.scalar(),
            )

            try:
                # Get current price
                current_price = TradingServiceService.get_current_price(
                    session,
                    service.stock_symbol.scalar(),
                )

                # Check sell condition using the service layer
                decision = TradingServiceService.check_sell_condition(
                    session,
                    service,
                    current_price,
                )
                return decision

            except BusinessLogicError as e:
                current_app.logger.error(f"Business logic error: {e!s}")
                raise
            except Exception as e:
                current_app.logger.error(f"Error checking sell condition: {e!s}")
                raise BusinessLogicError(f"Could not check sell condition: {e!s}")
