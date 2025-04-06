"""Trading Transactions API resources."""

import logging

from flask import request
from flask_jwt_extended import jwt_required
from flask_restx import Model, Namespace, OrderedModel, Resource, fields
from sqlalchemy import select

from app.api.schemas import ValidationError
from app.api.schemas.trading_transaction import (
    transaction_cancel_schema,
    transaction_complete_schema,
    transaction_create_schema,
    transaction_schema,
)
from app.models import TradingService, TradingTransaction, User
from app.models.enums import TransactionState
from app.services.session_manager import SessionManager
from app.services.transaction_service import TransactionService
from app.utils.auth import (
    get_current_user,
    require_ownership,
    verify_resource_ownership,
)
from app.utils.errors import (
    AuthorizationError,
    BusinessLogicError,
    ResourceNotFoundError,
)
from app.utils.query_utils import apply_pagination

# Set up logging
logger: logging.Logger = logging.getLogger(__name__)

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

# Models for collection responses with pagination
transaction_list_model: Model | OrderedModel = api.model(
    "TransactionList",
    {
        "items": fields.List(
            fields.Nested(transaction_model),
            description="List of transactions",
        ),
        "pagination": fields.Nested(
            api.model(
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
            ),
        ),
    },
)


@api.route("/")
class TransactionList(Resource):
    """Resource for managing transactions."""

    @api.doc(
        "list_transactions",
        params={
            "page": "Page number (default: 1)",
            "page_size": "Number of items per page (default: 20, max: 100)",
            "service_id": "Filter by service ID",
            "state": "Filter by transaction state (OPEN, CLOSED, CANCELLED)",
            "sort": "Sort field (e.g., created_at, purchase_date)",
            "order": "Sort order (asc or desc, default: desc)",
        },
    )
    @api.marshal_with(transaction_list_model)
    @api.response(200, "Success")
    @api.response(401, "Unauthorized")
    @jwt_required()
    def get(self) -> dict[str, any]:
        """List all transactions for the current user."""
        with SessionManager() as session:
            # Get current user
            user: User = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")

            # Get services owned by this user
            user_services: list[TradingService] = (
                session.execute(
                    select(TradingService).where(TradingService.user_id == user.id),
                )
                .scalars()
                .all()
            )
            if not user_services:
                return {
                    "items": [],
                    "pagination": {
                        "page": 1,
                        "page_size": 0,
                        "total_items": 0,
                        "total_pages": 0,
                        "has_next": False,
                        "has_prev": False,
                    },
                }

            service_ids: list[int] = [service.id for service in user_services]

            # Parse query parameters
            filters: dict[str, any] = {}

            service_id: str | None = request.args.get("service_id")
            if service_id and service_id.isdigit() and int(service_id) in service_ids:
                filters["service_id"] = int(service_id)

            state: str | None = request.args.get("state")
            if state and TransactionState.is_valid(state):
                filters["state"] = state

            # Build query from user's services
            all_transactions: list[any] = []
            try:
                if "service_id" in filters:
                    # Get transactions for a specific service
                    if "state" in filters:
                        transactions: list[any] = TransactionService.get_by_service(
                            session,
                            filters["service_id"],
                            filters["state"],
                        )
                    else:
                        transactions: list[any] = TransactionService.get_by_service(
                            session,
                            filters["service_id"],
                        )

                    all_transactions.extend(transactions)
                else:
                    # Get transactions for all user's services
                    for service_id in service_ids:
                        if "state" in filters:
                            transactions: list[any] = TransactionService.get_by_service(
                                session,
                                int(service_id),
                                filters["state"],
                            )
                        else:
                            transactions: list[any] = TransactionService.get_by_service(
                                session,
                                int(service_id),
                            )

                        all_transactions.extend(transactions)

                # Apply sorting
                sort_field: str = request.args.get("sort", "purchase_date")
                sort_order: str = request.args.get("order", "desc")

                # Sort using a safer approach
                def get_sort_key(t: any) -> any:
                    # Get attribute safely or use purchase_date as fallback
                    try:
                        val: any | None = getattr(t, sort_field, None)
                        if val is None:
                            val = getattr(t, "purchase_date", None)
                        return val
                    except Exception:
                        return None

                # Sort the transactions with explicit list casting
                all_transactions: list[any] = sorted(
                    list(all_transactions),
                    key=get_sort_key,
                    reverse=(sort_order.lower() == "desc"),
                )

                # Apply pagination using the utility function
                result: dict[str, any] = apply_pagination(all_transactions)

                # Serialize the results
                result["items"] = transaction_schema.dump(result["items"])

                return result

            except ValidationError as e:
                logger.warning(f"Validation error listing transactions: {e!s}")
                raise
            except Exception as e:
                logger.error(f"Error listing transactions: {e!s}")
                raise BusinessLogicError(
                    f"Could not list transactions: {e!s}",
                ) from e

    @api.doc("create_transaction")
    @api.expect(transaction_create_model)
    @api.marshal_with(transaction_model)
    @api.response(201, "Transaction created")
    @api.response(400, "Validation error")
    @api.response(401, "Unauthorized")
    @api.response(404, "Service not found")
    @jwt_required()
    def post(self) -> tuple[dict[str, any], int]:
        """Create a new trading transaction (buy)"""
        data: dict[str, any] = request.json

        # Validate input data
        try:
            validated_data: dict[str, any] = transaction_create_schema.load(data or {})
        except ValidationError as err:
            logger.warning(f"Validation error creating transaction: {err!s}")
            raise ValidationError(
                "Invalid transaction data",
                errors={"general": [str(err)]},
            ) from err

        # Safety check to ensure validated_data is a dictionary
        if not validated_data or not isinstance(validated_data, dict):
            raise ValidationError("Invalid transaction data format")

        service_id: int | None = validated_data.get("service_id")
        if not service_id:
            raise ValidationError("Missing service_id")

        with SessionManager() as session:
            # Get current user and verify service ownership
            user: User | None = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")

            # Verify service belongs to user
            verify_resource_ownership(
                session=session,
                resource_type="service",
                resource_id=service_id,
                user_id=user.id,
            )

            try:
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

                return transaction_schema.dump(transaction), 201

            except ValidationError as e:
                logger.warning(f"Validation error creating transaction: {e!s}")
                raise
            except ResourceNotFoundError as e:
                logger.warning(f"Resource not found: {e!s}")
                raise
            except BusinessLogicError as e:
                logger.error(f"Business logic error: {e!s}")
                raise
            except Exception as e:
                logger.error(f"Error creating transaction: {e!s}")
                raise BusinessLogicError(
                    f"Could not create transaction: {e!s}",
                ) from e


@api.route("/<int:id>")
@api.param("id", "The transaction identifier")
@api.response(404, "Transaction not found")
class TransactionItem(Resource):
    """Shows a single transaction"""

    @api.doc("get_transaction")
    @api.marshal_with(transaction_model)
    @api.response(200, "Success")
    @api.response(401, "Unauthorized")
    @api.response(404, "Transaction not found")
    @jwt_required()
    @require_ownership("transaction")
    def get(self, id: int) -> tuple[dict[str, any], int]:
        """Get a transaction by ID"""
        with SessionManager() as session:
            # Get current user
            user: User | None = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")

            # Verify ownership and get transaction
            transaction: TradingTransaction = TransactionService.verify_ownership(
                session,
                id,
                user.id,
            )
            return transaction_schema.dump(transaction), 200

    @api.doc("delete_transaction")
    @api.response(204, "Transaction deleted")
    @api.response(400, "Transaction cannot be deleted")
    @api.response(401, "Unauthorized")
    @api.response(404, "Transaction not found")
    @jwt_required()
    @require_ownership("transaction")
    def delete(self, id: int) -> tuple[str, int]:
        """Delete a transaction."""
        with SessionManager() as session:
            # Get current user
            user: User | None = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")

            # Verify ownership
            TransactionService.verify_ownership(session, id, user.id)

            try:
                # Delete the transaction
                TransactionService.delete_transaction(session, id)
                return "", 204

            except ResourceNotFoundError as e:
                logger.warning(f"Resource not found: {e!s}")
                raise
            except BusinessLogicError as e:
                logger.error(f"Business logic error: {e!s}")
                raise
            except Exception as e:
                logger.error(f"Error deleting transaction: {e!s}")
                raise BusinessLogicError(
                    f"Could not delete transaction: {e!s}",
                ) from e


@api.route("/<int:id>/complete")
@api.param("id", "The transaction identifier")
@api.response(404, "Transaction not found")
class TransactionComplete(Resource):
    """Complete (sell) a transaction"""

    @api.doc("complete_transaction")
    @api.expect(transaction_complete_model)
    @api.marshal_with(transaction_model)
    @api.response(200, "Transaction completed")
    @api.response(400, "Validation error or transaction already complete")
    @api.response(401, "Unauthorized")
    @api.response(404, "Transaction not found")
    @jwt_required()
    @require_ownership("transaction")
    def post(self, id: int) -> tuple[dict[str, any], int]:
        """Complete (sell) a transaction"""
        data: dict[str, any] = request.json

        # Validate input data
        try:
            # Ensure data is a dictionary
            data_dict: dict[str, any] = data if isinstance(data, dict) else {}
            validated_data: dict[str, any] = transaction_complete_schema.load(data_dict)
        except ValidationError as err:
            logger.warning(f"Validation error completing transaction: {err!s}")
            raise ValidationError(
                "Invalid sale data",
                errors={"general": [str(err)]},
            ) from err

        # Safely access sale_price and convert to Decimal
        if validated_data and isinstance(validated_data, dict):
            sale_price_value: any | None = validated_data.get("sale_price")
            if sale_price_value is not None:
                sale_price: float = float(str(sale_price_value))
            else:
                raise ValidationError(
                    "Missing sale price",
                    errors={"sale_price": ["Field is required"]},
                )
        else:
            raise ValidationError(
                "Missing sale price",
                errors={"sale_price": ["Field is required"]},
            )

        with SessionManager() as session:
            # Get current user
            user: User | None = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")

            # Verify ownership
            TransactionService.verify_ownership(session, id, user.id)

            try:
                # Complete the transaction using the service layer
                transaction: TradingTransaction = (
                    TransactionService.complete_transaction(session, id, sale_price)
                )
                return transaction_schema.dump(transaction), 200

            except ValidationError as e:
                logger.warning(f"Validation error completing transaction: {e!s}")
                raise
            except ResourceNotFoundError as e:
                logger.warning(f"Resource not found: {e!s}")
                raise
            except BusinessLogicError as e:
                logger.error(f"Business logic error: {e!s}")
                raise
            except Exception as e:
                logger.error(f"Error completing transaction: {e!s}")
                raise BusinessLogicError(
                    f"Could not complete transaction: {e!s}",
                ) from e


@api.route("/<int:id>/cancel")
@api.param("id", "The transaction identifier")
@api.response(404, "Transaction not found")
class TransactionCancel(Resource):
    """Cancel a transaction"""

    @api.doc("cancel_transaction")
    @api.expect(transaction_cancel_model)
    @api.marshal_with(transaction_model)
    @api.response(200, "Transaction cancelled")
    @api.response(400, "Validation error or transaction already complete")
    @api.response(401, "Unauthorized")
    @api.response(404, "Transaction not found")
    @jwt_required()
    @require_ownership("transaction")
    def post(self, id: int) -> tuple[dict[str, any], int]:
        """Cancel a transaction"""
        data: dict[str, any] = request.json or {}

        # Validate input data
        try:
            # Ensure data is a dictionary
            data_dict: dict[str, any] = data if isinstance(data, dict) else {}
            validated_data: dict[str, any] = transaction_cancel_schema.load(data_dict)
        except ValidationError as err:
            logger.warning(f"Validation error cancelling transaction: {err!s}")
            raise ValidationError(
                "Invalid cancellation data",
                errors={"general": [str(err)]},
            ) from err

        # Safely access reason
        reason = "User cancelled"
        if validated_data and isinstance(validated_data, dict):
            reason: str | None = validated_data.get("reason", reason)

        with SessionManager() as session:
            # Get current user
            user: User | None = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")

            # Verify ownership
            TransactionService.verify_ownership(session, id, user.id)

            try:
                # Cancel the transaction using the service layer
                transaction: TradingTransaction = TransactionService.cancel_transaction(
                    session,
                    id,
                    reason,
                )
                return transaction_schema.dump(transaction), 200

            except ValidationError as e:
                logger.warning(f"Validation error cancelling transaction: {e!s}")
                raise
            except ResourceNotFoundError as e:
                logger.warning(f"Resource not found: {e!s}")
                raise
            except BusinessLogicError as e:
                logger.error(f"Business logic error: {e!s}")
                raise
            except Exception as e:
                logger.error(f"Error cancelling transaction: {e!s}")
                raise BusinessLogicError(
                    f"Could not cancel transaction: {e!s}",
                ) from e


@api.route("/services/<int:service_id>")
@api.param("service_id", "The trading service identifier")
@api.response(404, "Service not found")
class ServiceTransactions(Resource):
    """Resource for managing transactions of a specific trading service."""

    @api.doc(
        "list_service_transactions",
        params={
            "page": "Page number (default: 1)",
            "page_size": "Number of items per page (default: 20, max: 100)",
            "state": "Filter by transaction state (OPEN, CLOSED, CANCELLED)",
            "sort": "Sort field (e.g., created_at, shares)",
            "order": "Sort order (asc or desc, default: desc)",
        },
    )
    @api.marshal_with(transaction_list_model)
    @api.response(200, "Success")
    @api.response(401, "Unauthorized")
    @api.response(404, "Service not found")
    @jwt_required()
    @require_ownership("service")
    def get(
        self,
        service_id: int,
    ) -> tuple[dict[str, any], int]:
        """Get all transactions for a specific trading service."""
        with SessionManager() as session:
            # Verify service exists
            service: TradingService | None = session.execute(
                select(TradingService).where(TradingService.id == service_id),
            ).scalar_one_or_none()
            if not service:
                raise ResourceNotFoundError(
                    f"TradingService with ID {service_id} not found",
                    resource_id=service_id,
                )

            try:
                # Parse query parameters
                state: str | None = request.args.get("state")
                if state and not TransactionState.is_valid(state):
                    raise ValidationError(f"Invalid transaction state: {state}")

                # Get transactions for this service
                if state:
                    transactions: list[any] = TransactionService.get_by_service(
                        session,
                        service_id,
                        state,
                        )
                else:
                    transactions: list[any] = TransactionService.get_by_service(
                        session,
                        service_id,
                    )

                # Get sort parameters
                sort_field: str = request.args.get("sort", "purchase_date")
                sort_order: str = request.args.get("order", "desc")

                # Define a sort key getter that handles missing attributes
                def get_sort_key(t: any) -> any:
                    # Get attribute safely or use purchase_date as fallback
                    if hasattr(t, sort_field):
                        return getattr(t, sort_field)
                    return t.purchase_date

                # Sort the transactions with explicit list casting
                transactions = sorted(
                    list(transactions),
                    key=get_sort_key,
                    reverse=(sort_order.lower() == "desc"),
                )

                # Apply pagination using the utility function
                result: dict[str, any] = apply_pagination(transactions)

                # Serialize the results
                result["items"] = transactions_schema.dump(result["items"])

                return result

            except ValidationError as e:
                logger.warning(f"Validation error listing transactions: {e!s}")
                raise
            except Exception as e:
                logger.error(f"Error listing transactions: {e!s}")
                raise BusinessLogicError(
                    f"Could not list transactions: {e!s}",
                ) from e

    @api.doc("create_transaction")
    @api.expect(transaction_create_model)
    @api.marshal_with(transaction_model)
    @api.response(201, "Transaction created")
    @api.response(400, "Validation error")
    @api.response(401, "Unauthorized")
    @api.response(404, "Service not found")
    @jwt_required()
    @require_ownership("service")
    def post(self) -> tuple[dict[str, any], int]:
        """Create a new trading transaction (buy)"""
        data: dict[str, any] = request.json

        # Validate input data
        try:
            validated_data: dict[str, any] = transaction_create_schema.load(data or {})
        except ValidationError as err:
            logger.warning(f"Validation error creating transaction: {err!s}")
            raise ValidationError(
                "Invalid transaction data",
                errors={"general": [str(err)]},
            ) from err

        # Safety check to ensure validated_data is a dictionary
        if not validated_data or not isinstance(validated_data, dict):
            raise ValidationError("Invalid transaction data format")

        service_id: int | None = validated_data.get("service_id")
        if not service_id:
            raise ValidationError("Missing service_id")

        with SessionManager() as session:
            # Get current user and verify service ownership
            user: User | None = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")

            # Verify service belongs to user
            verify_resource_ownership(
                session=session,
                resource_type="service",
                resource_id=service_id,
                user_id=user.id,
            )

            try:
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

                return transaction_schema.dump(transaction), 201

            except ValidationError as e:
                logger.warning(f"Validation error creating transaction: {e!s}")
                raise
            except ResourceNotFoundError as e:
                logger.warning(f"Resource not found: {e!s}")
                raise
            except BusinessLogicError as e:
                logger.error(f"Business logic error: {e!s}")
                raise
            except Exception as e:
                logger.error(f"Error creating transaction: {e!s}")
                raise BusinessLogicError(
                    f"Could not create transaction: {e!s}",
                ) from e


@api.route("/<int:id>/notes")
@api.param("id", "The transaction identifier")
@api.response(404, "Transaction not found")
class TransactionNotes(Resource):
    """Update transaction notes"""

    @api.doc("update_transaction_notes")
    @api.expect(
        api.model(
            "TransactionNotes",
            {"notes": fields.String(required=True, description="Transaction notes")},
        ),
    )
    @api.marshal_with(transaction_model)
    @api.response(200, "Notes updated")
    @api.response(400, "Validation error")
    @api.response(401, "Unauthorized")
    @api.response(404, "Transaction not found")
    @jwt_required()
    @require_ownership("transaction")
    def put(self, id: int) -> tuple[dict[str, any], int]:
        """Update transaction notes"""
        data: dict[str, any] = request.json

        # Check if data is None or doesn't contain notes
        if data is None or not isinstance(data, dict) or "notes" not in data:
            raise ValidationError(
                "Missing required field",
                errors={"notes": ["Field is required"]},
            )

        with SessionManager() as session:
            # Get current user
            user: User | None = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")

            # Verify ownership
            TransactionService.verify_ownership(session, id, user.id)

            try:
                # Update notes using the service layer
                notes: str = data.get("notes", "") if isinstance(data, dict) else ""
                transaction: TradingTransaction = (
                    TransactionService.update_transaction_notes(session, id, notes)
                )
                return transaction_schema.dump(transaction), 200

            except ResourceNotFoundError as e:
                logger.warning(f"Resource not found: {e!s}")
                raise
            except Exception as e:
                logger.error(f"Error updating transaction notes: {e!s}")
                raise BusinessLogicError(
                    f"Could not update transaction notes: {e!s}",
                ) from e


@api.route("/services/<int:service_id>/metrics")
@api.param("service_id", "The trading service identifier")
@api.response(404, "Service not found")
class TransactionMetrics(Resource):
    """Get metrics for transactions of a service"""

    @api.doc("get_transaction_metrics")
    @api.response(200, "Success")
    @api.response(401, "Unauthorized")
    @api.response(404, "Service not found")
    @jwt_required()
    @require_ownership("service")
    def get(
        self,
        service_id: int,
    ) -> tuple[dict[str, any], int]:
        """Get metrics for transactions of a service"""
        with SessionManager() as session:
            # Check if service exists and belongs to user
            # (require_ownership decorator already verifies ownership)
            service: TradingService | None = session.execute(
                select(TradingService).where(TradingService.id == service_id),
            ).scalar_one_or_none()
            if not service:
                raise ResourceNotFoundError(
                    f"TradingService with ID {service_id} not found",
                    resource_id=service_id,
                )

            try:
                # Calculate metrics using the service layer
                metrics: dict[str, any] = (
                    TransactionService.calculate_transaction_metrics(
                        session,
                        service_id,
                    )
                )
                return metrics, 200

            except Exception as e:
                logger.error(f"Error calculating transaction metrics: {e!s}")
                raise BusinessLogicError(
                    f"Could not calculate transaction metrics: {e!s}",
                ) from e
