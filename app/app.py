#!/usr/bin/env python3
"""
Main application file for the day-trader-v1 application.
"""
import os
import logging
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template

from database.scripts.database import setup_database
from app.stock_trading import stock_bp
from app.stock_data import data_bp

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key_for_development')

# Register blueprints
app.register_blueprint(stock_bp)
app.register_blueprint(data_bp)

@app.route('/')
def index():
    """Main landing page."""
    return render_template('index.html', now=datetime.now())

def initialize_application():
    """Initialize the application, including database setup."""
    logger.info("Initializing day-trader-v1 application...")
    
    # Determine if we should reset the database (in development)
    # For production, this would be set to False
    reset_db: bool = os.environ.get('RESET_DB', 'True').lower() in ('true', '1', 't')
    
    # Setup database
    engine = setup_database(reset_on_startup=reset_db)
    
    logger.info("Application initialization complete.")
    return engine

def main():
    """Main application entry point."""
    engine = initialize_application()
    
    # Start the Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)

if __name__ == "__main__":
    main()
