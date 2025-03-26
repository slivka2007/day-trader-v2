#!/usr/bin/env python3
"""
Startup script for the day-trader-v1 application.

This script is used to start the application. It's separate from app.py
to keep the application logic separate from the startup code.
"""
import os
from app.app import create_app, socketio, initialize_application

if __name__ == '__main__':
    # Initialize the application (setup database, etc.)
    engine = initialize_application()
    
    # Create the application
    app = create_app()
    
    # Run the app with SocketIO
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')
    port = int(os.environ.get('PORT', 5000))
    
    print(f"Starting day-trader-v1 on http://localhost:{port}")
    socketio.run(app, debug=debug, host='0.0.0.0', port=port)
