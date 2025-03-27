"""
Trading Transactions API resources.
"""
from flask import request, current_app
from flask_restx import Namespace, Resource, fields, abort
from datetime import datetime
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.database import get_db_session
from app.models import TradingTransaction, TransactionState, TradingService, User
from app.api.schemas.trading_transaction import (
    transaction_schema, 
    transactions_schema,
    transaction_complete_schema,
    transaction_create_schema,
    transaction_cancel_schema
)
from app.api.schemas.trading_service import service_schema
from app.api import apply_pagination, apply_filters
from app.utils.errors import ValidationError, ResourceNotFoundError, AuthorizationError
from app.utils.auth import require_ownership, verify_resource_ownership, get_current_user

# Create namespace
api = Namespace('transactions', description='Trading transaction operations')

# Define API models
transaction_model = api.model('Transaction', {
    'id': fields.Integer(readonly=True, description='The transaction identifier'),
    'service_id': fields.Integer(required=True, description='The trading service identifier'),
    'stock_id': fields.Integer(description='The stock identifier'),
    'stock_symbol': fields.String(required=True, description='The stock symbol'),
    'shares': fields.Float(required=True, description='Number of shares'),
    'state': fields.String(description='Transaction state'),
    'purchase_price': fields.Float(description='Purchase price per share'),
    'sale_price': fields.Float(description='Sale price per share (if sold)'),
    'gain_loss': fields.Float(description='Gain or loss amount (if sold)'),
    'purchase_date': fields.DateTime(description='Date of purchase'),
    'sale_date': fields.DateTime(description='Date of sale (if sold)'),
    'is_complete': fields.Boolean(description='Whether the transaction is completed'),
    'is_profitable': fields.Boolean(description='Whether the transaction is profitable (if sold)')
})

transaction_complete_model = api.model('TransactionComplete', {
    'sale_price': fields.Float(required=True, description='Sale price per share')
})

# Add pagination model
pagination_model = api.model('Pagination', {
    'page': fields.Integer(description='Current page number'),
    'page_size': fields.Integer(description='Number of items per page'),
    'total_items': fields.Integer(description='Total number of items'),
    'total_pages': fields.Integer(description='Total number of pages'),
    'has_next': fields.Boolean(description='Whether there is a next page'),
    'has_prev': fields.Boolean(description='Whether there is a previous page')
})

# Add paginated list model
transaction_list_model = api.model('TransactionList', {
    'items': fields.List(fields.Nested(transaction_model), description='List of transactions'),
    'pagination': fields.Nested(pagination_model, description='Pagination information')
})

@api.route('/')
class TransactionList(Resource):
    """Shows a list of all transactions, and lets you create a new transaction"""
    
    @api.doc('list_transactions')
    @api.marshal_list_with(transaction_model)
    @api.response(200, 'Success')
    @api.response(401, 'Unauthorized')
    @jwt_required()
    def get(self):
        """List all trading transactions"""
        with get_db_session() as session:
            # Get current user
            user = get_current_user(session)
            
            if not user:
                raise AuthorizationError("User not authenticated")
            
            # Get all services for this user
            user_services = session.query(TradingService).filter_by(user_id=user.id).all()
            service_ids = [service.id for service in user_services]
            
            # Get transactions for these services
            transactions = session.query(TradingTransaction).filter(
                TradingTransaction.service_id.in_(service_ids)
            ).all()
            
            return transactions_schema.dump(transactions)
    
    @api.doc('create_transaction')
    @api.expect(api.model('TransactionCreate', {
        'service_id': fields.Integer(required=True, description='The trading service identifier'),
        'stock_symbol': fields.String(required=True, description='The stock symbol'),
        'shares': fields.Float(required=True, description='Number of shares'),
        'purchase_price': fields.Float(required=True, description='Purchase price per share')
    }))
    @api.marshal_with(transaction_model, code=201)
    @api.response(201, 'Transaction created')
    @api.response(400, 'Validation error')
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Service not found')
    @jwt_required()
    def post(self):
        """Create a new trading transaction (buy)"""
        data = request.json
        
        # Validate input data
        errors = transaction_create_schema.validate(data)
        if errors:
            raise ValidationError("Invalid transaction data", errors=errors)
            
        service_id = data['service_id']
        
        with get_db_session() as session:
            # Get current user and verify service ownership
            user = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")
                
            # Verify service belongs to user
            verify_resource_ownership(
                session=session,
                resource_type='service',
                resource_id=service_id,
                user_id=user.id
            )
                
            try:
                # Create the transaction
                transaction = TradingTransaction.create_buy_transaction(
                    session,
                    service_id=service_id,
                    stock_symbol=data['stock_symbol'],
                    shares=data['shares'],
                    purchase_price=data['purchase_price']
                )
                
                session.add(transaction)
                session.commit()
                
                return transaction_schema.dump(transaction), 201
                
            except ValueError as e:
                current_app.logger.error(f"Error creating transaction: {str(e)}")
                raise ValidationError(str(e))

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
        with get_db_session() as session:
            transaction = session.query(TradingTransaction).filter_by(id=id).first()
            if not transaction:
                raise ResourceNotFoundError('Transaction', id)
                
            return transaction_schema.dump(transaction)

@api.route('/<int:id>/complete')
@api.param('id', 'The transaction identifier')
@api.response(404, 'Transaction not found')
class TransactionComplete(Resource):
    """Complete (sell) a transaction"""
    
    @api.doc('complete_transaction')
    @api.expect(api.model('TransactionComplete', {
        'sale_price': fields.Float(required=True, description='Sale price per share')
    }))
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
        errors = transaction_complete_schema.validate(data)
        if errors:
            raise ValidationError("Invalid sale data", errors=errors)
            
        sale_price = data['sale_price']
        
        with get_db_session() as session:
            # Get the transaction
            transaction = session.query(TradingTransaction).filter_by(id=id).first()
            if not transaction:
                raise ResourceNotFoundError('Transaction', id)
                
            try:
                # Complete the transaction
                result = transaction.complete_transaction(session, sale_price)
                session.commit()
                return result
                
            except ValueError as e:
                current_app.logger.error(f"Error completing transaction: {str(e)}")
                raise ValidationError(str(e))

@api.route('/<int:id>/cancel')
@api.param('id', 'The transaction identifier')
@api.response(404, 'Transaction not found')
class TransactionCancel(Resource):
    """Cancel a transaction"""
    
    @api.doc('cancel_transaction')
    @api.expect(api.model('TransactionCancel', {
        'reason': fields.String(description='Reason for cancellation')
    }))
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
        errors = transaction_cancel_schema.validate(data)
        if errors:
            raise ValidationError("Invalid cancellation data", errors=errors)
        
        with get_db_session() as session:
            # Get the transaction
            transaction = session.query(TradingTransaction).filter_by(id=id).first()
            if not transaction:
                raise ResourceNotFoundError('Transaction', id)
                
            try:
                # Cancel the transaction
                reason = data.get('reason', 'User cancelled')
                result = transaction.cancel_transaction(session, reason)
                session.commit()
                return result
                
            except ValueError as e:
                current_app.logger.error(f"Error cancelling transaction: {str(e)}")
                raise ValidationError(str(e))

@api.route('/services/<int:service_id>')
@api.param('service_id', 'The trading service identifier')
class ServiceTransactions(Resource):
    """Resource for getting transactions for a specific service."""
    
    @api.doc('get_service_transactions',
             params={
                 'page': 'Page number (default: 1)',
                 'page_size': 'Number of items per page (default: 20, max: 100)',
                 'state': 'Filter by transaction state (e.g., OPEN, CLOSED)',
                 'sort': 'Sort field (e.g., purchase_date, purchase_price)',
                 'order': 'Sort order (asc or desc, default: asc)'
             })
    @api.marshal_with(transaction_list_model)
    @api.response(200, 'Success')
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Service not found')
    @jwt_required()
    @require_ownership('service', id_parameter='service_id')
    def get(self, service_id):
        """Get all transactions for a service with filtering and pagination."""
        with get_db_session() as session:
            # Get base query
            query = session.query(TradingTransaction).filter_by(service_id=service_id)
            
            # Apply filters
            query = apply_filters(query, TradingTransaction)
            
            # Apply pagination
            result = apply_pagination(query)
            
            # Serialize the results
            result['items'] = transactions_schema.dump(result['items'])
            
            return result 