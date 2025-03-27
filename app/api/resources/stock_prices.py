"""
Stock Prices API resources.
"""
from flask import request, current_app
from flask_restx import Namespace, Resource, fields, abort
from datetime import datetime
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.database import get_db_session
from app.models import Stock, StockDailyPrice, StockIntradayPrice, PriceSource
from app.api import apply_pagination, apply_filters
from app.api.auth import admin_required
from app.utils.errors import ResourceNotFoundError
from app.api.schemas.stock_price import (
    daily_price_schema,
    daily_prices_schema,
    daily_price_input_schema,
    intraday_price_schema,
    intraday_prices_schema,
    intraday_price_input_schema
)

# Create namespace
api = Namespace('prices', description='Stock price operations')

# Define API models for daily prices
daily_price_model = api.model('StockDailyPrice', {
    'id': fields.Integer(readonly=True, description='Price record identifier'),
    'stock_id': fields.Integer(description='Stock identifier'),
    'stock_symbol': fields.String(description='Stock symbol'),
    'price_date': fields.Date(description='Price date'),
    'open': fields.Float(description='Opening price'),
    'high': fields.Float(description='High price'),
    'low': fields.Float(description='Low price'),
    'close': fields.Float(description='Closing price'),
    'volume': fields.Integer(description='Trading volume'),
    'adjusted_close': fields.Float(description='Adjusted closing price'),
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
    'stock_symbol': fields.String(description='Stock symbol'),
    'timestamp': fields.DateTime(description='Price timestamp'),
    'interval': fields.Integer(description='Time interval in minutes'),
    'open': fields.Float(description='Opening price'),
    'high': fields.Float(description='High price'),
    'low': fields.Float(description='Low price'),
    'close': fields.Float(description='Closing price'),
    'volume': fields.Integer(description='Trading volume'),
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
    'pagination': fields.Nested(pagination_model, description='Pagination information')
})

intraday_price_list_model = api.model('IntradayPriceList', {
    'items': fields.List(fields.Nested(intraday_price_model), description='List of intraday prices'),
    'pagination': fields.Nested(pagination_model, description='Pagination information')
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
            stock = session.query(Stock).filter_by(id=stock_id).first()
            if not stock:
                raise ResourceNotFoundError('Stock', stock_id)
            
            # Get base query for this stock's daily prices
            query = session.query(StockDailyPrice).filter_by(stock_id=stock_id)
            
            # Apply date filters if provided
            if 'start_date' in request.args:
                try:
                    start_date = datetime.strptime(request.args['start_date'], '%Y-%m-%d').date()
                    query = query.filter(StockDailyPrice.price_date >= start_date)
                except ValueError:
                    abort(400, 'Invalid start_date format. Use YYYY-MM-DD')
                    
            if 'end_date' in request.args:
                try:
                    end_date = datetime.strptime(request.args['end_date'], '%Y-%m-%d').date()
                    query = query.filter(StockDailyPrice.price_date <= end_date)
                except ValueError:
                    abort(400, 'Invalid end_date format. Use YYYY-MM-DD')
            
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
        try:
            data = request.json
            
            with get_db_session() as session:
                # Check if the stock exists
                stock = session.query(Stock).filter_by(id=stock_id).first()
                if stock is None:
                    abort(404, 'Stock not found')
                
                # Parse the price date
                try:
                    if isinstance(data['price_date'], str):
                        price_date = datetime.strptime(data['price_date'], '%Y-%m-%d').date()
                    else:
                        price_date = data['price_date']
                except ValueError:
                    abort(400, 'Invalid price_date format. Use YYYY-MM-DD')
                
                # Check if a record already exists for this date
                existing = session.query(StockDailyPrice).filter_by(
                    stock_id=stock_id, 
                    price_date=price_date
                ).first()
                
                if existing:
                    abort(409, f'Price record for date {price_date} already exists')
                
                # Validate and deserialize input
                data['stock_id'] = stock_id
                price_record = daily_price_input_schema.load(data)
                
                session.add(price_record)
                session.commit()
                session.refresh(price_record)
                
                return daily_price_schema.dump(price_record), 201
                
        except ValueError as e:
            abort(400, str(e))
        except Exception as e:
            current_app.logger.error(f"Error creating price record: {str(e)}")
            abort(400, str(e))

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
            stock = session.query(Stock).filter_by(id=stock_id).first()
            if not stock:
                raise ResourceNotFoundError('Stock', stock_id)
            
            # Get base query for this stock's intraday prices
            query = session.query(StockIntradayPrice).filter_by(stock_id=stock_id)
            
            # Apply timestamp filters if provided
            if 'start_time' in request.args:
                try:
                    start_time = datetime.strptime(request.args['start_time'], '%Y-%m-%d %H:%M:%S')
                    query = query.filter(StockIntradayPrice.timestamp >= start_time)
                except ValueError:
                    abort(400, 'Invalid start_time format. Use YYYY-MM-DD HH:MM:SS')
                    
            if 'end_time' in request.args:
                try:
                    end_time = datetime.strptime(request.args['end_time'], '%Y-%m-%d %H:%M:%S')
                    query = query.filter(StockIntradayPrice.timestamp <= end_time)
                except ValueError:
                    abort(400, 'Invalid end_time format. Use YYYY-MM-DD HH:MM:SS')
            
            # Apply interval filter if provided
            if 'interval' in request.args:
                try:
                    interval = int(request.args['interval'])
                    if interval not in [1, 5, 15, 30, 60]:
                        abort(400, 'Invalid interval. Use 1, 5, 15, 30, or 60')
                    query = query.filter(StockIntradayPrice.interval == interval)
                except ValueError:
                    abort(400, 'Invalid interval. Must be an integer')
            
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
        try:
            data = request.json
            
            with get_db_session() as session:
                # Check if the stock exists
                stock = session.query(Stock).filter_by(id=stock_id).first()
                if stock is None:
                    abort(404, 'Stock not found')
                
                # Parse the timestamp
                try:
                    if isinstance(data['timestamp'], str):
                        timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
                    else:
                        timestamp = data['timestamp']
                except ValueError:
                    abort(400, 'Invalid timestamp format. Use ISO format')
                
                # Get the interval
                interval = data.get('interval', 1)
                
                # Check if a record already exists for this timestamp and interval
                existing = session.query(StockIntradayPrice).filter_by(
                    stock_id=stock_id, 
                    timestamp=timestamp,
                    interval=interval
                ).first()
                
                if existing:
                    abort(409, f'Price record for timestamp {timestamp} and interval {interval} already exists')
                
                # Create the new price record
                price_record = StockIntradayPrice(
                    stock_id=stock_id,
                    timestamp=timestamp,
                    interval=interval,
                    open_price=data.get('open_price'),
                    high_price=data.get('high_price'),
                    low_price=data.get('low_price'),
                    close_price=data.get('close_price'),
                    volume=data.get('volume'),
                    source=data.get('source', PriceSource.DELAYED)
                )
                
                session.add(price_record)
                session.commit()
                session.refresh(price_record)
                
                # Prepare price data for event emission
                price_data = {
                    'id': price_record.id,
                    'stock_id': price_record.stock_id,
                    'timestamp': price_record.timestamp.isoformat(),
                    'interval': price_record.interval,
                    'open_price': float(price_record.open_price),
                    'high_price': float(price_record.high_price),
                    'low_price': float(price_record.low_price),
                    'close_price': float(price_record.close_price),
                    'volume': price_record.volume,
                    'source': price_record.source,
                    'created_at': price_record.created_at.isoformat(),
                    'updated_at': price_record.updated_at.isoformat()
                }
                
                # Use EventService to emit WebSocket events
                from app.services.events import EventService
                EventService.emit_price_update(
                    action='created',
                    price_data=price_data,
                    stock_symbol=stock.symbol
                )
                
                return intraday_price_schema.dump(price_record), 201
        except Exception as e:
            abort(400, str(e)) 