#!/usr/bin/env python3
"""
Main application file for the day-trader-v1 application.
"""
import os
import logging
from datetime import datetime, timedelta

from flask import Flask, render_template
from flask_socketio import SocketIO
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from app.services.database import setup_database, get_db_session
from app.socket_events import register_socketio_handlers

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create Flask-SocketIO instance
socketio = SocketIO()

def create_app(config=None):
    """
    Application factory function.
    
    Args:
        config: Configuration for the application
        
    Returns:
        The configured Flask application
    """
    # Create Flask app
    app = Flask(__name__)
    
    # Set default configuration
    app.config.update(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev_key_for_development'),
        DEBUG=os.environ.get('FLASK_DEBUG', 'True').lower() in ('true', '1', 't'),
        CORS_HEADERS='Content-Type',
        RESTX_MASK_SWAGGER=False,  # Show all fields in Swagger docs
        
        # JWT Configuration
        JWT_SECRET_KEY=os.environ.get('JWT_SECRET_KEY', 'jwt_dev_key_for_development'),
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(hours=1),
        JWT_REFRESH_TOKEN_EXPIRES=timedelta(days=30),
        JWT_TOKEN_LOCATION=['headers'],
        JWT_HEADER_NAME='Authorization',
        JWT_HEADER_TYPE='Bearer'
    )
    
    # Override with custom config if provided
    if config:
        app.config.update(config)
    
    # Initialize extensions
    CORS(app)  # Enable CORS for API requests from React frontend
    socketio.init_app(app, cors_allowed_origins="*")
    jwt = JWTManager(app)  # Initialize JWT
    
    # Register SocketIO event handlers
    register_socketio_handlers(socketio)
    
    # Register REST API (Flask-RESTX)
    from app.api import api_bp
    app.register_blueprint(api_bp)
    
    # Register traditional routes for backward compatibility
    from app.routes.stock_trading import stock_bp
    from app.routes.stock_data import data_bp
    app.register_blueprint(stock_bp)
    app.register_blueprint(data_bp)
    
    # Home route
    @app.route('/')
    def index():
        """Main landing page."""
        return render_template('index.html', now=datetime.now())
    
    # Make socketio available to routes
    app.socketio = socketio
    
    return app

def initialize_application():
    """
    Initialize the application, including database setup.
    
    Returns:
        Engine: SQLAlchemy engine
    """
    logger.info("Initializing day-trader-v1 application...")
    
    # Determine if we should reset the database (in development)
    reset_db: bool = os.environ.get('RESET_DB', 'True').lower() in ('true', '1', 't')
    
    # Setup database
    engine = setup_database(reset_on_startup=reset_db)
    
    logger.info("Application initialization complete.")
    return engine

def main():
    """Main application entry point."""
    engine = initialize_application()
    
    # Start the Flask app
    app = create_app()
    
    # Run the app with SocketIO
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, debug=app.config['DEBUG'], host='0.0.0.0', port=port)

if __name__ == "__main__":
    main()
