"""
WebSocket event handlers for the Day Trader application.

This module contains all WebSocket event handlers and related functionality.
"""
from flask import current_app
from flask_socketio import emit, join_room, leave_room
import functools
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Store for active socket connections
active_connections = {}

# Standardized error response
def create_error_response(message, code=400, details=None):
    """
    Create a standardized error response for WebSocket events.
    
    Args:
        message (str): The error message
        code (int): The error code (similar to HTTP status codes)
        details (dict, optional): Additional error details
        
    Returns:
        dict: Standardized error response
    """
    response = {
        'error': True,
        'code': code,
        'message': message,
        'timestamp': datetime.now().isoformat()
    }
    
    if details:
        response['details'] = details
        
    return response

def socketio_handler(event_name):
    """
    Decorator for SocketIO event handlers.
    
    Args:
        event_name (str): The name of the event
        
    Returns:
        Decorated function
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            logger.debug(f"Received '{event_name}' event: {args}")
            try:
                return f(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in '{event_name}' handler: {str(e)}")
                error_response = create_error_response(
                    message=str(e),
                    code=500,
                    details={'event': event_name}
                )
                emit('error', error_response)
        return wrapped
    return decorator

# Connect/disconnect events
@socketio_handler('connect')
def handle_connect():
    """Handle client connection."""
    logger.info("Client connected")
    # Store connection information if needed
    emit('connected', {'status': 'connected'})

@socketio_handler('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info("Client disconnected")
    # Clean up connection information if needed

# Service-related events
@socketio_handler('join_service')
def join_service_room(data):
    """
    Join a room for a specific service.
    
    Args:
        data (dict): Contains service_id
    """
    service_id = data.get('service_id')
    if not service_id:
        error = create_error_response(
            message='service_id is required', 
            code=400, 
            details={'required_fields': ['service_id']}
        )
        emit('error', error)
        return
        
    room = f"service_{service_id}"
    join_room(room)
    logger.debug(f"Client joined room: {room}")
    emit('joined', {'room': room}, room=room)

@socketio_handler('leave_service')
def leave_service_room(data):
    """
    Leave a room for a specific service.
    
    Args:
        data (dict): Contains service_id
    """
    service_id = data.get('service_id')
    if not service_id:
        error = create_error_response(
            message='service_id is required', 
            code=400, 
            details={'required_fields': ['service_id']}
        )
        emit('error', error)
        return
        
    room = f"service_{service_id}"
    leave_room(room)
    logger.debug(f"Client left room: {room}")
    emit('left', {'room': room})

# Price update events
@socketio_handler('join_price_updates')
def join_price_updates():
    """Join the price updates room to receive all price updates."""
    room = "price_updates"
    join_room(room)
    logger.debug(f"Client joined price updates room")
    emit('joined', {'room': room}, room=room)

# All services updates
@socketio_handler('join_services')
def join_services():
    """Join the services room to receive updates for all services."""
    room = "services"
    join_room(room)
    logger.debug(f"Client joined services room")
    emit('joined', {'room': room}, room=room)

# Transaction updates
@socketio_handler('join_transactions')
def join_transactions():
    """Join the transactions room to receive all transaction updates."""
    room = "transactions"
    join_room(room)
    logger.debug(f"Client joined transactions room")
    emit('joined', {'room': room}, room=room)

def register_socketio_handlers(socketio):
    """
    Register all SocketIO event handlers.
    
    Args:
        socketio: The SocketIO instance
    """
    socketio.on_event('connect', handle_connect)
    socketio.on_event('disconnect', handle_disconnect)
    socketio.on_event('join_service', join_service_room)
    socketio.on_event('leave_service', leave_service_room)
    socketio.on_event('join_price_updates', join_price_updates)
    socketio.on_event('join_services', join_services)
    socketio.on_event('join_transactions', join_transactions)
    
    logger.info("Registered SocketIO event handlers") 