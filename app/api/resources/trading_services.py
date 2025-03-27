"""
Trading Services API resources.
"""
from flask import request, current_app
from flask_restx import Namespace, Resource, fields, abort
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.database import get_db_session
from app.models import TradingService, TradingTransaction, User, ServiceState, TradingMode
from app.api.schemas.trading_service import (
    service_schema, 
    services_schema,
    service_create_schema,
    service_update_schema
)
from app.api import apply_pagination, apply_filters
from app.utils.errors import ValidationError, ResourceNotFoundError, AuthorizationError, BusinessLogicError
from app.utils.auth import require_ownership, verify_resource_ownership, get_current_user

# Create namespace
api = Namespace('services', description='Trading service operations')

# Define models for Swagger documentation
service_model = api.model('TradingService', {
    'id': fields.Integer(readonly=True, description='The service identifier'),
    'user_id': fields.Integer(description='User owning this service'),
    'name': fields.String(required=True, description='Service name'),
    'description': fields.String(description='Service description'),
    'stock_symbol': fields.String(required=True, description='Stock ticker symbol'),
    'service_state': fields.String(description='Service state (ACTIVE, INACTIVE, etc.)'),
    'mode': fields.String(description='Trading mode (BUY or SELL)'),
    'is_active': fields.Boolean(description='Whether the service is active'),
    'initial_balance': fields.Float(required=True, description='Initial fund balance'),
    'fund_balance': fields.Float(description='Current fund balance'),
    'minimum_balance': fields.Float(description='Minimum fund balance to maintain'),
    'allocation_percent': fields.Float(description='Percentage of funds to allocate per trade'),
    'buy_threshold': fields.Float(description='Buy threshold percentage'),
    'sell_threshold': fields.Float(description='Sell threshold percentage'),
    'stop_loss_percent': fields.Float(description='Stop loss percentage'),
    'take_profit_percent': fields.Float(description='Take profit percentage'),
    'current_shares': fields.Float(description='Current shares owned'),
    'buy_count': fields.Integer(description='Total buy transactions'),
    'sell_count': fields.Integer(description='Total sell transactions'),
    'total_gain_loss': fields.Float(description='Total gain/loss amount'),
    'created_at': fields.DateTime(description='Creation timestamp'),
    'updated_at': fields.DateTime(description='Last update timestamp'),
    'is_profitable': fields.Boolean(readonly=True, description='Whether the service is profitable'),
    'performance_pct': fields.Float(readonly=True, description='Performance as percentage of initial balance')
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
service_list_model = api.model('ServiceList', {
    'items': fields.List(fields.Nested(service_model), description='List of services'),
    'pagination': fields.Nested(pagination_model, description='Pagination information')
})

@api.route('/')
class ServiceList(Resource):
    """Shows a list of all trading services, and lets you create a new service"""
    
    @api.doc('list_services',
             params={
                 'page': 'Page number (default: 1)',
                 'page_size': 'Number of items per page (default: 20, max: 100)',
                 'is_active': 'Filter by active status (true/false)',
                 'stock_symbol': 'Filter by stock symbol',
                 'sort': 'Sort field (e.g., created_at, name)',
                 'order': 'Sort order (asc or desc, default: asc)'
             })
    @api.marshal_with(service_list_model)
    @api.response(200, 'Success')
    @api.response(401, 'Unauthorized')
    @jwt_required()
    def get(self):
        """List all trading services for the authenticated user"""
        with get_db_session() as session:
            # Get current user
            user = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")
            
            # Get base query for user's services
            query = session.query(TradingService).filter_by(user_id=user.id)
            
            # Apply filters
            query = apply_filters(query, TradingService)
            
            # Apply pagination
            result = apply_pagination(query)
            
            # Serialize the results
            result['items'] = services_schema.dump(result['items'])
            
            return result
    
    @api.doc('create_service')
    @api.expect(api.model('ServiceCreate', {
        'name': fields.String(required=True, description='Service name'),
        'stock_symbol': fields.String(required=True, description='Stock ticker symbol'),
        'initial_balance': fields.Float(required=True, description='Initial fund balance'),
        'minimum_balance': fields.Float(description='Minimum fund balance to maintain'),
        'allocation_percent': fields.Float(description='Percentage of funds to allocate per trade'),
        'description': fields.String(description='Service description'),
        'is_active': fields.Boolean(description='Whether the service is active')
    }))
    @api.marshal_with(service_model, code=201)
    @api.response(201, 'Service created')
    @api.response(400, 'Validation error')
    @api.response(401, 'Unauthorized')
    @jwt_required()
    def post(self):
        """Create a new trading service"""
        data = request.json
        
        # Validate input data
        errors = service_create_schema.validate(data)
        if errors:
            raise ValidationError("Invalid service data", errors=errors)
            
        with get_db_session() as session:
            # Get current user
            user = get_current_user(session)
            if not user:
                raise AuthorizationError("User not authenticated")
                
            try:
                # Create the service
                service = TradingService.create_service(
                    session=session,
                    user_id=user.id,
                    data=data
                )
                
                return service_schema.dump(service), 201
                
            except ValueError as e:
                current_app.logger.error(f"Error creating service: {str(e)}")
                raise BusinessLogicError(str(e))
            except IntegrityError as e:
                current_app.logger.error(f"Database integrity error: {str(e)}")
                raise BusinessLogicError("Could not create service due to database constraints")

@api.route('/<int:id>')
@api.param('id', 'The trading service identifier')
@api.response(404, 'Service not found')
class ServiceItem(Resource):
    """Shows a single trading service"""
    
    @api.doc('get_service')
    @api.marshal_with(service_model)
    @api.response(200, 'Success')
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Service not found')
    @jwt_required()
    @require_ownership('service')
    def get(self, id):
        """Get a trading service by ID"""
        with get_db_session() as session:
            service = session.query(TradingService).filter_by(id=id).first()
            if not service:
                raise ResourceNotFoundError('TradingService', id)
                
            return service_schema.dump(service)
    
    @api.doc('update_service')
    @api.expect(api.model('ServiceUpdate', {
        'name': fields.String(description='Service name'),
        'description': fields.String(description='Service description'),
        'stock_symbol': fields.String(description='Stock ticker symbol'),
        'is_active': fields.Boolean(description='Whether the service is active'),
        'minimum_balance': fields.Float(description='Minimum fund balance to maintain'),
        'allocation_percent': fields.Float(description='Percentage of funds to allocate per trade'),
        'buy_threshold': fields.Float(description='Buy threshold percentage'),
        'sell_threshold': fields.Float(description='Sell threshold percentage'),
        'stop_loss_percent': fields.Float(description='Stop loss percentage'),
        'take_profit_percent': fields.Float(description='Take profit percentage')
    }))
    @api.marshal_with(service_model)
    @api.response(200, 'Service updated')
    @api.response(400, 'Validation error')
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Service not found')
    @jwt_required()
    @require_ownership('service')
    def put(self, id):
        """Update a trading service"""
        data = request.json
        
        # Validate input data
        errors = service_update_schema.validate(data)
        if errors:
            raise ValidationError("Invalid service data", errors=errors)
            
        with get_db_session() as session:
            service = session.query(TradingService).filter_by(id=id).first()
            if not service:
                raise ResourceNotFoundError('TradingService', id)
                
            try:
                # Update the service
                result = service.update(session, data)
                session.commit()
                return result
                
            except ValueError as e:
                current_app.logger.error(f"Error updating service: {str(e)}")
                raise BusinessLogicError(str(e))
            except IntegrityError as e:
                current_app.logger.error(f"Database integrity error: {str(e)}")
                raise BusinessLogicError("Could not update service due to database constraints")

@api.route('/<int:id>/state')
@api.param('id', 'The trading service identifier')
@api.response(404, 'Service not found')
class ServiceState(Resource):
    """Resource for changing a service's state"""
    
    @api.doc('change_service_state')
    @api.expect(api.model('StateChange', {
        'state': fields.String(required=True, description='New state (ACTIVE, INACTIVE, etc.)')
    }))
    @api.response(200, 'State changed')
    @api.response(400, 'Invalid state')
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Service not found')
    @jwt_required()
    @require_ownership('service')
    def put(self, id):
        """Change the state of a trading service"""
        data = request.json
        
        if 'state' not in data:
            raise ValidationError("Missing required field", errors={'state': ['Field is required']})
            
        # Parse the state string to enum
        try:
            new_state = ServiceState[data['state'].upper()]
        except (KeyError, ValueError):
            valid_states = [s.name for s in ServiceState]
            raise ValidationError(
                "Invalid state value", 
                errors={'state': [f"Must be one of: {', '.join(valid_states)}"]}
            )
            
        with get_db_session() as session:
            service = session.query(TradingService).filter_by(id=id).first()
            if not service:
                raise ResourceNotFoundError('TradingService', id)
                
            try:
                # Change service state
                result = service.change_state(session, new_state)
                session.commit()
                return result
                
            except ValueError as e:
                current_app.logger.error(f"Error changing service state: {str(e)}")
                raise BusinessLogicError(str(e))

@api.route('/<int:id>/toggle')
@api.param('id', 'The trading service identifier')
@api.response(404, 'Service not found')
class ServiceToggle(Resource):
    """Resource for toggling a service's active status"""
    
    @api.doc('toggle_service')
    @api.response(200, 'Service toggled')
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Service not found')
    @jwt_required()
    @require_ownership('service')
    def post(self, id):
        """Toggle the active status of a trading service"""
        with get_db_session() as session:
            service = session.query(TradingService).filter_by(id=id).first()
            if not service:
                raise ResourceNotFoundError('TradingService', id)
                
            try:
                # Toggle service active status
                result = service.toggle_active(session)
                session.commit()
                return result
                
            except ValueError as e:
                current_app.logger.error(f"Error toggling service: {str(e)}")
                raise BusinessLogicError(str(e))

@api.route('/<int:id>/check-buy')
@api.param('id', 'The trading service identifier')
@api.response(404, 'Service not found')
class ServiceBuyCheck(Resource):
    """Resource for checking if a service should buy its configured stock"""
    
    @api.doc('check_buy_condition')
    @api.response(200, 'Buy check completed')
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Service not found')
    @jwt_required()
    @require_ownership('service')
    def get(self, id):
        """Check if the service should buy its configured stock."""
        with get_db_session() as session:
            service = session.query(TradingService).filter_by(id=id).first()
            if not service:
                raise ResourceNotFoundError('TradingService', id)
                
            # Get current price (placeholder - would use actual price in production)
            current_price = 100.0  # Placeholder value
            
            # Check buy condition
            result = service.check_buy_condition(current_price)
            
            # Add service data to response
            result['service_id'] = service.id
            result['stock_symbol'] = service.stock_symbol
            result['timestamp'] = datetime.utcnow().isoformat()
            
            return result

@api.route('/<int:id>/check-sell')
@api.param('id', 'The trading service identifier')
@api.response(404, 'Service not found')
class ServiceSellCheck(Resource):
    """Resource for checking if a service should sell its current holdings"""
    
    @api.doc('check_sell_condition')
    @api.response(200, 'Sell check completed')
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Service not found')
    @jwt_required()
    @require_ownership('service')
    def get(self, id):
        """Check if the service should sell its current holdings."""
        with get_db_session() as session:
            service = session.query(TradingService).filter_by(id=id).first()
            if not service:
                raise ResourceNotFoundError('TradingService', id)
                
            # Get current price (placeholder - would use actual price in production)
            current_price = 100.0  # Placeholder value
            
            # Check sell condition
            result = service.check_sell_condition(current_price)
            
            # Add service data to response
            result['service_id'] = service.id
            result['stock_symbol'] = service.stock_symbol
            result['timestamp'] = datetime.utcnow().isoformat()
            
            return result 