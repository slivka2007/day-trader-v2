#!/usr/bin/env python3
"""
Main application file for the day-trader-v1 application.
"""
import os
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from sqlalchemy import Engine, desc
from flask import Flask, render_template, request, jsonify, redirect, url_for

from app.database import setup_database, check_and_update_schema, get_session
from app.models.stock_service_model import StockService, STATE_ACTIVE, STATE_INACTIVE, MODE_BUY, MODE_SELL
from app.models.stock_transaction_model import StockTransaction
from app.services.stock_service import StockTradingService
from app.apis.stock_purchase_api import MOCK_PRICES

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Available test stocks
TEST_STOCKS = list(MOCK_PRICES.keys())

def initialize_application() -> Engine:
    """Initialize the application, including database setup.
    
    Returns:
        Engine: SQLAlchemy engine instance
    """
    logger.info("Initializing day-trader-v1 application...")
    
    # Determine if we should reset the database (in development)
    # For production, this would be set to False
    reset_db: bool = os.environ.get('RESET_DB', 'True').lower() in ('true', '1', 't')
    
    # Setup database - this will also update the database.sql file if needed
    engine: Engine = setup_database(reset_on_startup=reset_db)
    
    logger.info("Application initialization complete.")
    return engine

@app.route('/')
def index():
    """Main dashboard page."""
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
    
    return render_template('index.html', 
                          services=services,
                          transactions=recent_transactions,
                          test_stocks=TEST_STOCKS,
                          now=datetime.now())

@app.route('/services/create', methods=['POST'])
def create_service():
    """Create a new stock trading service."""
    stock_symbol = request.form.get('stock_symbol')
    if not stock_symbol:
        return jsonify({"error": "Stock symbol is required"}), 400
    
    try:
        starting_balance = Decimal(request.form.get('starting_balance', '1000.00'))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid starting balance"}), 400
    
    # Create a new service
    try:
        service = StockTradingService(
            stock_symbol=stock_symbol,
            starting_balance=starting_balance
        )
        
        # For demo purposes, we'll immediately start the trading cycle in a separate thread
        import threading
        thread = threading.Thread(
            target=service.start_trading_cycle,
            kwargs={"polling_interval": 10},  # 10 seconds for demo purposes
            daemon=True
        )
        thread.start()
        
        logger.info(f"Started trading service for {stock_symbol} with balance {starting_balance}")
        return redirect(url_for('index'))
    
    except Exception as e:
        logger.error(f"Error creating service: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/services/<int:service_id>/stop', methods=['POST'])
def stop_service(service_id):
    """Stop an active stock trading service."""
    try:
        session = get_session()
        service = session.query(StockService).filter_by(service_id=service_id).first()
        
        if not service:
            session.close()
            return jsonify({"error": "Service not found"}), 404
        
        if service.service_state == STATE_INACTIVE:
            session.close()
            return jsonify({"error": "Service already inactive"}), 400
        
        # Update service state to inactive
        service.service_state = STATE_INACTIVE
        session.commit()
        session.close()
        
        logger.info(f"Stopped trading service {service_id}")
        
        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": True, "message": f"Service {service_id} stopped successfully"})
        else:
            return redirect(url_for('index'))
    
    except Exception as e:
        logger.error(f"Error stopping service: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/services/<int:service_id>/start', methods=['POST'])
def start_service(service_id):
    """Restart an inactive stock trading service."""
    logger.info(f"Received request to start service {service_id}")
    logger.info(f"Request headers: {request.headers}")
    
    try:
        session = get_session()
        service = session.query(StockService).filter_by(service_id=service_id).first()
        
        if not service:
            logger.error(f"Service {service_id} not found")
            session.close()
            return jsonify({"error": "Service not found"}), 404
        
        if service.service_state == STATE_ACTIVE:
            session.close()
            return jsonify({"error": "Service already active"}), 400
        
        # Update service state to active
        service.service_state = STATE_ACTIVE
        
        # Set appropriate mode based on whether the service has shares
        if service.current_number_of_shares > 0:
            service.service_mode = MODE_SELL
        else:
            service.service_mode = MODE_BUY
            
        session.commit()
        
        # Start trading cycle in a separate thread
        import threading
        thread = threading.Thread(
            target=StockTradingService.restart_trading_cycle,
            args=(service_id,),
            kwargs={"polling_interval": 10},  # 10 seconds for demo purposes
            daemon=True
        )
        thread.start()
        
        session.close()
        logger.info(f"Restarted trading service {service_id}")
        
        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": True, "message": f"Service {service_id} started successfully"})
        else:
            return redirect(url_for('index'))
    
    except Exception as e:
        logger.error(f"Error starting service: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/transactions/recent')
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

@app.route('/services/active')
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

def main() -> None:
    """Main application entry point."""
    engine: Engine = initialize_application()
    
    # Start the Flask app
    app.run(debug=True)

if __name__ == "__main__":
    main()
