#!/usr/bin/env python3
"""
Stock trading service module for day-trader-v1 application.
"""
import logging
from datetime import datetime
from decimal import Decimal
import threading
from typing import Optional, Dict, Any, List, Union
from sqlalchemy import desc
from flask import Blueprint, render_template, request, jsonify, redirect, url_for

from database.scripts.database import get_session
from database.models.stock_service_model import StockService, STATE_ACTIVE, STATE_INACTIVE, MODE_BUY, MODE_SELL
from database.models.stock_transaction_model import StockTransaction
from app.services.stock_service import StockTradingService
from app.apis.stock_purchase_api import MOCK_PRICES

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
stock_bp = Blueprint('stock', __name__, url_prefix='/stock')

# Available test stocks
TEST_STOCKS = list(MOCK_PRICES.keys())

@stock_bp.route('/')
def index():
    """Stock trading service dashboard page."""
    # Get all services
    session = get_session()
    services = session.query(StockService).all()
    
    # Get 10 most recent transactions
    recent_transactions = (
        session.query(StockTransaction)
        .order_by(desc(StockTransaction.transaction_id))
        .limit(10)
        .all()
    )
    
    session.close()
    
    return render_template('stock_trading.html', 
                          services=services,
                          transactions=recent_transactions,
                          test_stocks=TEST_STOCKS,
                          now=datetime.now())

@stock_bp.route('/services/create', methods=['POST'])
def create_service():
    """Create a new stock trading service."""
    stock_symbol = request.form.get('stock_symbol')
    if not stock_symbol:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            response = jsonify({"error": "Stock symbol is required"})
            response.headers['Content-Type'] = 'application/json'
            return response, 400
        else:
            return redirect(url_for('stock.index'))
    
    try:
        starting_balance = Decimal(request.form.get('starting_balance', '1000.00'))
    except (ValueError, TypeError):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            response = jsonify({"error": "Invalid starting balance"})
            response.headers['Content-Type'] = 'application/json'
            return response, 400
        else:
            return redirect(url_for('stock.index'))
    
    # Create a new service
    try:
        service = StockTradingService(
            stock_symbol=stock_symbol,
            starting_balance=starting_balance
        )
        
        # The service_id is stored in the service.service attribute
        service_id = service.service.service_id
        
        # For demo purposes, we'll immediately start the trading cycle in a separate thread
        thread = threading.Thread(
            target=service.start_trading_cycle,
            kwargs={"polling_interval": 10},  # 10 seconds for demo purposes
            daemon=True
        )
        thread.start()
        
        logger.info(f"Started trading service for {stock_symbol} with balance {starting_balance}")
        
        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            response = jsonify({
                "success": True,
                "message": f"Trading service for {stock_symbol} started successfully",
                "service_id": service_id  # Use the extracted service_id
            })
            response.headers['Content-Type'] = 'application/json'
            return response
        else:
            return redirect(url_for('stock.index'))
    
    except Exception as e:
        logger.error(f"Error creating service: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            response = jsonify({"error": str(e)})
            response.headers['Content-Type'] = 'application/json'
            return response, 500
        else:
            # Flash error message and redirect
            return redirect(url_for('stock.index'))

@stock_bp.route('/services/<int:service_id>/stop', methods=['POST'])
def stop_service(service_id):
    """Stop an active stock trading service."""
    try:
        session = get_session()
        service = session.query(StockService).filter_by(service_id=service_id).first()
        
        if not service:
            session.close()
            response = jsonify({"error": "Service not found"})
            response.headers['Content-Type'] = 'application/json'
            return response, 404
        
        if service.service_state == STATE_INACTIVE:
            session.close()
            response = jsonify({"error": "Service already inactive"})
            response.headers['Content-Type'] = 'application/json'
            return response, 400
        
        # Update service state to inactive
        service.service_state = STATE_INACTIVE
        session.commit()
        session.close()
        
        logger.info(f"Stopped trading service {service_id}")
        
        # Return JSON with explicit content type
        response = jsonify({
            "success": True, 
            "message": f"Service {service_id} stopped successfully"
        })
        response.headers['Content-Type'] = 'application/json'
        return response
    
    except Exception as e:
        logger.error(f"Error stopping service: {str(e)}")
        response = jsonify({"error": str(e)})
        response.headers['Content-Type'] = 'application/json'
        return response, 500

@stock_bp.route('/services/<int:service_id>/start', methods=['POST'])
def start_service(service_id):
    """Restart an inactive stock trading service."""
    try:
        session = get_session()
        service = session.query(StockService).filter_by(service_id=service_id).first()
        
        if not service:
            logger.error(f"Service {service_id} not found")
            session.close()
            response = jsonify({"error": "Service not found"})
            response.headers['Content-Type'] = 'application/json'
            return response, 404
        
        if service.service_state == STATE_ACTIVE:
            session.close()
            response = jsonify({"error": "Service already active"})
            response.headers['Content-Type'] = 'application/json'
            return response, 400
        
        # Update service state to active
        service.service_state = STATE_ACTIVE
        
        # Set appropriate mode based on whether the service has shares
        if service.current_number_of_shares > 0:
            service.service_mode = MODE_SELL
        else:
            service.service_mode = MODE_BUY
            
        session.commit()
        
        try:
            # Start trading cycle in a separate thread
            thread = threading.Thread(
                target=StockTradingService.restart_trading_cycle,
                args=(service_id,),
                kwargs={"polling_interval": 10},  # 10 seconds for demo purposes
                daemon=True
            )
            thread.start()
            logger.info(f"Started thread for service {service_id}")
        except Exception as thread_error:
            logger.error(f"Error starting thread for service {service_id}: {str(thread_error)}")
            # Continue anyway - the service state is updated, which is most important
        
        session.close()
        logger.info(f"Restarted trading service {service_id}")
        
        # Set response headers to ensure JSON
        response = jsonify({
            "success": True, 
            "message": f"Service {service_id} started successfully"
        })
        response.headers['Content-Type'] = 'application/json'
        return response
    
    except Exception as e:
        logger.error(f"Error starting service: {str(e)}")
        session = get_session()
        try:
            # Try to reset service state if there was an error
            service = session.query(StockService).filter_by(service_id=service_id).first()
            if service:
                service.service_state = STATE_INACTIVE
                session.commit()
        except Exception as rollback_error:
            logger.error(f"Error rolling back service state: {str(rollback_error)}")
        finally:
            session.close()
        
        response = jsonify({"error": str(e)})
        response.headers['Content-Type'] = 'application/json'
        return response, 500

@stock_bp.route('/transactions/recent')
def recent_transactions():
    """Get recent transactions for AJAX updates."""
    try:
        session = get_session()
        transactions = (
            session.query(StockTransaction)
            .order_by(desc(StockTransaction.transaction_id))
            .limit(10)
            .all()
        )
        
        # Convert to list of dicts for JSON serialization
        result = []
        for t in transactions:
            result.append({
                "transaction_id": t.transaction_id,
                "service_id": t.service_id,
                "stock_symbol": t.stock_symbol,
                "number_of_shares": t.number_of_shares,
                "purchase_price": str(t.purchase_price),
                "sale_price": str(t.sale_price) if t.sale_price else None,
                "gain_loss": str(t.gain_loss) if t.gain_loss else None,
                "date_time_of_purchase": t.date_time_of_purchase.isoformat() if t.date_time_of_purchase else None,
                "date_time_of_sale": t.date_time_of_sale.isoformat() if t.date_time_of_sale else None
            })
        
        session.close()
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error getting recent transactions: {str(e)}")
        return jsonify({"error": str(e)}), 500

@stock_bp.route('/services/active')
def active_services():
    """Get active services for AJAX updates."""
    try:
        session = get_session()
        services = session.query(StockService).all()
        
        # Convert to list of dicts for JSON serialization
        result = []
        for s in services:
            result.append({
                "service_id": s.service_id,
                "stock_symbol": s.stock_symbol,
                "starting_balance": str(s.starting_balance),
                "fund_balance": str(s.fund_balance),
                "total_gain_loss": str(s.total_gain_loss),
                "current_number_of_shares": s.current_number_of_shares,
                "service_state": s.service_state,
                "service_mode": s.service_mode,
                "start_date": s.start_date.isoformat() if s.start_date else None,
                "number_of_buy_transactions": s.number_of_buy_transactions,
                "number_of_sell_transactions": s.number_of_sell_transactions
            })
        
        session.close()
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error getting active services: {str(e)}")
        return jsonify({"error": str(e)}), 500
