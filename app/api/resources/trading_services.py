"""
Trading Services API resources.
"""
from flask import request, current_app
from flask_restx import Namespace, Resource, fields, abort
from sqlalchemy.exc import IntegrityError
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.database import get_db_session
from app.models import TradingService, ServiceState, TradingMode, User
from app.api.schemas.trading_service import (
    service_schema, 
    services_schema, 
    service_create_schema,
    service_update_schema
)
from app.api import apply_pagination, apply_filters
from app.api.auth import admin_required

# Create namespace
api = Namespace('services', description='Trading service operations')

# Define API models
service_model = api.model('TradingService', {
    'id': fields.Integer(readonly=True, description='Service identifier'),
    'stock_id': fields.Integer(description='ID of the stock being traded'),
    'stock_symbol': fields.String(required=True, description='Stock ticker symbol'),
    'name': fields.String(description='Service name'),
    'initial_balance': fields.Float(description='Starting balance'),
    'current_balance': fields.Float(description='Current balance'),
    'total_gain_loss': fields.Float(description='Total gain/loss'),
    'current_shares': fields.Integer(description='Current shares held'),
    'state': fields.String(description='Service state (ACTIVE, INACTIVE, etc.)'),
    'mode': fields.String(description='Trading mode (BUY, SELL, HOLD)'),
    'started_at': fields.DateTime(description='Start timestamp'),
    'stopped_at': fields.DateTime(description='Stop timestamp'),
    'buy_count': fields.Integer(description='Number of buy transactions'),
    'sell_count': fields.Integer(description='Number of sell transactions'),
    'created_at': fields.DateTime(description='Creation timestamp'),
    'updated_at': fields.DateTime(description='Last update timestamp')
})

service_create_model = api.model('TradingServiceCreate', {
    'stock_symbol': fields.String(required=True, description='Stock ticker symbol'),
    'name': fields.String(description='Service name'),
    'initial_balance': fields.Float(required=True, description='Initial balance')
})

service_update_model = api.model('TradingServiceUpdate', {
    'name': fields.String(description='Service name'),
    'state': fields.String(description='Service state (ACTIVE, INACTIVE, etc.)'),
    'mode': fields.String(description='Trading mode (BUY, SELL, HOLD)')
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
service_list_model = api.model('TradingServiceList', {
    'items': fields.List(fields.Nested(service_model), description='List of services'),
    'pagination': fields.Nested(pagination_model, description='Pagination information')
})

@api.route('/')
class ServiceList(Resource):
    """Resource for managing the collection of trading services."""
    
    @api.doc('list_services',
             params={
                 'page': 'Page number (default: 1)',
                 'page_size': 'Number of items per page (default: 20, max: 100)',
                 'state': 'Filter by service state (e.g., ACTIVE, INACTIVE)',
                 'stock_symbol': 'Filter by stock symbol',
                 'mode': 'Filter by trading mode (e.g., BUY, SELL)',
                 'created_after': 'Filter by creation date (ISO format)',
                 'sort': 'Sort field (e.g., created_at, current_balance)',
                 'order': 'Sort order (asc or desc, default: asc)'
             })
    @api.marshal_with(service_list_model)
    @api.response(200, 'Success')
    @api.response(401, 'Unauthorized')
    @jwt_required()
    def get(self):
        """Get all trading services with filtering and pagination."""
        with get_db_session() as session:
            # Get base query
            query = session.query(TradingService)
            
            # Apply filters
            query = apply_filters(query, TradingService)
            
            # Apply pagination
            result = apply_pagination(query)
            
            # Serialize the results
            result['items'] = services_schema.dump(result['items'])
            
            return result
    
    @api.doc('create_service')
    @api.expect(service_create_model)
    @api.marshal_with(service_model, code=201)
    @api.response(201, 'Service created successfully')
    @api.response(400, 'Invalid input')
    @api.response(401, 'Unauthorized')
    @jwt_required()
    def post(self):
        """Create a new trading service."""
        try:
            data = request.json
            # Validate and deserialize input
            service = service_create_schema.load(data)
            
            # Get user ID from token
            user_id = get_jwt_identity()
            
            with get_db_session() as session:
                # Check if the stock exists and get its ID if available
                from app.models import Stock
                stock = session.query(Stock).filter_by(symbol=data['stock_symbol']).first()
                if stock:
                    service.stock_id = stock.id
                
                # Associate with the current user (in a real app, you might store user_id in the service)
                user = session.query(User).filter_by(id=user_id).first()
                if not user:
                    abort(401, "User not found")
                
                session.add(service)
                session.commit()
                session.refresh(service)
                
                result = service_schema.dump(service)
                
                # Emit WebSocket event
                current_app.socketio.emit('service_update', {
                    'action': 'created',
                    'service': result
                }, room='services')
                
                return result, 201
        except Exception as e:
            current_app.logger.error(f"Error creating service: {str(e)}")
            abort(400, str(e))

@api.route('/<int:id>')
@api.param('id', 'The trading service identifier')
@api.response(404, 'Trading service not found')
class ServiceResource(Resource):
    """Resource for managing individual trading services."""
    
    @api.doc('get_service')
    @api.marshal_with(service_model)
    @api.response(200, 'Success')
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Trading service not found')
    @jwt_required()
    def get(self, id):
        """Get a trading service by ID."""
        with get_db_session() as session:
            service = session.query(TradingService).filter_by(id=id).first()
            if service is None:
                abort(404, 'Trading service not found')
            return service_schema.dump(service)
    
    @api.doc('update_service')
    @api.expect(service_update_model)
    @api.marshal_with(service_model)
    @api.response(200, 'Service updated successfully')
    @api.response(400, 'Invalid input')
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Trading service not found')
    @jwt_required()
    def put(self, id):
        """Update a trading service."""
        try:
            data = request.json
            
            with get_db_session() as session:
                service = session.query(TradingService).filter_by(id=id).first()
                if service is None:
                    abort(404, 'Trading service not found')
                
                # Validate update data
                validated_data = service_update_schema.load(data)
                
                # Update fields that are provided
                for key, value in data.items():
                    if hasattr(service, key):
                        setattr(service, key, value)
                
                session.commit()
                result = service_schema.dump(service)
                
                # Emit WebSocket event
                current_app.socketio.emit('service_update', {
                    'action': 'updated',
                    'service': result
                }, room=f"service_{id}")
                
                # Also broadcast to the general services room
                current_app.socketio.emit('service_update', {
                    'action': 'updated',
                    'service': result
                }, room='services')
                
                return result
        except Exception as e:
            current_app.logger.error(f"Error updating service: {str(e)}")
            abort(400, str(e))
    
    @api.doc('delete_service')
    @api.response(204, 'Trading service deleted')
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Trading service not found')
    @jwt_required()
    def delete(self, id):
        """Delete a trading service."""
        with get_db_session() as session:
            service = session.query(TradingService).filter_by(id=id).first()
            if service is None:
                abort(404, 'Trading service not found')
            
            session.delete(service)
            session.commit()
            
            # Emit WebSocket event to services room
            current_app.socketio.emit('service_update', {
                'action': 'deleted',
                'service_id': id
            }, room='services')
            
            return '', 204

@api.route('/<int:id>/toggle')
@api.param('id', 'The trading service identifier')
@api.response(404, 'Trading service not found')
class ServiceToggle(Resource):
    """Resource for toggling a trading service state."""
    
    @api.doc('toggle_service')
    @api.marshal_with(service_model)
    @api.response(200, 'Service state toggled successfully')
    @api.response(400, 'Bad request')
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Trading service not found')
    @jwt_required()
    def post(self, id):
        """Toggle a trading service between active and inactive."""
        try:
            with get_db_session() as session:
                service = session.query(TradingService).filter_by(id=id).first()
                if service is None:
                    abort(404, 'Trading service not found')
                
                # Toggle state
                new_state = ServiceState.INACTIVE if service.state == ServiceState.ACTIVE else ServiceState.ACTIVE
                service.state = new_state
                
                session.commit()
                result = service_schema.dump(service)
                
                # Emit WebSocket event
                room = f"service_{id}"
                current_app.socketio.emit('service_update', {
                    'action': 'toggled',
                    'service': result,
                    'new_state': new_state.value
                }, room=room)
                
                return result
        except Exception as e:
            current_app.logger.error(f"Error toggling service: {str(e)}")
            abort(400, str(e)) 