#!/usr/bin/env python3
"""
Stock market data module for day-trader-v1 application.
"""
import logging
from datetime import datetime

from flask import Blueprint, render_template, request, jsonify

from app.config.constants import SUPPORTED_SYMBOLS
from app.exceptions.exceptions import InvalidSymbolError, DataFetchError
from app.services.stock_market_data_api import (
    get_intraday_data,
    save_intraday_data,
    get_daily_data,
    save_daily_data
)
from app.services.database import get_session
from app.models.stock_model import Stock
from app.models.daily_price_model import DailyPrice
from app.models.intraday_price_model import IntradayPrice

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
data_bp = Blueprint('data', __name__, url_prefix='/market-data')

@data_bp.route('/')
def index():
    """Render the market data page."""
    return render_template(
        'stock_data.html',
        supported_stocks=SUPPORTED_SYMBOLS,
        now=datetime.now()
    )

@data_bp.route('/api/<symbol>', methods=['GET'])
def fetch_market_data(symbol: str):
    """API endpoint to fetch market data."""
    try:
        # Get query parameters
        data_type = request.args.get('data_type', 'intraday')
        interval = request.args.get('interval', '1m')
        period = request.args.get('period', '1d')
        save_to_db = request.args.get('save', 'false').lower() == 'true'
        
        # Validate symbol
        symbol = symbol.upper()
        if symbol not in SUPPORTED_SYMBOLS:
            return jsonify({'error': f'Invalid stock symbol: {symbol}'}), 400
        
        # Fetch data based on type
        if data_type == 'intraday':
            if save_to_db:
                stock_id, count = save_intraday_data(symbol, interval, period)
                return jsonify({
                    'message': f'Successfully saved {count} intraday records for {symbol}',
                    'count': count,
                    'stock_id': stock_id,
                    'data': get_intraday_data(symbol, interval, period)
                })
            else:
                data = get_intraday_data(symbol, interval, period)
                return jsonify({
                    'message': f'Successfully fetched {len(data)} intraday records for {symbol}',
                    'data': data
                })
        elif data_type == 'daily':
            if save_to_db:
                stock_id, count = save_daily_data(symbol, period)
                return jsonify({
                    'message': f'Successfully saved {count} daily records for {symbol}',
                    'count': count,
                    'stock_id': stock_id,
                    'data': get_daily_data(symbol, period)
                })
            else:
                data = get_daily_data(symbol, period)
                return jsonify({
                    'message': f'Successfully fetched {len(data)} daily records for {symbol}',
                    'data': data
                })
        else:
            return jsonify({'error': 'Invalid data type. Must be "intraday" or "daily".'}), 400
            
    except InvalidSymbolError as e:
        logger.error(f"Invalid symbol error: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except DataFetchError as e:
        logger.error(f"Data fetch error: {str(e)}")
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500

@data_bp.route('/database-records/<data_type>', methods=['GET'])
def get_database_records(data_type: str):
    """API endpoint to get recent database records."""
    session = get_session()
    try:
        if data_type == 'intraday':
            # Get recent intraday records with stock info joined
            records = session.query(
                IntradayPrice.id,
                IntradayPrice.stock_id,
                IntradayPrice.timestamp,
                IntradayPrice.open,
                IntradayPrice.high,
                IntradayPrice.low,
                IntradayPrice.close,
                IntradayPrice.volume,
                Stock.symbol.label('stock_symbol'),
                Stock.name.label('stock_name')
            ).join(Stock).order_by(IntradayPrice.id.desc()).limit(10).all()
            
            return jsonify([{
                'id': r.id,
                'stock_id': r.stock_id,
                'stock_symbol': r.stock_symbol,
                'stock_name': r.stock_name,
                'timestamp': r.timestamp.isoformat(),
                'open': float(r.open) if r.open is not None else None,
                'high': float(r.high) if r.high is not None else None,
                'low': float(r.low) if r.low is not None else None,
                'close': float(r.close) if r.close is not None else None,
                'volume': r.volume
            } for r in records])
            
        elif data_type == 'daily':
            # Get recent daily records with stock info joined
            records = session.query(
                DailyPrice.id,
                DailyPrice.stock_id,
                DailyPrice.date,
                DailyPrice.open,
                DailyPrice.high,
                DailyPrice.low,
                DailyPrice.close,
                DailyPrice.adj_close,
                DailyPrice.volume,
                Stock.symbol.label('stock_symbol'),
                Stock.name.label('stock_name')
            ).join(Stock).order_by(DailyPrice.id.desc()).limit(10).all()
            
            return jsonify([{
                'id': r.id,
                'stock_id': r.stock_id,
                'stock_symbol': r.stock_symbol,
                'stock_name': r.stock_name,
                'date': r.date.isoformat(),
                'open': float(r.open) if r.open is not None else None,
                'high': float(r.high) if r.high is not None else None,
                'low': float(r.low) if r.low is not None else None,
                'close': float(r.close) if r.close is not None else None,
                'adj_close': float(r.adj_close) if r.adj_close is not None else None,
                'volume': r.volume
            } for r in records])
            
        else:
            return jsonify({'error': 'Invalid data type. Must be "intraday" or "daily".'}), 400
            
    except Exception as e:
        logger.error(f"Error fetching database records: {str(e)}")
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500
    finally:
        session.close()
