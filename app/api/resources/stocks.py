"""
Stock API resources.
"""
from flask import request, current_app
from flask_restx import Namespace, Resource, fields
from sqlalchemy.exc import IntegrityError
from flask_jwt_extended import jwt_required
from http import HTTPStatus
from typing import Dict, Any, cast

from app.services.session_manager import SessionManager
from app.models import Stock
from app.services.stock_service import StockService
from app.api.schemas.stock import stock_schema, stocks_schema, stock_input_schema
from app.api import apply_pagination, apply_filters
from app.utils.auth import admin_required
from app.utils.errors import ValidationError, BusinessLogicError

# Create namespace
api = Namespace('stocks', description='Stock operations')

# Define API models
stock_model = api.model('Stock', {
    'id': fields.Integer(readonly=True, description='Stock identifier'),
    'symbol': fields.String(required=True, description='Stock ticker symbol'),
    'name': fields.String(description='Company name'),
    'is_active': fields.Boolean(description='Whether the stock is active'),
    'sector': fields.String(description='Industry sector'),
    'description': fields.String(description='Stock description'),
    'created_at': fields.DateTime(description='Creation timestamp'),
    'updated_at': fields.DateTime(description='Last update timestamp')
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

# Add search results model
stock_search_model = api.model('StockSearchResults', {
    'results': fields.List(fields.Nested(stock_model), description='List of matching stocks'),
    'count': fields.Integer(description='Number of results returned')
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
        with SessionManager() as session:
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
    @api.marshal_with(stock_model)
    @api.response(HTTPStatus.CREATED, 'Stock created successfully')
    @api.response(HTTPStatus.BAD_REQUEST, 'Invalid input')
    @api.response(HTTPStatus.UNAUTHORIZED, 'Unauthorized')
    @api.response(403, 'Admin privileges required')
    @api.response(409, 'Stock with this symbol already exists')
    @jwt_required()
    @admin_required
    def post(self):
        """Create a new stock. Requires admin privileges."""
        data = request.json
        
        # Validate input data
        try:
            validated_data = stock_input_schema.load(data or {})
        except ValidationError as err:
            error_messages = getattr(err, 'messages', {})
            raise ValidationError("Invalid stock data", errors=error_messages)
        
        with SessionManager() as session:
            try:
                # Create the stock using the StockService
                stock = StockService.create_stock(
                    session=session,
                    data=cast(Dict[str, Any], validated_data)
                )
                
                return stock_schema.dump(stock), 201
                
            except ValidationError as e:
                current_app.logger.warning(f"Validation error creating stock: {str(e)}")
                raise
            except IntegrityError:
                symbol = (data or {}).get('symbol', 'unknown')
                current_app.logger.error(f"Stock with symbol {symbol} already exists")
                raise BusinessLogicError("Stock with this symbol already exists")
            except Exception as e:
                current_app.logger.error(f"Error creating stock: {str(e)}")
                raise BusinessLogicError(f"Could not create stock: {str(e)}")

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
        with SessionManager() as session:
            stock = StockService.get_or_404(session, id)
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
        data = request.json
        
        # Validate input data
        try:
            validated_data = stock_input_schema.load(data or {}, partial=True)
        except ValidationError as err:
            error_messages = getattr(err, 'messages', {})
            raise ValidationError("Invalid stock data", errors=error_messages)
        
        with SessionManager() as session:
            # Get the stock
            stock = StockService.get_or_404(session, id)
            
            try:
                # Update the stock using StockService
                result = StockService.update_stock(
                    session, 
                    stock, 
                    cast(Dict[str, Any], validated_data)
                )
                return stock_schema.dump(result)
                
            except ValidationError as e:
                current_app.logger.warning(f"Validation error updating stock: {str(e)}")
                raise
            except Exception as e:
                current_app.logger.error(f"Error updating stock: {str(e)}")
                raise BusinessLogicError(f"Could not update stock: {str(e)}")
    
    @api.doc('delete_stock')
    @api.response(204, 'Stock deleted')
    @api.response(401, 'Unauthorized')
    @api.response(403, 'Admin privileges required')
    @api.response(404, 'Stock not found')
    @api.response(409, 'Cannot delete stock with dependencies')
    @jwt_required()
    @admin_required
    def delete(self, id):
        """Delete a stock. Requires admin privileges."""
        with SessionManager() as session:
            # Get the stock
            stock = StockService.get_or_404(session, id)
            
            try:
                # Delete the stock using StockService
                StockService.delete_stock(session, stock)
                return '', 204
                
            except BusinessLogicError as e:
                current_app.logger.warning(f"Business logic error deleting stock: {str(e)}")
                raise
            except Exception as e:
                current_app.logger.error(f"Error deleting stock: {str(e)}")
                raise BusinessLogicError(f"Could not delete stock: {str(e)}")

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
        with SessionManager() as session:
            stock = StockService.find_by_symbol_or_404(session, symbol)
            return stock_schema.dump(stock)

@api.route('/search')
class StockSearch(Resource):
    """Resource for searching stocks."""
    
    @api.doc('search_stocks',
             params={
                 'q': 'Search query string (searches in symbol and name)',
                 'limit': 'Maximum number of results to return (default: 10)'
             })
    @api.marshal_with(stock_search_model)
    @api.response(200, 'Success')
    def get(self):
        """Search for stocks by symbol or name."""
        query = request.args.get('q', '')
        limit = min(int(request.args.get('limit', 10)), 50)  # Cap at 50 results
        
        with SessionManager() as session:
            stocks = StockService.search_stocks(session, query, limit)
            results = stocks_schema.dump(stocks)
            
            return {
                'results': results,
                'count': len(results)
            }

@api.route('/<int:id>/toggle-active')
@api.param('id', 'The stock identifier')
@api.response(404, 'Stock not found')
class StockToggleActive(Resource):
    """Resource for toggling a stock's active status."""
    
    @api.doc('toggle_stock_active')
    @api.marshal_with(stock_model)
    @api.response(200, 'Stock status toggled')
    @api.response(401, 'Unauthorized')
    @api.response(403, 'Admin privileges required')
    @api.response(404, 'Stock not found')
    @jwt_required()
    @admin_required
    def post(self, id):
        """Toggle the active status of a stock. Requires admin privileges."""
        with SessionManager() as session:
            # Get the stock
            stock = StockService.get_or_404(session, id)
            
            try:
                # Toggle active status using StockService
                result = StockService.toggle_active(session, stock)
                return stock_schema.dump(result)
                
            except ValidationError as e:
                current_app.logger.warning(f"Validation error toggling stock status: {str(e)}")
                raise
            except Exception as e:
                current_app.logger.error(f"Error toggling stock active status: {str(e)}")
                raise BusinessLogicError(f"Could not toggle stock status: {str(e)}") 