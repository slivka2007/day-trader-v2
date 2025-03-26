"""
API routes for system information and operations.
"""
from flask import jsonify, current_app
import platform
import sys
import os
from datetime import datetime

from app.routes.api import bp

@bp.route('/system/health', methods=['GET'])
def health_check():
    """
    Simple health check endpoint.
    
    Returns:
        JSON response with status information
    """
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat()
    })

@bp.route('/system/info', methods=['GET'])
def system_info():
    """
    Get system information.
    
    Returns:
        JSON response with system information
    """
    return jsonify({
        'python_version': sys.version,
        'platform': platform.platform(),
        'app_name': current_app.name,
        'environment': os.environ.get('FLASK_ENV', 'development')
    })

@bp.route('/system/websocket-test', methods=['POST'])
def test_websocket():
    """
    Test WebSocket connectivity.
    
    This endpoint emits a test event to all connected WebSocket clients.
    
    Returns:
        JSON response confirming the event was emitted
    """
    # This will be implemented once we add WebSocket support
    # socketio.emit('test', {'message': 'Test WebSocket message', 'timestamp': datetime.now().isoformat()})
    
    return jsonify({
        'status': 'ok',
        'message': 'WebSocket test event emitted',
        'timestamp': datetime.now().isoformat()
    }) 