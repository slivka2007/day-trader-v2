"""
Trading Transactions API resources.
"""
import logging
from flask import request
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required
from http import HTTPStatus

from app.services.session_manager import SessionManager
from app.models import TransactionState, TradingService
from app.services.transaction_service import TransactionService
from app.api.schemas.trading_transaction import (
    transaction_schema, 
    transaction_complete_schema,
    transaction_create_schema,
    transaction_cancel_schema
)
from app.api import apply_pagination
from app.utils.errors import ValidationError, ResourceNotFoundError, AuthorizationError, BusinessLogicError
from app.utils.auth import require_ownership, verify_resource_ownership, get_current_user

# Set up logging
logger = logging.getLogger(__name__)

# Create namespace
api = Namespace('transactions', description='Trading transaction operations')

# Define API models
transaction_model = api.model('TradingTransaction', {
    'id': fields.Integer(readonly=True, description='The transaction identifier'),
    'service_id': fields.Integer(required=True, description='The trading service identifier'),
    'stock_id': fields.Integer(description='The stock identifier'),
    'stock_symbol': fields.String(description='Stock ticker symbol'),
    'state': fields.String(description='Transaction state'),
    'shares': fields.Float(description='Number of shares'),
    'purchase_price': fields.Float(description='Purchase price per share'),
    'sale_price': fields.Float(description='Sale price per share'),
    'gain_loss': fields.Float(description='Profit or loss amount'),
    'purchase_date': fields.DateTime(description='Date of purchase'),
    'sale_date': fields.DateTime(description='Date of sale (if sold)'),
    'notes': fields.String(description='Transaction notes'),
    'created_at': fields.DateTime(description='Creation timestamp'),
    'updated_at': fields.DateTime(description='Last update timestamp'),
    'is_complete': fields.Boolean(description='Whether the transaction is complete'),
    'is_profitable': fields.Boolean(description='Whether the transaction is profitable'),
    'duration_days': fields.Integer(description='Duration of transaction in days'),
    'total_cost': fields.Float(description='Total cost of the purchase'),
    'total_revenue': fields.Float(description='Total revenue from the sale'),
    'profit_loss_percent': fields.Float(description='Profit/loss as a percentage')
})

transaction_complete_model = api.model('TransactionComplete', {
    'sale_price': fields.Float(required=True, description='Sale price per share')
})

transaction_create_model = api.model('TransactionCreate', {
    'service_id': fields.Integer(required=True, description='The trading service identifier'),
    'stock_symbol': fields.String(required=True, description='The stock symbol'),
    'shares': fields.Float(required=True, description='Number of shares'),
    'purchase_price': fields.Float(required=True, description='Purchase price per share')
})

transaction_cancel_model = api.model('TransactionCancel', {
    'reason': fields.String(description='Reason for cancellation')
})

# Models for collection responses with pagination
transaction_list_model = api.model('TransactionList', {
    'items': fields.List(fields.Nested(transaction_model), description='List of transactions'),
    'pagination': fields.Nested(api.model('Pagination', {
        'page': fields.Integer(description='Current page number'),
        'page_size': fields.Integer(description='Number of items per page'),
        'total_items': fields.Integer(description='Total number of items'),
        'total_pages': fields.Integer(description='Total number of pages'),
        'has_next': fields.Boolean(description='Whether there is a next page'),
        'has_prev': fields.Boolean(description='Whether there is a previous page')
    }))
})

@api.route('/')
class TransactionList(Resource):
    """Resource for managing transactions."""
    
    @api.doc('list_transactions',
             params={
                 'page': 'Page number (default: 1)',
                 'page_size': 'Number of items per page (default: 20, max: 100)',
                 'service_id': 'Filter by service ID',
                 'state': 'Filter by transaction state (OPEN, CLOSED, CANCELLED)',
                 'sort': 'Sort field (e.g., created_at, purchase_date)',
                 'order': 'Sort order (asc or desc, default: desc)'
             })
    @api.marshal_with(transaction_list_model)
    @api.response(200, 'Success')
    @api.response(401, 'Unauthorized')
    @jwt_required()
    def get(self):
        """List all transactions for the current user."""
        with SessionManager() as session:
            # Get current user
            user = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")
                
            # Get services owned by this user
            user_services = session.query(TradingService).filter_by(user_id=user.id).all()
            if not user_services:
                return {'items': [], 'pagination': {
                    'page': 1, 'page_size': 0, 'total_items': 0,
                    'total_pages': 0, 'has_next': False, 'has_prev': False
                }}
            
            service_ids = [service.id for service in user_services]
            
            # Parse query parameters
            filters = {}
            
            service_id = request.args.get('service_id')
            if service_id and service_id.isdigit() and int(service_id) in service_ids:
                filters['service_id'] = int(service_id)
            
            state = request.args.get('state')
            if state and TransactionState.is_valid(state):
                filters['state'] = state
            
            # Build query from user's services
            all_transactions = []
            try:
                if 'service_id' in filters:
                    # Get transactions for a specific service
                    if 'state' in filters:
                        transactions = TransactionService.get_by_service(
                            session, filters['service_id'], filters['state']
                        )
                    else:
                        transactions = TransactionService.get_by_service(
                            session, filters['service_id']
                        )
                        
                    all_transactions.extend(transactions)
                else:
                    # Get transactions for all user's services
                    for service_id in service_ids:
                        if 'state' in filters:
                            transactions = TransactionService.get_by_service(
                                session, int(service_id), filters['state']  # type: ignore
                            )
                        else:
                            transactions = TransactionService.get_by_service(
                                session, int(service_id)  # type: ignore
                            )
                            
                        all_transactions.extend(transactions)
            
                # Apply sorting
                sort_field = request.args.get('sort', 'purchase_date')
                sort_order = request.args.get('order', 'desc')
                
                all_transactions = sorted(
                    all_transactions,
                    key=lambda t: getattr(t, sort_field, t.purchase_date),  
                    reverse=(sort_order.lower() == 'desc')
                )
                
                # Apply pagination
                paginated_data = apply_pagination(
                    query=all_transactions  # type: ignore
                )
                
                return paginated_data
                
            except ValidationError as e:
                logger.warning(f"Validation error listing transactions: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"Error listing transactions: {str(e)}")
                raise BusinessLogicError(f"Could not list transactions: {str(e)}")

    @api.doc('create_transaction')
    @api.expect(transaction_create_model)
    @api.marshal_with(transaction_model)
    @api.response(201, 'Transaction created')
    @api.response(400, 'Validation error')
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Service not found')
    @jwt_required()
    def post(self):
        """Create a new trading transaction (buy)"""
        data = request.json
        
        # Validate input data
        try:
            validated_data = transaction_create_schema.load(data or {})
        except ValidationError as err:
            logger.warning(f"Validation error creating transaction: {str(err)}")
            raise ValidationError("Invalid transaction data", errors={"general": [str(err)]})
            
        # Safety check to ensure validated_data is a dictionary
        if not validated_data or not isinstance(validated_data, dict):
            raise ValidationError("Invalid transaction data format")
            
        service_id = validated_data.get('service_id')
        if not service_id:
            raise ValidationError("Missing service_id")
        
        with SessionManager() as session:
            # Get current user and verify service ownership
            user = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")
                
            # Verify service belongs to user
            verify_resource_ownership(
                session=session,
                resource_type='service',
                resource_id=service_id,
                user_id=user.id  # type: ignore
            )
                
            try:
                # Create the transaction using the service layer
                transaction = TransactionService.create_buy_transaction(
                    session=session,
                    service_id=service_id,
                    stock_symbol=validated_data.get('stock_symbol', ''),
                    shares=validated_data.get('shares', 0),
                    purchase_price=validated_data.get('purchase_price', 0)
                )
                
                return transaction_schema.dump(transaction), 201
                
            except ValidationError as e:
                logger.warning(f"Validation error creating transaction: {str(e)}")
                raise
            except ResourceNotFoundError as e:
                logger.warning(f"Resource not found: {str(e)}")
                raise
            except BusinessLogicError as e:
                logger.error(f"Business logic error: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"Error creating transaction: {str(e)}")
                raise BusinessLogicError(f"Could not create transaction: {str(e)}")

@api.route('/<int:id>')
@api.param('id', 'The transaction identifier')
@api.response(404, 'Transaction not found')
class TransactionItem(Resource):
    """Shows a single transaction"""
    
    @api.doc('get_transaction')
    @api.marshal_with(transaction_model)
    @api.response(200, 'Success')
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Transaction not found')
    @jwt_required()
    @require_ownership('transaction')
    def get(self, id):
        """Get a transaction by ID"""
        with SessionManager() as session:
            # Get current user
            user = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")
                
            # Verify ownership and get transaction
            transaction = TransactionService.verify_ownership(session, id, int(user.id))  # type: ignore
            return transaction_schema.dump(transaction)
            
    @api.doc('delete_transaction')
    @api.response(204, 'Transaction deleted')
    @api.response(400, 'Transaction cannot be deleted')
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Transaction not found')
    @jwt_required()
    @require_ownership('transaction')
    def delete(self, id):
        """Delete a transaction."""
        with SessionManager() as session:
            # Get current user
            user = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")
                
            # Verify ownership
            TransactionService.verify_ownership(session, id, int(user.id))  # type: ignore
                
            try:
                # Delete the transaction
                TransactionService.delete_transaction(session, id)
                return '', 204
                
            except ResourceNotFoundError as e:
                logger.warning(f"Resource not found: {str(e)}")
                raise
            except BusinessLogicError as e:
                logger.error(f"Business logic error: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"Error deleting transaction: {str(e)}")
                raise BusinessLogicError(f"Could not delete transaction: {str(e)}")

@api.route('/<int:id>/complete')
@api.param('id', 'The transaction identifier')
@api.response(404, 'Transaction not found')
class TransactionComplete(Resource):
    """Complete (sell) a transaction"""
    
    @api.doc('complete_transaction')
    @api.expect(transaction_complete_model)
    @api.marshal_with(transaction_model)
    @api.response(200, 'Transaction completed')
    @api.response(400, 'Validation error or transaction already complete')
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Transaction not found')
    @jwt_required()
    @require_ownership('transaction')
    def post(self, id):
        """Complete (sell) a transaction"""
        data = request.json
        
        # Validate input data
        try:
            validated_data = transaction_complete_schema.load(data)  # type: ignore
        except ValidationError as err:
            logger.warning(f"Validation error completing transaction: {str(err)}")
            raise ValidationError("Invalid sale data", errors={"general": [str(err)]})
            
        sale_price = validated_data['sale_price']  # type: ignore
        
        with SessionManager() as session:
            # Get current user
            user = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")
                
            # Verify ownership
            TransactionService.verify_ownership(session, id, int(user.id))  # type: ignore
                
            try:
                # Complete the transaction using the service layer
                transaction = TransactionService.complete_transaction(session, id, sale_price)
                return transaction_schema.dump(transaction)
                
            except ValidationError as e:
                logger.warning(f"Validation error completing transaction: {str(e)}")
                raise
            except ResourceNotFoundError as e:
                logger.warning(f"Resource not found: {str(e)}")
                raise
            except BusinessLogicError as e:
                logger.error(f"Business logic error: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"Error completing transaction: {str(e)}")
                raise BusinessLogicError(f"Could not complete transaction: {str(e)}")

@api.route('/<int:id>/cancel')
@api.param('id', 'The transaction identifier')
@api.response(404, 'Transaction not found')
class TransactionCancel(Resource):
    """Cancel a transaction"""
    
    @api.doc('cancel_transaction')
    @api.expect(transaction_cancel_model)
    @api.marshal_with(transaction_model)
    @api.response(200, 'Transaction cancelled')
    @api.response(400, 'Validation error or transaction already complete')
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Transaction not found')
    @jwt_required()
    @require_ownership('transaction')
    def post(self, id):
        """Cancel a transaction"""
        data = request.json or {}
        
        # Validate input data
        try:
            validated_data = transaction_cancel_schema.load(data)
        except ValidationError as err:
            logger.warning(f"Validation error cancelling transaction: {str(err)}")  # type: ignore
            raise ValidationError("Invalid cancellation data", errors={"general": [str(err)]})  # type: ignore
        
        reason = validated_data.get('reason', 'User cancelled')  # type: ignore
        
        with SessionManager() as session:
            # Get current user
            user = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")
                
            # Verify ownership
            TransactionService.verify_ownership(session, id, int(user.id))  # type: ignore
                
            try:
                # Cancel the transaction using the service layer
                transaction = TransactionService.cancel_transaction(session, id, reason)
                return transaction_schema.dump(transaction)
                
            except ValidationError as e:
                logger.warning(f"Validation error cancelling transaction: {str(e)}")
                raise
            except ResourceNotFoundError as e:
                logger.warning(f"Resource not found: {str(e)}")
                raise
            except BusinessLogicError as e:
                logger.error(f"Business logic error: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"Error cancelling transaction: {str(e)}")
                raise BusinessLogicError(f"Could not cancel transaction: {str(e)}")

@api.route('/services/<int:service_id>')
@api.param('service_id', 'The trading service identifier')
@api.response(404, 'Service not found')
class ServiceTransactions(Resource):
    """Resource for managing transactions of a specific trading service."""
    
    @api.doc('list_service_transactions',
             params={
                 'page': 'Page number (default: 1)',
                 'page_size': 'Number of items per page (default: 20, max: 100)',
                 'state': 'Filter by transaction state (OPEN, CLOSED, CANCELLED)',
                 'sort': 'Sort field (e.g., created_at, shares)',
                 'order': 'Sort order (asc or desc, default: desc)'
             })
    @api.marshal_with(transaction_list_model)
    @api.response(200, 'Success')
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Service not found')
    @jwt_required()
    @require_ownership('service')
    def get(self, service_id):
        """Get all transactions for a specific trading service."""
        with SessionManager() as session:
            # Check if service exists and belongs to user
            # (require_ownership decorator already verifies ownership)
            service = session.query(TradingService).filter_by(id=service_id).first()
            if not service:
                raise ResourceNotFoundError(f"TradingService with ID {service_id} not found", resource_id=service_id)
            
            # Get transactions for this service
            state = request.args.get('state')
            
            try:
                # Use service layer to get transactions
                if state:
                    transactions = TransactionService.get_by_service(session, service_id, state)
                else:
                    transactions = TransactionService.get_by_service(session, service_id)
                
                # Apply sorting
                sort_field = request.args.get('sort', 'purchase_date')
                sort_order = request.args.get('order', 'desc')
                
                transactions = sorted(
                    transactions,
                    key=lambda t: getattr(t, sort_field, t.purchase_date),  # type: ignore
                    reverse=(sort_order.lower() == 'desc')
                )
                    
                # Apply pagination
                paginated_data = apply_pagination(
                    query=transactions
                )
                
                return paginated_data
                
            except ValidationError as e:
                logger.warning(f"Validation error listing transactions: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"Error listing transactions: {str(e)}")
                raise BusinessLogicError(f"Could not list transactions: {str(e)}")

@api.route('/<int:id>/notes')
@api.param('id', 'The transaction identifier')
@api.response(404, 'Transaction not found')
class TransactionNotes(Resource):
    """Update transaction notes"""
    
    @api.doc('update_transaction_notes')
    @api.expect(api.model('TransactionNotes', {
        'notes': fields.String(required=True, description='Transaction notes')
    }))
    @api.marshal_with(transaction_model)
    @api.response(200, 'Notes updated')
    @api.response(400, 'Validation error')
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Transaction not found')
    @jwt_required()
    @require_ownership('transaction')
    def put(self, id):
        """Update transaction notes"""
        data = request.json
        
        if 'notes' not in data:  # type: ignore
            raise ValidationError("Missing required field", errors={'notes': ['Field is required']})
        
        with SessionManager() as session:
            # Get current user
            user = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")
                
            # Verify ownership
            TransactionService.verify_ownership(session, id, int(user.id))  # type: ignore
                
            try:
                # Update notes using the service layer
                transaction = TransactionService.update_transaction_notes(session, id, data['notes'])  # type: ignore
                return transaction_schema.dump(transaction)
                
            except ResourceNotFoundError as e:
                logger.warning(f"Resource not found: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"Error updating transaction notes: {str(e)}")
                raise BusinessLogicError(f"Could not update transaction notes: {str(e)}")

@api.route('/services/<int:service_id>/metrics')
@api.param('service_id', 'The trading service identifier')
@api.response(404, 'Service not found')
class TransactionMetrics(Resource):
    """Get metrics for transactions of a service"""
    
    @api.doc('get_transaction_metrics')
    @api.response(200, 'Success')
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Service not found')
    @jwt_required()
    @require_ownership('service')
    def get(self, service_id):
        """Get metrics for transactions of a service"""
        with SessionManager() as session:
            # Check if service exists and belongs to user
            # (require_ownership decorator already verifies ownership)
            service = session.query(TradingService).filter_by(id=service_id).first()
            if not service:
                raise ResourceNotFoundError(f"TradingService with ID {service_id} not found", resource_id=service_id)
            
            try:
                # Calculate metrics using the service layer
                metrics = TransactionService.calculate_transaction_metrics(session, service_id)
                return metrics
                
            except Exception as e:
                logger.error(f"Error calculating transaction metrics: {str(e)}")
                raise BusinessLogicError(f"Could not calculate transaction metrics: {str(e)}") 