"""
Stock Prices API resources.
"""
from flask import request, current_app
from flask_restx import Namespace, Resource, fields, abort
from datetime import datetime, date
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.database import get_db_session
from app.models import Stock, StockDailyPrice, StockIntradayPrice, PriceSource
from app.api import apply_pagination, apply_filters
from app.api.auth import admin_required

# Create namespace
api = Namespace('prices', description='Stock price operations')

# Define API models for daily prices
daily_price_model = api.model('StockDailyPrice', {
    'id': fields.Integer(readonly=True, description='Price record identifier'),
    'stock_id': fields.Integer(description='Stock identifier'),
    'price_date': fields.Date(description='Trading date'),
    'open_price': fields.Float(description='Opening price'),
    'high_price': fields.Float(description='Highest price'),
    'low_price': fields.Float(description='Lowest price'),
    'close_price': fields.Float(description='Closing price'),
    'adj_close': fields.Float(description='Adjusted closing price'),
    'volume': fields.Integer(description='Trading volume'),
    'source': fields.String(description='Price data source'),
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
    'timestamp': fields.DateTime(description='Trading timestamp'),
    'interval': fields.Integer(description='Time interval in minutes'),
    'open_price': fields.Float(description='Opening price'),
    'high_price': fields.Float(description='Highest price'),
    'low_price': fields.Float(description='Lowest price'),
    'close_price': fields.Float(description='Closing price'),
    'volume': fields.Integer(description='Trading volume'),
    'source': fields.String(description='Price data source'),
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
class StockDailyPriceList(Resource):
    """Resource for managing daily prices for a specific stock."""
    
    @api.doc('list_daily_prices',
             params={
                 'page': 'Page number (default: 1)',
                 'page_size': 'Number of items per page (default: 20, max: 100)',
                 'start_date': 'Filter prices on or after this date (YYYY-MM-DD)',
                 'end_date': 'Filter prices on or before this date (YYYY-MM-DD)',
                 'sort': 'Sort field (e.g., price_date, close_price)',
                 'order': 'Sort order (asc or desc, default: asc)'
             })
    @api.marshal_with(daily_price_list_model)
    @api.response(200, 'Success')
    @api.response(400, 'Invalid query parameters')
    @api.response(404, 'Stock not found')
    def get(self, stock_id):
        """Get daily prices for a stock with filtering and pagination."""
        with get_db_session() as session:
            # Check if the stock exists
            stock = session.query(Stock).filter_by(id=stock_id).first()
            if stock is None:
                abort(404, 'Stock not found')
            
            # Start with base query
            query = session.query(StockDailyPrice).filter_by(stock_id=stock_id)
            
            # Handle special date filtering
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            if start_date:
                try:
                    start = datetime.strptime(start_date, '%Y-%m-%d').date()
                    query = query.filter(StockDailyPrice.price_date >= start)
                except ValueError:
                    abort(400, 'Invalid start_date format. Use YYYY-MM-DD')
            
            if end_date:
                try:
                    end = datetime.strptime(end_date, '%Y-%m-%d').date()
                    query = query.filter(StockDailyPrice.price_date <= end)
                except ValueError:
                    abort(400, 'Invalid end_date format. Use YYYY-MM-DD')
            
            # Apply additional filters
            query = apply_filters(query, StockDailyPrice)
            
            # Apply default sort if not specified
            sort_field = request.args.get('sort', 'price_date')
            sort_order = request.args.get('order', 'asc')
            
            if sort_field == 'price_date':
                sort_col = StockDailyPrice.price_date
                if sort_order.lower() == 'desc':
                    sort_col = sort_col.desc()
                query = query.order_by(sort_col)
            
            # Apply pagination
            result = apply_pagination(query)
            
            # Serialize the results
            result['items'] = result['items']  # Already ORM objects
            
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
                
                # Create the new price record
                price_record = StockDailyPrice(
                    stock_id=stock_id,
                    price_date=price_date,
                    open_price=data.get('open_price'),
                    high_price=data.get('high_price'),
                    low_price=data.get('low_price'),
                    close_price=data.get('close_price'),
                    adj_close=data.get('adj_close'),
                    volume=data.get('volume'),
                    source=data.get('source', PriceSource.HISTORICAL)
                )
                
                session.add(price_record)
                session.commit()
                session.refresh(price_record)
                
                # Prepare price data for event emission
                price_data = {
                    'id': price_record.id,
                    'stock_id': price_record.stock_id,
                    'price_date': price_record.price_date.isoformat(),
                    'open_price': float(price_record.open_price),
                    'high_price': float(price_record.high_price),
                    'low_price': float(price_record.low_price),
                    'close_price': float(price_record.close_price),
                    'adj_close': float(price_record.adj_close),
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
                
                return price_record, 201
        except Exception as e:
            abort(400, str(e))

@api.route('/intraday/stocks/<int:stock_id>')
@api.param('stock_id', 'The stock identifier')
@api.response(404, 'Stock not found')
class StockIntradayPriceList(Resource):
    """Resource for managing intraday prices for a specific stock."""
    
    @api.doc('list_intraday_prices',
             params={
                 'page': 'Page number (default: 1)',
                 'page_size': 'Number of items per page (default: 20, max: 100)',
                 'start_time': 'Filter prices on or after this time (ISO format)',
                 'end_time': 'Filter prices on or before this time (ISO format)',
                 'interval': 'Filter by time interval in minutes',
                 'sort': 'Sort field (e.g., timestamp, close_price)',
                 'order': 'Sort order (asc or desc, default: asc)'
             })
    @api.marshal_with(intraday_price_list_model)
    @api.response(200, 'Success')
    @api.response(400, 'Invalid query parameters')
    @api.response(404, 'Stock not found')
    def get(self, stock_id):
        """Get intraday prices for a stock with filtering and pagination."""
        with get_db_session() as session:
            # Check if the stock exists
            stock = session.query(Stock).filter_by(id=stock_id).first()
            if stock is None:
                abort(404, 'Stock not found')
            
            # Start with base query
            query = session.query(StockIntradayPrice).filter_by(stock_id=stock_id)
            
            # Handle special time filtering
            start_time = request.args.get('start_time')
            end_time = request.args.get('end_time')
            interval = request.args.get('interval')
            
            if start_time:
                try:
                    start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    query = query.filter(StockIntradayPrice.timestamp >= start)
                except ValueError:
                    abort(400, 'Invalid start_time format. Use ISO format')
            
            if end_time:
                try:
                    end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                    query = query.filter(StockIntradayPrice.timestamp <= end)
                except ValueError:
                    abort(400, 'Invalid end_time format. Use ISO format')
            
            if interval:
                try:
                    interval_value = int(interval)
                    query = query.filter(StockIntradayPrice.interval == interval_value)
                except ValueError:
                    abort(400, 'Invalid interval format. Use an integer value')
            
            # Apply additional filters
            query = apply_filters(query, StockIntradayPrice)
            
            # Apply default sort if not specified
            sort_field = request.args.get('sort', 'timestamp')
            sort_order = request.args.get('order', 'asc')
            
            if sort_field == 'timestamp':
                sort_col = StockIntradayPrice.timestamp
                if sort_order.lower() == 'desc':
                    sort_col = sort_col.desc()
                query = query.order_by(sort_col)
            
            # Apply pagination
            result = apply_pagination(query)
            
            # Serialize the results
            result['items'] = result['items']  # Already ORM objects
            
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
                
                return price_record, 201
        except Exception as e:
            abort(400, str(e)) 