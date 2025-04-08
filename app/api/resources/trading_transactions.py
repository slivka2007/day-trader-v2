"""Trading Transactions API resources."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from flask import request
from flask_jwt_extended import jwt_required
from flask_restx import Model, Namespace, OrderedModel, Resource, fields

if TYPE_CHECKING:
    from app.models import TradingService, TradingTransaction, User

from app.api.schemas.trading_transaction import (
    transaction_cancel_schema,
    transaction_complete_schema,
    transaction_create_schema,
    transaction_schema,
    transactions_schema,
)
from app.models.enums import TransactionState
from app.services.session_manager import SessionManager
from app.services.transaction_service import TransactionService
from app.utils.auth import (
    get_current_user,
    require_ownership,
    verify_resource_ownership,
)
from app.utils.constants import ApiConstants, PaginationConstants
from app.utils.errors import (
    AuthorizationError,
    BusinessLogicError,
    ResourceNotFoundError,
    ValidationError,
)
from app.utils.query_utils import apply_pagination

# Set up logging
logger: logging.Logger = logging.getLogger(__name__)

# Define exception types for request handling
RoutingExceptions: tuple[type[Exception], ...] = (
    RecursionError,
    MemoryError,
    NameError,
    TypeError,
    ValueError,
    KeyError,
    AttributeError,
)


# Helper functions for validation
def validate_transaction_field(field_name: str) -> None:
    """Validate if a required field is present.

    Args:
        field_name: Name of the required field

    Raises:
        ValidationError: When the field is missing

    """
    raise ValidationError(
        ValidationError.FIELD_REQUIRED.format(key=field_name),
        errors={field_name: ["Field is required"]},
    )


def validate_transaction_data_format() -> None:
    """Validate if transaction data is in the correct format.

    Args:
        data: The data to validate

    Raises:
        ValidationError: When the data format is invalid

    """
    error_msg: str = "Invalid transaction data format"
    raise ValidationError(error_msg)


def validate_transaction_state(state: str) -> None:
    """Validate if transaction state is valid.

    Args:
        state: The state to validate

    Raises:
        ValidationError: When the state is invalid

    """
    error_msg: str = f"Invalid transaction state: {state}"
    raise ValidationError(error_msg)


def validate_user_authentication(user: User | None) -> None:
    """Validate if user is authenticated.

    Args:
        user: The user to validate

    Raises:
        AuthorizationError: When user is not authenticated

    """
    if not user:
        raise AuthorizationError(AuthorizationError.NOT_AUTHENTICATED)


def validate_transaction_exists(
    transaction: TradingTransaction | None,
    transaction_id: int,
) -> None:
    """Validate if transaction exists.

    Args:
        transaction: The transaction to validate
        transaction_id: ID of the transaction

    Raises:
        ResourceNotFoundError: When transaction is not found

    """
    if not transaction:
        raise ResourceNotFoundError(
            ResourceNotFoundError.NOT_FOUND.format(
                resource_type="TradingTransaction",
                resource_id=transaction_id,
            ),
        )


def validate_service_exists(service: TradingService | None, service_id: int) -> None:
    """Validate if service exists.

    Args:
        service: The service to validate
        service_id: ID of the service

    Raises:
        ResourceNotFoundError: When service is not found

    """
    if not service:
        raise ResourceNotFoundError(
            ResourceNotFoundError.NOT_FOUND.format(
                resource_type="TradingService",
                resource_id=service_id,
            ),
        )


# Create namespace
api: Namespace = Namespace("transactions", description="Trading transaction operations")

# Define API models
transaction_model: Model | OrderedModel = api.model(
    "TradingTransaction",
    {
        "id": fields.Integer(readonly=True, description="The transaction identifier"),
        "service_id": fields.Integer(
            required=True,
            description="The trading service identifier",
        ),
        "stock_id": fields.Integer(description="The stock identifier"),
        "stock_symbol": fields.String(description="Stock ticker symbol"),
        "state": fields.String(description="Transaction state"),
        "shares": fields.Float(description="Number of shares"),
        "purchase_price": fields.Float(description="Purchase price per share"),
        "sale_price": fields.Float(description="Sale price per share"),
        "gain_loss": fields.Float(description="Profit or loss amount"),
        "purchase_date": fields.DateTime(description="Date of purchase"),
        "sale_date": fields.DateTime(description="Date of sale (if sold)"),
        "notes": fields.String(description="Transaction notes"),
        "created_at": fields.DateTime(description="Creation timestamp"),
        "updated_at": fields.DateTime(description="Last update timestamp"),
        "is_complete": fields.Boolean(
            description="Whether the transaction is complete",
        ),
        "is_profitable": fields.Boolean(
            description="Whether the transaction is profitable",
        ),
        "duration_days": fields.Integer(description="Duration of transaction in days"),
        "total_cost": fields.Float(description="Total cost of the purchase"),
        "total_revenue": fields.Float(description="Total revenue from the sale"),
        "profit_loss_percent": fields.Float(description="Profit/loss as a percentage"),
    },
)

transaction_complete_model: Model | OrderedModel = api.model(
    "TransactionComplete",
    {"sale_price": fields.Float(required=True, description="Sale price per share")},
)

transaction_create_model: Model | OrderedModel = api.model(
    "TransactionCreate",
    {
        "service_id": fields.Integer(
            required=True,
            description="The trading service identifier",
        ),
        "stock_symbol": fields.String(required=True, description="The stock symbol"),
        "shares": fields.Float(required=True, description="Number of shares"),
        "purchase_price": fields.Float(
            required=True,
            description="Purchase price per share",
        ),
    },
)

transaction_cancel_model: Model | OrderedModel = api.model(
    "TransactionCancel",
    {"reason": fields.String(description="Reason for cancellation")},
)

# Pagination model
pagination_model: Model | OrderedModel = api.model(
    "Pagination",
    {
        "page": fields.Integer(description="Current page number"),
        "page_size": fields.Integer(description="Number of items per page"),
        "total_items": fields.Integer(description="Total number of items"),
        "total_pages": fields.Integer(description="Total number of pages"),
        "has_next": fields.Boolean(
            description="Whether there is a next page",
        ),
        "has_prev": fields.Boolean(
            description="Whether there is a previous page",
        ),
    },
)

# Models for collection responses with pagination
transaction_list_model: Model | OrderedModel = api.model(
    "TransactionList",
    {
        "items": fields.List(
            fields.Nested(transaction_model),
            description="List of transactions",
        ),
        "pagination": fields.Nested(pagination_model),
    },
)


@api.route("/")
class TransactionList(Resource):
    """Resource for managing transactions."""

    @api.doc(
        "list_transactions",
        params={
            "page": f"Page number (default: {PaginationConstants.DEFAULT_PAGE})",
            "page_size": (
                f"Number of items per page (default: "
                f"{PaginationConstants.DEFAULT_PER_PAGE}, "
                f"max: {PaginationConstants.MAX_PER_PAGE})"
            ),
            "service_id": "Filter by service ID",
            "state": "Filter by transaction state (OPEN, CLOSED, CANCELLED)",
            "sort": "Sort field (e.g., created_at, purchase_date)",
            "order": "Sort order (asc or desc, default: desc)",
        },
    )
    @api.marshal_with(transaction_list_model)
    @api.response(ApiConstants.HTTP_OK, "Success")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @jwt_required()
    def get(self) -> tuple[dict[str, any], int]:
        """List all transactions for the current user."""
        try:
            with SessionManager() as session:
                # Get current user
                user: User | None = get_current_user(session)
                validate_user_authentication(user)

                # Build filters from request parameters
                filters: dict[str, any] = {}

                service_id: str | None = request.args.get("service_id")
                if service_id and service_id.isdigit():
                    filters["service_id"] = int(service_id)

                state: str | None = request.args.get("state")
                if state and TransactionState.is_valid(state):
                    filters["state"] = state

                # Get user's transactions with filters using service layer
                all_transactions: list[TradingTransaction] = (
                    TransactionService.get_transactions_for_user(
                        session,
                        user.id,
                        filters,
                    )
                )

                # Sort transactions
                sort_field: str = request.args.get("sort", "purchase_date")
                sort_order: str = request.args.get("order", "desc")

                sorted_transactions: list[TradingTransaction] = (
                    TransactionService.sort_transactions(
                        all_transactions,
                        sort_field,
                        sort_order,
                    )
                )

                # Apply pagination and prepare response
                result: dict[str, any] = apply_pagination(sorted_transactions)
                result["items"] = transactions_schema.dump(result["items"])

                return result, ApiConstants.HTTP_OK

        except ValidationError as e:
            logger.warning("Validation error listing transactions: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except AuthorizationError as e:
            logger.warning("Authorization error listing transactions: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except BusinessLogicError as e:
            logger.exception("Business logic error listing transactions")
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except RoutingExceptions as e:
            logger.exception("Routing error in listing transactions")
            return {
                "error": True,
                "message": f"An unexpected routing error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR

    @api.doc("create_transaction")
    @api.expect(transaction_create_model)
    @api.marshal_with(transaction_model)
    @api.response(ApiConstants.HTTP_CREATED, "Transaction created")
    @api.response(ApiConstants.HTTP_BAD_REQUEST, "Validation error")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Service not found")
    @jwt_required()
    def post(self) -> tuple[dict[str, any], int]:
        """Create a new trading transaction (buy)."""
        try:
            data: dict[str, any] = request.json or {}

            # Validate input data
            validated_data: dict[str, any] = transaction_create_schema.load(data)

            # Safety check to ensure validated_data is a dictionary
            if not validated_data or not isinstance(validated_data, dict):
                validate_transaction_data_format()

            service_id: int | None = validated_data.get("service_id")
            if not service_id:
                validate_transaction_field("service_id")

            with SessionManager() as session:
                # Get current user and verify service ownership
                user: User | None = get_current_user(session)
                validate_user_authentication(user)

                # Verify service belongs to user
                verify_resource_ownership(
                    session=session,
                    resource_type="service",
                    resource_id=service_id,
                    user_id=user.id,
                )

                # Create the transaction using the service layer
                transaction: TradingTransaction = (
                    TransactionService.create_buy_transaction(
                        session=session,
                        service_id=service_id,
                        stock_symbol=validated_data.get("stock_symbol", ""),
                        shares=validated_data.get("shares", 0),
                        purchase_price=validated_data.get("purchase_price", 0),
                    )
                )

                return transaction_schema.dump(transaction), ApiConstants.HTTP_CREATED

        except ValidationError as e:
            error_messages: dict[str, any] = getattr(e, "messages", {})
            logger.warning("Validation error creating transaction: %s", error_messages)
            return {
                "error": True,
                "message": str(e),
                "validation_errors": error_messages,
            }, ApiConstants.HTTP_BAD_REQUEST
        except ResourceNotFoundError as e:
            logger.warning("Resource not found: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except AuthorizationError as e:
            logger.warning("Authorization error creating transaction: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except BusinessLogicError as e:
            logger.exception("Business logic error creating transaction")
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except RoutingExceptions as e:
            logger.exception("Routing error in creating transaction")
            return {
                "error": True,
                "message": f"An unexpected routing error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/<int:transaction_id>")
@api.param("transaction_id", "The transaction identifier")
@api.response(ApiConstants.HTTP_NOT_FOUND, "Transaction not found")
class TransactionItem(Resource):
    """Shows a single transaction."""

    @api.doc("get_transaction")
    @api.marshal_with(transaction_model)
    @api.response(ApiConstants.HTTP_OK, "Success")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Transaction not found")
    @jwt_required()
    @require_ownership("transaction", id_parameter="transaction_id")
    def get(self, transaction_id: int) -> tuple[dict[str, any], int]:
        """Get a transaction by ID."""
        try:
            with SessionManager() as session:
                # Get current user
                user: User | None = get_current_user(session)
                validate_user_authentication(user)

                # Verify ownership and get transaction
                transaction: TradingTransaction = TransactionService.verify_ownership(
                    session,
                    transaction_id,
                    user.id,
                )
                return transaction_schema.dump(transaction), ApiConstants.HTTP_OK

        except ResourceNotFoundError as e:
            logger.warning("Transaction not found: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except AuthorizationError as e:
            logger.warning("Authorization error getting transaction: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except BusinessLogicError as e:
            logger.exception("Business logic error retrieving transaction")
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except RoutingExceptions as e:
            logger.exception("Routing error in retrieving transaction")
            return {
                "error": True,
                "message": f"An unexpected routing error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR

    @api.doc("delete_transaction")
    @api.response(ApiConstants.HTTP_NO_CONTENT, "Transaction deleted")
    @api.response(ApiConstants.HTTP_BAD_REQUEST, "Transaction cannot be deleted")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Transaction not found")
    @jwt_required()
    @require_ownership("transaction", id_parameter="transaction_id")
    def delete(self, transaction_id: int) -> tuple[str | dict[str, any], int]:
        """Delete a transaction."""
        try:
            with SessionManager() as session:
                # Get current user
                user: User | None = get_current_user(session)
                validate_user_authentication(user)

                # Verify ownership
                TransactionService.verify_ownership(session, transaction_id, user.id)

                # Delete the transaction
                TransactionService.delete_transaction(session, transaction_id)
                return "", ApiConstants.HTTP_NO_CONTENT

        except ResourceNotFoundError as e:
            logger.warning("Transaction not found: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except AuthorizationError as e:
            logger.warning("Authorization error deleting transaction: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except BusinessLogicError as e:
            logger.exception("Business logic error deleting transaction")
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except RoutingExceptions as e:
            logger.exception("Routing error in deleting transaction")
            return {
                "error": True,
                "message": f"An unexpected routing error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/<int:transaction_id>/complete")
@api.param("transaction_id", "The transaction identifier")
@api.response(ApiConstants.HTTP_NOT_FOUND, "Transaction not found")
class TransactionComplete(Resource):
    """Complete (sell) a transaction."""

    @api.doc("complete_transaction")
    @api.expect(transaction_complete_model)
    @api.marshal_with(transaction_model)
    @api.response(ApiConstants.HTTP_OK, "Transaction completed")
    @api.response(
        ApiConstants.HTTP_BAD_REQUEST,
        "Validation error or transaction already complete",
    )
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Transaction not found")
    @jwt_required()
    @require_ownership("transaction", id_parameter="transaction_id")
    def post(self, transaction_id: int) -> tuple[dict[str, any], int]:
        """Complete (sell) a transaction."""
        try:
            data: dict[str, any] = request.json or {}

            # Validate input data
            validated_data: dict[str, any] = transaction_complete_schema.load(data)

            # Safely access sale_price and convert to Decimal
            if validated_data and isinstance(validated_data, dict):
                sale_price_value: any | None = validated_data.get("sale_price")
                if sale_price_value is not None:
                    sale_price: float = float(str(sale_price_value))
                else:
                    validate_transaction_field("sale_price")
            else:
                validate_transaction_field("sale_price")

            with SessionManager() as session:
                # Get current user
                user: User | None = get_current_user(session)
                validate_user_authentication(user)

                # Verify ownership
                TransactionService.verify_ownership(session, transaction_id, user.id)

                # Complete the transaction using the service layer
                transaction: TradingTransaction = (
                    TransactionService.complete_transaction(
                        session,
                        transaction_id,
                        sale_price,
                    )
                )
                return transaction_schema.dump(transaction), ApiConstants.HTTP_OK

        except ValidationError as e:
            error_messages: dict[str, any] = getattr(e, "messages", {})
            logger.warning(
                "Validation error completing transaction: %s",
                error_messages,
            )
            return {
                "error": True,
                "message": str(e),
                "validation_errors": error_messages,
            }, ApiConstants.HTTP_BAD_REQUEST
        except ResourceNotFoundError as e:
            logger.warning("Transaction not found: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except AuthorizationError as e:
            logger.warning("Authorization error completing transaction: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except BusinessLogicError as e:
            logger.exception("Business logic error completing transaction")
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except RoutingExceptions as e:
            logger.exception("Routing error in completing transaction")
            return {
                "error": True,
                "message": f"An unexpected routing error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/<int:transaction_id>/cancel")
@api.param("transaction_id", "The transaction identifier")
@api.response(ApiConstants.HTTP_NOT_FOUND, "Transaction not found")
class TransactionCancel(Resource):
    """Cancel a transaction."""

    @api.doc("cancel_transaction")
    @api.expect(transaction_cancel_model)
    @api.marshal_with(transaction_model)
    @api.response(ApiConstants.HTTP_OK, "Transaction cancelled")
    @api.response(
        ApiConstants.HTTP_BAD_REQUEST,
        "Validation error or transaction already complete",
    )
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Transaction not found")
    @jwt_required()
    @require_ownership("transaction", id_parameter="transaction_id")
    def post(self, transaction_id: int) -> tuple[dict[str, any], int]:
        """Cancel a transaction."""
        try:
            data: dict[str, any] = request.json or {}

            # Validate input data
            validated_data: dict[str, any] = transaction_cancel_schema.load(data)

            # Safely access reason
            reason = "User cancelled"
            if validated_data and isinstance(validated_data, dict):
                reason: str | None = validated_data.get("reason", reason)

            with SessionManager() as session:
                # Get current user
                user: User | None = get_current_user(session)
                validate_user_authentication(user)

                # Verify ownership
                TransactionService.verify_ownership(session, transaction_id, user.id)

                # Cancel the transaction using the service layer
                transaction: TradingTransaction = TransactionService.cancel_transaction(
                    session,
                    transaction_id,
                    reason,
                )
                return transaction_schema.dump(transaction), ApiConstants.HTTP_OK

        except ValidationError as e:
            error_messages: dict[str, any] = getattr(e, "messages", {})
            logger.warning(
                "Validation error cancelling transaction: %s",
                error_messages,
            )
            return {
                "error": True,
                "message": str(e),
                "validation_errors": error_messages,
            }, ApiConstants.HTTP_BAD_REQUEST
        except ResourceNotFoundError as e:
            logger.warning("Transaction not found: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except AuthorizationError as e:
            logger.warning("Authorization error cancelling transaction: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except BusinessLogicError as e:
            logger.exception("Business logic error cancelling transaction")
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except RoutingExceptions as e:
            logger.exception("Routing error in cancelling transaction")
            return {
                "error": True,
                "message": f"An unexpected routing error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/services/<int:service_id>")
@api.param("service_id", "The trading service identifier")
@api.response(ApiConstants.HTTP_NOT_FOUND, "Service not found")
class ServiceTransactions(Resource):
    """Resource for managing transactions of a specific trading service."""

    @api.doc(
        "list_service_transactions",
        params={
            "page": f"Page number (default: {PaginationConstants.DEFAULT_PAGE})",
            "page_size": (
                f"Number of items per page (default: "
                f"{PaginationConstants.DEFAULT_PER_PAGE}, "
                f"max: {PaginationConstants.MAX_PER_PAGE})"
            ),
            "state": "Filter by transaction state (OPEN, CLOSED, CANCELLED)",
            "sort": "Sort field (e.g., created_at, shares)",
            "order": "Sort order (asc or desc, default: desc)",
        },
    )
    @api.marshal_with(transaction_list_model)
    @api.response(ApiConstants.HTTP_OK, "Success")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Service not found")
    @jwt_required()
    @require_ownership("service", id_parameter="service_id")
    def get(
        self,
        service_id: int,
    ) -> tuple[dict[str, any], int]:
        """Get all transactions for a specific trading service."""
        try:
            with SessionManager() as session:
                # Parse query parameters
                state: str | None = request.args.get("state")
                if state and not TransactionState.is_valid(state):
                    validate_transaction_state(state)

                # Get transactions for this service using service layer
                if state:
                    transactions: list[TradingTransaction] = (
                        TransactionService.get_by_service(
                            session,
                            service_id,
                            state,
                        )
                    )
                else:
                    transactions: list[TradingTransaction] = (
                        TransactionService.get_by_service(
                            session,
                            service_id,
                        )
                    )

                # Sort transactions
                sort_field: str = request.args.get("sort", "purchase_date")
                sort_order: str = request.args.get("order", "desc")

                sorted_transactions: list[TradingTransaction] = (
                    TransactionService.sort_transactions(
                        transactions,
                        sort_field,
                        sort_order,
                    )
                )

                # Apply pagination and prepare response
                result: dict[str, any] = apply_pagination(sorted_transactions)
                result["items"] = transactions_schema.dump(result["items"])

                return result, ApiConstants.HTTP_OK

        except ValidationError as e:
            logger.warning("Validation error listing service transactions: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except ResourceNotFoundError as e:
            logger.warning("Service not found: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except AuthorizationError as e:
            logger.warning("Authorization error listing service transactions: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except BusinessLogicError as e:
            logger.exception("Business logic error listing service transactions")
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except RoutingExceptions as e:
            logger.exception("Routing error in listing service transactions")
            return {
                "error": True,
                "message": f"An unexpected routing error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/<int:transaction_id>/notes")
@api.param("transaction_id", "The transaction identifier")
@api.response(ApiConstants.HTTP_NOT_FOUND, "Transaction not found")
class TransactionNotes(Resource):
    """Update transaction notes."""

    @api.doc("update_transaction_notes")
    @api.expect(
        api.model(
            "TransactionNotes",
            {"notes": fields.String(required=True, description="Transaction notes")},
        ),
    )
    @api.marshal_with(transaction_model)
    @api.response(ApiConstants.HTTP_OK, "Notes updated")
    @api.response(ApiConstants.HTTP_BAD_REQUEST, "Validation error")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Transaction not found")
    @jwt_required()
    @require_ownership("transaction", id_parameter="transaction_id")
    def put(self, transaction_id: int) -> tuple[dict[str, any], int]:
        """Update transaction notes."""
        try:
            data: dict[str, any] = request.json or {}

            # Check if data is None or doesn't contain notes
            if "notes" not in data:
                validate_transaction_field("notes")

            with SessionManager() as session:
                # Get current user
                user: User | None = get_current_user(session)
                validate_user_authentication(user)

                # Get transaction (ownership already verified by decorator)
                transaction: TradingTransaction = TransactionService.get_by_id(
                    session,
                    transaction_id,
                )
                if not transaction:
                    validate_transaction_exists(transaction, transaction_id)

                # Update notes using the service layer
                notes: str = data.get("notes", "") if isinstance(data, dict) else ""
                transaction: TradingTransaction = (
                    TransactionService.update_transaction_notes(
                        session,
                        transaction_id,
                        notes,
                    )
                )
                return transaction_schema.dump(transaction), ApiConstants.HTTP_OK

        except ValidationError as e:
            logger.warning("Validation error updating transaction notes: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except ResourceNotFoundError as e:
            logger.warning("Transaction not found: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except AuthorizationError as e:
            logger.warning("Authorization error updating transaction notes: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except BusinessLogicError as e:
            logger.exception("Business logic error updating transaction notes")
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except RoutingExceptions as e:
            logger.exception("Routing error in updating transaction notes")
            return {
                "error": True,
                "message": f"An unexpected routing error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


@api.route("/services/<int:service_id>/metrics")
@api.param("service_id", "The trading service identifier")
@api.response(ApiConstants.HTTP_NOT_FOUND, "Service not found")
class TransactionMetrics(Resource):
    """Get metrics for transactions of a service."""

    @api.doc("get_transaction_metrics")
    @api.response(ApiConstants.HTTP_OK, "Success")
    @api.response(ApiConstants.HTTP_UNAUTHORIZED, "Unauthorized")
    @api.response(ApiConstants.HTTP_NOT_FOUND, "Service not found")
    @jwt_required()
    @require_ownership("service", id_parameter="service_id")
    def get(
        self,
        service_id: int,
    ) -> tuple[dict[str, any], int]:
        """Get metrics for transactions of a service."""
        try:
            with SessionManager() as session:
                # Check if service exists using service layer
                # (require_ownership decorator already verifies ownership)
                service: TradingService | None = TransactionService.get_service_by_id(
                    session,
                    service_id,
                )
                validate_service_exists(service, service_id)

                # Calculate metrics using the service layer
                metrics: dict[str, any] = (
                    TransactionService.calculate_transaction_metrics(
                        session,
                        service_id,
                    )
                )
                return metrics, ApiConstants.HTTP_OK

        except ResourceNotFoundError as e:
            logger.warning("Service not found: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except AuthorizationError as e:
            logger.warning("Authorization error calculating metrics: %s", e)
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except BusinessLogicError as e:
            logger.exception("Business logic error calculating metrics")
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except RoutingExceptions as e:
            logger.exception("Routing error in calculating transaction metrics")
            return {
                "error": True,
                "message": f"An unexpected routing error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR
