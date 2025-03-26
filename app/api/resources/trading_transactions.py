"""
Trading Transactions API resources.
"""
from flask import request, current_app
from flask_restx import Namespace, Resource, fields, abort
from datetime import datetime
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.database import get_db_session
from app.models import TradingTransaction, TransactionState
from app.api.schemas.trading_transaction import (
    transaction_schema, 
    transactions_schema,
    transaction_complete_schema
)
from app.api.schemas.trading_service import service_schema
from app.api import apply_pagination, apply_filters

# Create namespace
api = Namespace('transactions', description='Trading transaction operations')

# Define API models
transaction_model = api.model('TradingTransaction', {
    'id': fields.Integer(readonly=True, description='Transaction identifier'),
    'service_id': fields.Integer(description='Service identifier'),
    'stock_id': fields.Integer(description='Stock identifier'),
    'stock_symbol': fields.String(description='Stock ticker symbol'),
    'shares': fields.Integer(description='Number of shares'),
    'state': fields.String(description='Transaction state (OPEN, CLOSED, CANCELLED)'),
    'purchase_price': fields.Float(description='Purchase price per share'),
    'sale_price': fields.Float(description='Sale price per share'),
    'gain_loss': fields.Float(description='Total gain/loss from this transaction'),
    'purchase_date': fields.DateTime(description='Purchase date/time'),
    'sale_date': fields.DateTime(description='Sale date/time'),
    'created_at': fields.DateTime(description='Creation timestamp'),
    'updated_at': fields.DateTime(description='Last update timestamp'),
    'is_complete': fields.Boolean(readonly=True, description='Whether the transaction is complete'),
    'is_profitable': fields.Boolean(readonly=True, description='Whether the transaction made a profit')
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
    """Resource for managing the collection of transactions."""
    
    @api.doc('list_transactions',
             params={
                 'page': 'Page number (default: 1)',
                 'page_size': 'Number of items per page (default: 20, max: 100)',
                 'state': 'Filter by transaction state (e.g., OPEN, CLOSED)',
                 'service_id': 'Filter by service ID',
                 'stock_symbol': 'Filter by stock symbol',
                 'purchase_date_after': 'Filter by purchase date (ISO format)',
                 'purchase_date_before': 'Filter by purchase date (ISO format)',
                 'sort': 'Sort field (e.g., purchase_date, purchase_price)',
                 'order': 'Sort order (asc or desc, default: asc)'
             })
    @api.marshal_with(transaction_list_model)
    @api.response(200, 'Success')
    @api.response(401, 'Unauthorized')
    @jwt_required()
    def get(self):
        """Get all transactions with filtering and pagination."""
        with get_db_session() as session:
            # Get base query
            query = session.query(TradingTransaction)
            
            # Apply filters
            query = apply_filters(query, TradingTransaction)
            
            # Apply pagination
            result = apply_pagination(query)
            
            # Serialize the results
            result['items'] = transactions_schema.dump(result['items'])
            
            return result

@api.route('/<int:id>')
@api.param('id', 'The transaction identifier')
@api.response(404, 'Transaction not found')
class TransactionResource(Resource):
    """Resource for managing individual transactions."""
    
    @api.doc('get_transaction')
    @api.marshal_with(transaction_model)
    @api.response(200, 'Success')
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Transaction not found')
    @jwt_required()
    def get(self, id):
        """Get a transaction by ID."""
        with get_db_session() as session:
            transaction = session.query(TradingTransaction).filter_by(id=id).first()
            if transaction is None:
                abort(404, 'Transaction not found')
            return transaction_schema.dump(transaction)
    
    @api.doc('complete_transaction')
    @api.expect(transaction_complete_model)
    @api.marshal_with(transaction_model)
    @api.response(200, 'Transaction completed successfully')
    @api.response(400, 'Invalid input or transaction already completed')
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Transaction not found')
    @jwt_required()
    def put(self, id):
        """Complete (sell) a transaction."""
        try:
            data = request.json
            
            # Validate the sale data
            validated_data = transaction_complete_schema.load(data)
            
            with get_db_session() as session:
                transaction = session.query(TradingTransaction).filter_by(id=id).first()
                if transaction is None:
                    abort(404, 'Transaction not found')
                
                # Check if transaction is already completed
                if transaction.state == TransactionState.CLOSED:
                    abort(400, 'Transaction is already completed')
                
                # Complete the transaction
                transaction.sale_price = data['sale_price']
                transaction.sale_date = datetime.utcnow()
                transaction.state = TransactionState.CLOSED
                transaction.gain_loss = (transaction.sale_price - transaction.purchase_price) * transaction.shares
                
                # Update the service as well
                service = transaction.service
                service.fund_balance += (transaction.sale_price * transaction.shares)
                service.total_gain_loss += transaction.gain_loss
                service.current_shares -= transaction.shares
                service.sell_count += 1
                
                # If all shares are sold, switch back to BUY mode
                from app.models import TradingMode
                if service.current_shares == 0:
                    service.mode = TradingMode.BUY
                
                session.commit()
                result = transaction_schema.dump(transaction)
                
                # Emit WebSocket events to transactions room
                current_app.socketio.emit('transaction_update', {
                    'action': 'completed',
                    'transaction': result
                }, room='transactions')
                
                # Also emit to services room for general updates
                current_app.socketio.emit('service_update', {
                    'action': 'transaction_completed',
                    'service_id': transaction.service_id,
                    'transaction_id': transaction.id
                }, room='services')
                
                # Create service room name for targeted updates
                service_room = f"service_{transaction.service_id}"
                service_data = service_schema.dump(service)
                
                current_app.socketio.emit('service_update', {
                    'action': 'updated',
                    'service': service_data
                }, room=service_room)
                
                return result
        except Exception as e:
            current_app.logger.error(f"Error completing transaction: {str(e)}")
            abort(400, str(e))

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
    def get(self, service_id):
        """Get all transactions for a service with filtering and pagination."""
        with get_db_session() as session:
            # Check if service exists
            from app.models import TradingService
            service = session.query(TradingService).filter_by(id=service_id).first()
            if not service:
                abort(404, 'Trading service not found')
                
            # Get base query
            query = session.query(TradingTransaction).filter_by(service_id=service_id)
            
            # Apply filters
            query = apply_filters(query, TradingTransaction)
            
            # Apply pagination
            result = apply_pagination(query)
            
            # Serialize the results
            result['items'] = transactions_schema.dump(result['items'])
            
            return result 