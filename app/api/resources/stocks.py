"""
Stock API resources.
"""
from flask import request
from flask_restx import Namespace, Resource, fields, abort
from sqlalchemy.exc import IntegrityError
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.database import get_db_session
from app.models import Stock
from app.api.schemas.stock import stock_schema, stocks_schema, stock_input_schema
from app.api import apply_pagination, apply_filters
from app.api.auth import admin_required

# Create namespace
api = Namespace('stocks', description='Stock operations')

# Define API models
stock_model = api.model('Stock', {
    'id': fields.Integer(readonly=True, description='Stock identifier'),
    'symbol': fields.String(required=True, description='Stock ticker symbol'),
    'name': fields.String(description='Company name'),
    'is_active': fields.Boolean(description='Whether the stock is active'),
    'sector': fields.String(description='Industry sector'),
    'description': fields.String(description='Stock description')
})

stock_input_model = api.model('StockInput', {
    'symbol': fields.String(required=True, description='Stock ticker symbol'),
    'name': fields.String(description='Company name'),
    'is_active': fields.Boolean(description='Whether the stock is active'),
    'sector': fields.String(description='Industry sector'),
    'description': fields.String(description='Stock description')
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
stock_list_model = api.model('StockList', {
    'items': fields.List(fields.Nested(stock_model), description='List of stocks'),
    'pagination': fields.Nested(pagination_model, description='Pagination information')
})

@api.route('/')
class StockList(Resource):
    """Resource for managing the collection of stocks."""
    
    @api.doc('list_stocks',
             params={
                 'page': 'Page number (default: 1)',
                 'page_size': 'Number of items per page (default: 20, max: 100)',
                 'symbol': 'Filter by symbol (exact match)',
                 'symbol_like': 'Filter by symbol (partial match)',
                 'is_active': 'Filter by active status (true/false)',
                 'sector': 'Filter by sector',
                 'sort': 'Sort field (e.g., symbol, name)',
                 'order': 'Sort order (asc or desc, default: asc)'
             })
    @api.marshal_with(stock_list_model)
    @api.response(200, 'Success')
    def get(self):
        """Get all stocks with filtering and pagination."""
        with get_db_session() as session:
            # Get base query
            query = session.query(Stock)
            
            # Apply filters
            query = apply_filters(query, Stock)
            
            # Apply pagination
            result = apply_pagination(query)
            
            # Serialize the results
            result['items'] = stocks_schema.dump(result['items'])
            
            return result
    
    @api.doc('create_stock')
    @api.expect(stock_input_model)
    @api.marshal_with(stock_model, code=201)
    @api.response(201, 'Stock created successfully')
    @api.response(400, 'Invalid input')
    @api.response(401, 'Unauthorized')
    @api.response(403, 'Admin privileges required')
    @api.response(409, 'Stock with this symbol already exists')
    @jwt_required()
    @admin_required
    def post(self):
        """Create a new stock. Requires admin privileges."""
        try:
            data = request.json
            # Validate and deserialize input
            stock = stock_input_schema.load(data)
            
            with get_db_session() as session:
                session.add(stock)
                session.commit()
                # Refresh to get the ID and other database-generated values
                session.refresh(stock)
                return stock_schema.dump(stock), 201
        except IntegrityError:
            abort(409, 'Stock with this symbol already exists')
        except Exception as e:
            abort(400, str(e))

@api.route('/<int:id>')
@api.param('id', 'The stock identifier')
@api.response(404, 'Stock not found')
class StockResource(Resource):
    """Resource for managing individual stocks."""
    
    @api.doc('get_stock')
    @api.marshal_with(stock_model)
    @api.response(200, 'Success')
    @api.response(404, 'Stock not found')
    def get(self, id):
        """Get a stock by ID."""
        with get_db_session() as session:
            stock = session.query(Stock).filter_by(id=id).first()
            if stock is None:
                abort(404, 'Stock not found')
            return stock_schema.dump(stock)
    
    @api.doc('update_stock')
    @api.expect(stock_input_model)
    @api.marshal_with(stock_model)
    @api.response(200, 'Stock updated successfully')
    @api.response(400, 'Invalid input')
    @api.response(401, 'Unauthorized')
    @api.response(403, 'Admin privileges required')
    @api.response(404, 'Stock not found')
    @jwt_required()
    @admin_required
    def put(self, id):
        """Update a stock. Requires admin privileges."""
        try:
            data = request.json
            
            with get_db_session() as session:
                stock = session.query(Stock).filter_by(id=id).first()
                if stock is None:
                    abort(404, 'Stock not found')
                
                # Update fields that are provided
                for key, value in data.items():
                    if hasattr(stock, key):
                        setattr(stock, key, value)
                
                session.commit()
                return stock_schema.dump(stock)
        except Exception as e:
            abort(400, str(e))
    
    @api.doc('delete_stock')
    @api.response(204, 'Stock deleted')
    @api.response(401, 'Unauthorized')
    @api.response(403, 'Admin privileges required')
    @api.response(404, 'Stock not found')
    @jwt_required()
    @admin_required
    def delete(self, id):
        """Delete a stock. Requires admin privileges."""
        with get_db_session() as session:
            stock = session.query(Stock).filter_by(id=id).first()
            if stock is None:
                abort(404, 'Stock not found')
            
            session.delete(stock)
            session.commit()
            return '', 204

@api.route('/symbol/<string:symbol>')
@api.param('symbol', 'The stock symbol')
@api.response(404, 'Stock not found')
class StockBySymbol(Resource):
    """Resource for retrieving stocks by symbol."""
    
    @api.doc('get_stock_by_symbol')
    @api.marshal_with(stock_model)
    @api.response(200, 'Success')
    @api.response(404, 'Stock not found')
    def get(self, symbol):
        """Get a stock by symbol."""
        with get_db_session() as session:
            stock = session.query(Stock).filter_by(symbol=symbol.upper()).first()
            if stock is None:
                abort(404, f'Stock with symbol {symbol} not found')
            return stock_schema.dump(stock) 