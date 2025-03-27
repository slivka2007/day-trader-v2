"""
WebSocket event handlers for the Day Trader application.

This module provides comprehensive event handlers for real-time updates via WebSockets.
It handles connections, room management, and various event subscriptions.
"""
from flask import current_app
from flask_socketio import emit, join_room, leave_room
import functools
import logging
from app.utils.current_datetime import get_current_datetime

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
        'timestamp': get_current_datetime().isoformat()
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

def register_handlers(socketio):
    """Register all WebSocket event handlers."""
    
    # ========== CONNECTION EVENTS ==========
    
    @socketio.on('connect')
    @socketio_handler('connect')
    def handle_connect():
        """Handle client connection."""
        logger.info('Client connected to WebSocket')
        emit('connection_response', {'status': 'connected'})
    
    @socketio.on('disconnect')
    @socketio_handler('disconnect')
    def handle_disconnect():
        """Handle client disconnection."""
        logger.info('Client disconnected from WebSocket')
    
    # ========== ROOM MANAGEMENT ==========
    
    @socketio.on('join')
    @socketio_handler('join')
    def handle_join(data):
        """
        Handle a client joining a room.
        
        Rooms supported:
        - 'services': For all trading service updates
        - 'transactions': For all transaction updates
        - 'price_updates': For all stock price updates
        - 'service_{id}': For updates to a specific service (use service_id parameter)
        - 'stock_{symbol}': For updates to a specific stock (use symbol parameter)
        
        Example:
        ```
        socket.emit('join', {'room': 'services'})  # Join all services updates
        socket.emit('join', {'room': 'service_123'})  # Join specific service updates
        ```
        """
        if not isinstance(data, dict) or 'room' not in data:
            emit('error', create_error_response('Invalid join request format'))
            return
            
        room = data['room']
        logger.info(f'Client joining room: {room}')
        join_room(room)
        emit('join_response', {'status': 'joined', 'room': room}, room=room)
    
    @socketio.on('leave')
    @socketio_handler('leave')
    def handle_leave(data):
        """Handle a client leaving a room."""
        if not isinstance(data, dict) or 'room' not in data:
            emit('error', create_error_response('Invalid leave request format'))
            return
            
        room = data['room']
        logger.info(f'Client leaving room: {room}')
        leave_room(room)
        emit('leave_response', {'status': 'left', 'room': room})
    
    # ========== SERVICE EVENT HANDLERS ==========
    
    @socketio.on('service_watch')
    @socketio_handler('service_watch')
    def handle_service_watch(data):
        """
        Handle watching a specific trading service.
        
        This is a convenience method that joins the 'service_{id}' room.
        For consistency, prefer using the generic 'join' event with the room parameter.
        """
        if not isinstance(data, dict) or 'service_id' not in data:
            emit('error', create_error_response('Invalid service watch request', 
                                               details={'required_fields': ['service_id']}))
            return
            
        service_id = data['service_id']
        room = f'service_{service_id}'
        logger.info(f'Client watching service ID: {service_id}')
        join_room(room)
        emit('watch_response', {'status': 'watching', 'type': 'service', 'id': service_id})
    
    @socketio.on('join_services')
    @socketio_handler('join_services')
    def join_services():
        """
        Join the services room to receive updates for all services.
        
        This is a convenience method that joins the 'services' room.
        For consistency, prefer using the generic 'join' event with the room parameter.
        """
        room = "services"
        join_room(room)
        logger.debug(f"Client joined services room")
        emit('joined', {'room': room}, room=room)
    
    # ========== STOCK EVENT HANDLERS ==========
    
    @socketio.on('stock_watch')
    @socketio_handler('stock_watch')
    def handle_stock_watch(data):
        """
        Handle watching a specific stock.
        
        This is a convenience method that joins the 'stock_{symbol}' room.
        For consistency, prefer using the generic 'join' event with the room parameter.
        """
        if not isinstance(data, dict) or 'symbol' not in data:
            emit('error', create_error_response('Invalid stock watch request',
                                               details={'required_fields': ['symbol']}))
            return
            
        symbol = data['symbol'].upper()
        room = f'stock_{symbol}'
        logger.info(f'Client watching stock: {symbol}')
        join_room(room)
        emit('watch_response', {'status': 'watching', 'type': 'stock', 'symbol': symbol})
    
    @socketio.on('join_price_updates')
    @socketio_handler('join_price_updates')
    def join_price_updates():
        """
        Join the price updates room to receive all price updates.
        
        This is a convenience method that joins the 'price_updates' room.
        For consistency, prefer using the generic 'join' event with the room parameter.
        """
        room = "price_updates"
        join_room(room)
        logger.debug(f"Client joined price updates room")
        emit('joined', {'room': room}, room=room)
    
    # ========== TRANSACTION EVENT HANDLERS ==========
    
    @socketio.on('join_transactions')
    @socketio_handler('join_transactions')
    def join_transactions():
        """
        Join the transactions room to receive all transaction updates.
        
        This is a convenience method that joins the 'transactions' room.
        For consistency, prefer using the generic 'join' event with the room parameter.
        """
        room = "transactions"
        join_room(room)
        logger.debug(f"Client joined transactions room")
        emit('joined', {'room': room}, room=room)

    logger.info('WebSocket event handlers registered')
    return socketio

# Public function for initializing WebSockets in the main app
def init_websockets(app):
    """Initialize WebSocket handlers"""
    from flask_socketio import SocketIO
    
    # Create SocketIO instance with CORS support
    socketio = SocketIO(cors_allowed_origins="*")
    socketio.init_app(app)
    
    # Register all event handlers
    register_handlers(socketio)
    
    # Store reference in app for easy access from routes
    app.socketio = socketio
    
    return socketio 