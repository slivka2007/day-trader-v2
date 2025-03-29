"""
Stock Prices API resources.
"""
from flask import request, current_app
from flask_restx import Namespace, Resource, fields
from datetime import datetime
from flask_jwt_extended import jwt_required

from app.services.database import get_db_session
from app.models import StockDailyPrice, StockIntradayPrice
from app.services.price_service import PriceService
from app.services.stock_service import StockService
from app.api import apply_pagination, apply_filters
from app.utils.auth import admin_required
from app.utils.errors import ValidationError, ResourceNotFoundError, BusinessLogicError
from app.api.schemas.stock_price import (
    daily_price_schema,
    daily_prices_schema,
    daily_price_input_schema,
    intraday_price_schema,
    intraday_prices_schema,
    intraday_price_input_schema,
)

# Create namespace
api = Namespace('prices', description='Stock price operations')

# Define API models for daily prices
daily_price_model = api.model('StockDailyPrice', {
    'id': fields.Integer(readonly=True, description='Price record identifier'),
    'stock_id': fields.Integer(description='Stock identifier'),
    'price_date': fields.Date(description='Price date'),
    'open_price': fields.Float(description='Opening price'),
    'high_price': fields.Float(description='High price'),
    'low_price': fields.Float(description='Low price'),
    'close_price': fields.Float(description='Closing price'),
    'adj_close': fields.Float(description='Adjusted closing price'),
    'volume': fields.Integer(description='Trading volume'),
    'source': fields.String(description='Price data source'),
    'change': fields.Float(description='Price change (close - open)'),
    'change_percent': fields.Float(description='Percentage price change'),
    'stock_symbol': fields.String(description='Stock symbol'),
    'created_at': fields.DateTime(description='Creation timestamp'),
    'updated_at': fields.DateTime(description='Last update timestamp')
})

daily_price_input_model = api.model('StockDailyPriceInput', {
    'price_date': fields.Date(required=True, description='Trading date'),
    'open_price': fields.Float(description='Opening price'),
    'high_price': fields.Float(description='Highest price'),
    'low_price': fields.Float(description='Lowest price'),
    'close_price': fields.Float(description='Closing price'),
    'adj_close': fields.Float(description='Adjusted closing price'),
    'volume': fields.Integer(description='Trading volume'),
    'source': fields.String(description='Price data source')
})

# Define API models for intraday prices
intraday_price_model = api.model('StockIntradayPrice', {
    'id': fields.Integer(readonly=True, description='Price record identifier'),
    'stock_id': fields.Integer(description='Stock identifier'),
    'timestamp': fields.DateTime(description='Price timestamp'),
    'interval': fields.Integer(description='Time interval in minutes'),
    'open_price': fields.Float(description='Opening price'),
    'high_price': fields.Float(description='High price'),
    'low_price': fields.Float(description='Low price'),
    'close_price': fields.Float(description='Closing price'),
    'volume': fields.Integer(description='Trading volume'),
    'source': fields.String(description='Price data source'),
    'change': fields.Float(description='Price change (close - open)'),
    'change_percent': fields.Float(description='Percentage price change'),
    'stock_symbol': fields.String(description='Stock symbol'),
    'created_at': fields.DateTime(description='Creation timestamp'),
    'updated_at': fields.DateTime(description='Last update timestamp')
})

intraday_price_input_model = api.model('StockIntradayPriceInput', {
    'timestamp': fields.DateTime(required=True, description='Trading timestamp'),
    'interval': fields.Integer(description='Time interval in minutes'),
    'open_price': fields.Float(description='Opening price'),
    'high_price': fields.Float(description='Highest price'),
    'low_price': fields.Float(description='Lowest price'),
    'close_price': fields.Float(description='Closing price'),
    'volume': fields.Integer(description='Trading volume'),
    'source': fields.String(description='Price data source')
})

# Add pagination models
pagination_model = api.model('Pagination', {
    'page': fields.Integer(description='Current page number'),
    'page_size': fields.Integer(description='Number of items per page'),
    'total_items': fields.Integer(description='Total number of items'),
    'total_pages': fields.Integer(description='Total number of pages'),
    'has_next': fields.Boolean(description='Whether there is a next page'),
    'has_prev': fields.Boolean(description='Whether there is a previous page')
})

daily_price_list_model = api.model('DailyPriceList', {
    'items': fields.List(fields.Nested(daily_price_model), description='List of daily prices'),
    'pagination': fields.Nested(pagination_model, description='Pagination information'),
    'stock_symbol': fields.String(description='Stock symbol'),
    'stock_id': fields.Integer(description='Stock ID')
})

intraday_price_list_model = api.model('IntradayPriceList', {
    'items': fields.List(fields.Nested(intraday_price_model), description='List of intraday prices'),
    'pagination': fields.Nested(pagination_model, description='Pagination information'),
    'stock_symbol': fields.String(description='Stock symbol'),
    'stock_id': fields.Integer(description='Stock ID')
})

@api.route('/daily/stocks/<int:stock_id>')
@api.param('stock_id', 'The stock identifier')
@api.response(404, 'Stock not found')
class StockDailyPrices(Resource):
    """Resource for daily price data for a specific stock."""
    
    @api.doc('get_daily_prices',
             params={
                 'page': 'Page number (default: 1)',
                 'page_size': 'Number of items per page (default: 20, max: 100)',
                 'start_date': 'Filter by start date (format: YYYY-MM-DD)',
                 'end_date': 'Filter by end date (format: YYYY-MM-DD)',
                 'sort': 'Sort field (e.g., price_date)',
                 'order': 'Sort order (asc or desc, default: desc for dates)'
             })
    @api.marshal_with(daily_price_list_model)
    @api.response(200, 'Success')
    @api.response(404, 'Stock not found')
    def get(self, stock_id):
        """Get daily price data for a specific stock with filtering and pagination."""
        with get_db_session() as session:
            # Verify stock exists
            stock = StockService.get_or_404(session, stock_id)
            
            # Get base query for this stock's daily prices
            query = session.query(StockDailyPrice).filter_by(stock_id=stock_id)
            
            # Apply date filters if provided
            if 'start_date' in request.args:
                try:
                    start_date = datetime.strptime(request.args['start_date'], '%Y-%m-%d').date()
                    query = query.filter(StockDailyPrice.price_date >= start_date)
                except ValueError:
                    raise ValidationError("Invalid start_date format. Use YYYY-MM-DD")
                    
            if 'end_date' in request.args:
                try:
                    end_date = datetime.strptime(request.args['end_date'], '%Y-%m-%d').date()
                    query = query.filter(StockDailyPrice.price_date <= end_date)
                except ValueError:
                    raise ValidationError("Invalid end_date format. Use YYYY-MM-DD")
            
            # Apply other filters
            query = apply_filters(query, StockDailyPrice)
            
            # Default sort by date descending if not specified
            if 'sort' not in request.args:
                query = query.order_by(StockDailyPrice.price_date.desc())
            
            # Apply pagination
            result = apply_pagination(query)
            
            # Add stock information to response
            result['stock_symbol'] = stock.symbol
            result['stock_id'] = stock_id
            
            # Serialize the results
            result['items'] = daily_prices_schema.dump(result['items'])
            
            return result
    
    @api.doc('create_daily_price')
    @api.expect(daily_price_input_model)
    @api.marshal_with(daily_price_model, code=201)
    @api.response(201, 'Price record created')
    @api.response(400, 'Invalid input')
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Stock not found')
    @api.response(409, 'Price record already exists for this date')
    @jwt_required()
    @admin_required
    def post(self, stock_id):
        """Add a new daily price record for a stock. Requires admin privileges."""
        data = request.json
        
        try:
            # Validate and load input data
            validated_data = daily_price_input_schema.load(data)
            
            with get_db_session() as session:
                # Parse the price date
                if isinstance(validated_data.price_date, str):
                    try:
                        price_date = datetime.strptime(validated_data.price_date, '%Y-%m-%d').date()
                    except ValueError:
                        raise ValidationError("Invalid price_date format. Use YYYY-MM-DD")
                else:
                    price_date = validated_data.price_date
                
                # Create the price record using the service
                price_record = PriceService.create_daily_price(
                    session=session,
                    stock_id=stock_id,
                    price_date=price_date,
                    data=data
                )
                
                return daily_price_schema.dump(price_record), 201
                
        except ValidationError as e:
            current_app.logger.error(f"Validation error creating price record: {str(e)}")
            raise
        except ResourceNotFoundError:
            raise
        except BusinessLogicError as e:
            current_app.logger.error(f"Business logic error: {str(e)}")
            raise
        except Exception as e:
            current_app.logger.error(f"Error creating price record: {str(e)}")
            raise ValidationError(str(e))

@api.route('/intraday/stocks/<int:stock_id>')
@api.param('stock_id', 'The stock identifier')
@api.response(404, 'Stock not found')
class StockIntradayPrices(Resource):
    """Resource for intraday price data for a specific stock."""
    
    @api.doc('get_intraday_prices',
             params={
                 'page': 'Page number (default: 1)',
                 'page_size': 'Number of items per page (default: 20, max: 100)',
                 'start_time': 'Filter by start timestamp (format: YYYY-MM-DD HH:MM:SS)',
                 'end_time': 'Filter by end timestamp (format: YYYY-MM-DD HH:MM:SS)',
                 'interval': 'Filter by interval in minutes (1, 5, 15, 30, 60)',
                 'sort': 'Sort field (e.g., timestamp)',
                 'order': 'Sort order (asc or desc, default: desc for timestamps)'
             })
    @api.marshal_with(intraday_price_list_model)
    @api.response(200, 'Success')
    @api.response(404, 'Stock not found')
    def get(self, stock_id):
        """Get intraday price data for a specific stock with filtering and pagination."""
        with get_db_session() as session:
            # Verify stock exists
            stock = StockService.get_or_404(session, stock_id)
            
            # Get base query for this stock's intraday prices
            query = session.query(StockIntradayPrice).filter_by(stock_id=stock_id)
            
            # Apply timestamp filters if provided
            if 'start_time' in request.args:
                try:
                    start_time = datetime.strptime(request.args['start_time'], '%Y-%m-%d %H:%M:%S')
                    query = query.filter(StockIntradayPrice.timestamp >= start_time)
                except ValueError:
                    raise ValidationError("Invalid start_time format. Use YYYY-MM-DD HH:MM:SS")
                    
            if 'end_time' in request.args:
                try:
                    end_time = datetime.strptime(request.args['end_time'], '%Y-%m-%d %H:%M:%S')
                    query = query.filter(StockIntradayPrice.timestamp <= end_time)
                except ValueError:
                    raise ValidationError("Invalid end_time format. Use YYYY-MM-DD HH:MM:SS")
            
            # Apply interval filter if provided
            if 'interval' in request.args:
                try:
                    interval = int(request.args['interval'])
                    if interval not in [1, 5, 15, 30, 60]:
                        raise ValidationError("Invalid interval. Use 1, 5, 15, 30, or 60")
                    query = query.filter(StockIntradayPrice.interval == interval)
                except ValueError:
                    raise ValidationError("Invalid interval. Must be an integer")
            
            # Apply other filters
            query = apply_filters(query, StockIntradayPrice)
            
            # Default sort by timestamp descending if not specified
            if 'sort' not in request.args:
                query = query.order_by(StockIntradayPrice.timestamp.desc())
            
            # Apply pagination
            result = apply_pagination(query)
            
            # Add stock information to response
            result['stock_symbol'] = stock.symbol
            result['stock_id'] = stock_id
            
            # Serialize the results
            result['items'] = intraday_prices_schema.dump(result['items'])
            
            return result
    
    @api.doc('create_intraday_price')
    @api.expect(intraday_price_input_model)
    @api.marshal_with(intraday_price_model, code=201)
    @api.response(201, 'Price record created')
    @api.response(400, 'Invalid input')
    @api.response(401, 'Unauthorized')
    @api.response(403, 'Admin privileges required')
    @api.response(404, 'Stock not found')
    @api.response(409, 'Price record already exists for this timestamp and interval')
    @jwt_required()
    @admin_required
    def post(self, stock_id):
        """Add a new intraday price record for a stock. Requires admin privileges."""
        data = request.json
        
        try:
            # Validate and load input data
            validated_data = intraday_price_input_schema.load(data)
            
            with get_db_session() as session:
                # Parse the timestamp
                if isinstance(validated_data.timestamp, str):
                    try:
                        timestamp = datetime.fromisoformat(validated_data.timestamp.replace('Z', '+00:00'))
                    except ValueError:
                        raise ValidationError("Invalid timestamp format. Use ISO format")
                else:
                    timestamp = validated_data.timestamp
                
                # Get the interval
                interval = validated_data.interval
                
                # Create the intraday price record using the service
                price_record = PriceService.create_intraday_price(
                    session=session,
                    stock_id=stock_id,
                    timestamp=timestamp,
                    interval=interval,
                    data=data
                )
                
                return intraday_price_schema.dump(price_record), 201
                
        except ValidationError as e:
            current_app.logger.error(f"Validation error creating price record: {str(e)}")
            raise
        except ResourceNotFoundError:
            raise
        except BusinessLogicError as e:
            current_app.logger.error(f"Business logic error: {str(e)}")
            raise
        except Exception as e:
            current_app.logger.error(f"Error creating price record: {str(e)}")
            raise ValidationError(str(e))

@api.route('/daily/<int:price_id>')
@api.param('price_id', 'The daily price record identifier')
@api.response(404, 'Price record not found')
class DailyPriceItem(Resource):
    """Resource for managing individual daily price records."""
    
    @api.doc('get_daily_price')
    @api.marshal_with(daily_price_model)
    @api.response(200, 'Success')
    @api.response(404, 'Price record not found')
    def get(self, price_id):
        """Get a daily price record by ID."""
        with get_db_session() as session:
            price = PriceService.get_daily_price_or_404(session, price_id)
            return daily_price_schema.dump(price)
    
    @api.doc('update_daily_price')
    @api.expect(daily_price_input_model)
    @api.marshal_with(daily_price_model)
    @api.response(200, 'Price record updated')
    @api.response(400, 'Invalid input')
    @api.response(401, 'Unauthorized')
    @api.response(403, 'Admin privileges required')
    @api.response(404, 'Price record not found')
    @jwt_required()
    @admin_required
    def put(self, price_id):
        """Update a daily price record. Requires admin privileges."""
        data = request.json
        
        # Don't allow changing date or stock
        if 'price_date' in data:
            del data['price_date']
        if 'stock_id' in data:
            del data['stock_id']
        
        try:
            with get_db_session() as session:
                # Update the price record using the service
                result = PriceService.update_daily_price(session, price_id, data)
                return daily_price_schema.dump(result)
                
        except ValidationError as e:
            current_app.logger.error(f"Validation error updating price record: {str(e)}")
            raise
        except BusinessLogicError as e:
            current_app.logger.error(f"Business logic error: {str(e)}")
            raise
        except Exception as e:
            current_app.logger.error(f"Error updating price record: {str(e)}")
            raise ValidationError(str(e))
    
    @api.doc('delete_daily_price')
    @api.response(204, 'Price record deleted')
    @api.response(401, 'Unauthorized')
    @api.response(403, 'Admin privileges required')
    @api.response(404, 'Price record not found')
    @jwt_required()
    @admin_required
    def delete(self, price_id):
        """Delete a daily price record. Requires admin privileges."""
        try:
            with get_db_session() as session:
                # Delete the price record using the service
                PriceService.delete_daily_price(session, price_id)
                return '', 204
                
        except ValidationError as e:
            raise BusinessLogicError(str(e))
        except BusinessLogicError:
            raise
        except Exception as e:
            current_app.logger.error(f"Error deleting price record: {str(e)}")
            raise BusinessLogicError(str(e))

@api.route('/intraday/<int:price_id>')
@api.param('price_id', 'The intraday price record identifier')
@api.response(404, 'Price record not found')
class IntradayPriceItem(Resource):
    """Resource for managing individual intraday price records."""
    
    @api.doc('get_intraday_price')
    @api.marshal_with(intraday_price_model)
    @api.response(200, 'Success')
    @api.response(404, 'Price record not found')
    def get(self, price_id):
        """Get an intraday price record by ID."""
        with get_db_session() as session:
            price = PriceService.get_intraday_price_or_404(session, price_id)
            return intraday_price_schema.dump(price)
    
    @api.doc('update_intraday_price')
    @api.expect(intraday_price_input_model)
    @api.marshal_with(intraday_price_model)
    @api.response(200, 'Price record updated')
    @api.response(400, 'Invalid input')
    @api.response(401, 'Unauthorized')
    @api.response(403, 'Admin privileges required')
    @api.response(404, 'Price record not found')
    @jwt_required()
    @admin_required
    def put(self, price_id):
        """Update an intraday price record. Requires admin privileges."""
        data = request.json
        
        # Don't allow changing timestamp, interval, or stock
        if 'timestamp' in data:
            del data['timestamp']
        if 'interval' in data:
            del data['interval']
        if 'stock_id' in data:
            del data['stock_id']
        
        try:
            with get_db_session() as session:
                # Update the price record using the service
                result = PriceService.update_intraday_price(session, price_id, data)
                return intraday_price_schema.dump(result)
                
        except ValidationError as e:
            current_app.logger.error(f"Validation error updating price record: {str(e)}")
            raise
        except BusinessLogicError as e:
            current_app.logger.error(f"Business logic error: {str(e)}")
            raise
        except Exception as e:
            current_app.logger.error(f"Error updating price record: {str(e)}")
            raise ValidationError(str(e))
    
    @api.doc('delete_intraday_price')
    @api.response(204, 'Price record deleted')
    @api.response(401, 'Unauthorized')
    @api.response(403, 'Admin privileges required')
    @api.response(404, 'Price record not found')
    @jwt_required()
    @admin_required
    def delete(self, price_id):
        """Delete an intraday price record. Requires admin privileges."""
        try:
            with get_db_session() as session:
                # Delete the price record using the service
                PriceService.delete_intraday_price(session, price_id)
                return '', 204
                
        except ValidationError as e:
            raise BusinessLogicError(str(e))
        except BusinessLogicError:
            raise
        except Exception as e:
            current_app.logger.error(f"Error deleting price record: {str(e)}")
            raise BusinessLogicError(str(e)) 