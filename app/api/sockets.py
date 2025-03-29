"""
WebSocket event handlers for the Day Trader application.

This module provides comprehensive event handlers for real-time updates via WebSockets.
It handles connections, room management, and various event subscriptions.
"""
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
        - 'users': For user account updates
        - 'stocks': For general stock updates
        - 'metrics': For analytics dashboard updates
        - 'system': For system-wide notifications
        - 'system_{severity}': For filtered system notifications by severity
        - 'errors': For error events
        - 'data_feeds': For consolidated data feeds
        - 'database_admin': For database operation events
        - 'service_{id}': For updates to a specific service (use service_id parameter)
        - 'stock_{symbol}': For updates to a specific stock (use symbol parameter)
        - 'user_{id}': For updates to a specific user (use user_id parameter)
        
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

    # ========== USER EVENT HANDLERS ==========
    
    @socketio.on('join_users')
    @socketio_handler('join_users')
    def join_users():
        """
        Join the users room to receive all user updates.
        
        This is a convenience method that joins the 'users' room.
        For consistency, prefer using the generic 'join' event with the room parameter.
        """
        room = "users"
        join_room(room)
        logger.debug(f"Client joined users room")
        emit('joined', {'room': room}, room=room)
    
    @socketio.on('user_watch')
    @socketio_handler('user_watch')
    def handle_user_watch(data):
        """
        Handle watching a specific user.
        
        This is a convenience method that joins the 'user_{id}' room.
        For consistency, prefer using the generic 'join' event with the room parameter.
        """
        if not isinstance(data, dict) or 'user_id' not in data:
            emit('error', create_error_response('Invalid user watch request',
                                               details={'required_fields': ['user_id']}))
            return
            
        user_id = data['user_id']
        room = f'user_{user_id}'
        logger.info(f'Client watching user ID: {user_id}')
        join_room(room)
        emit('watch_response', {'status': 'watching', 'type': 'user', 'id': user_id})
    
    # ========== METRICS EVENT HANDLERS ==========
    
    @socketio.on('join_metrics')
    @socketio_handler('join_metrics')
    def join_metrics():
        """
        Join the metrics room to receive all metrics updates.
        
        This is a convenience method that joins the 'metrics' room.
        For consistency, prefer using the generic 'join' event with the room parameter.
        """
        room = "metrics"
        join_room(room)
        logger.debug(f"Client joined metrics room")
        emit('joined', {'room': room}, room=room)
    
    # ========== SYSTEM NOTIFICATION HANDLERS ==========
    
    @socketio.on('join_system')
    @socketio_handler('join_system')
    def join_system(data=None):
        """
        Join the system notifications room.
        
        Optionally specify a severity to only receive notifications of that level.
        Valid severity levels: 'info', 'warning', 'error', 'critical'
        
        This is a convenience method that joins the 'system' or 'system_{severity}' room.
        For consistency, prefer using the generic 'join' event with the room parameter.
        """
        severity = None
        if isinstance(data, dict) and 'severity' in data:
            severity = data['severity']
            if severity not in ['info', 'warning', 'error', 'critical']:
                emit('error', create_error_response('Invalid severity level',
                                                   details={'valid_levels': ['info', 'warning', 'error', 'critical']}))
                return
        
        room = "system" if severity is None else f"system_{severity}"
        join_room(room)
        logger.debug(f"Client joined system notifications room: {room}")
        emit('joined', {'room': room}, room=room)
    
    # ========== ERROR EVENT HANDLERS ==========
    
    @socketio.on('join_errors')
    @socketio_handler('join_errors')
    def join_errors():
        """
        Join the errors room to receive all error events.
        
        This is a convenience method that joins the 'errors' room.
        For consistency, prefer using the generic 'join' event with the room parameter.
        """
        room = "errors"
        join_room(room)
        logger.debug(f"Client joined errors room")
        emit('joined', {'room': room}, room=room)
    
    # ========== DATA FEED HANDLERS ==========
    
    @socketio.on('join_data_feeds')
    @socketio_handler('join_data_feeds')
    def join_data_feeds():
        """
        Join the data feeds room to receive consolidated data updates.
        
        This is a convenience method that joins the 'data_feeds' room.
        For consistency, prefer using the generic 'join' event with the room parameter.
        """
        room = "data_feeds"
        join_room(room)
        logger.debug(f"Client joined data feeds room")
        emit('joined', {'room': room}, room=room)
    
    # ========== DATABASE EVENT HANDLERS ==========
    
    @socketio.on('join_database_admin')
    @socketio_handler('join_database_admin')
    def join_database_admin():
        """
        Join the database_admin room to receive database operation events.
        
        This is a convenience method that joins the 'database_admin' room.
        For consistency, prefer using the generic 'join' event with the room parameter.
        """
        room = "database_admin"
        join_room(room)
        logger.debug(f"Client joined database admin room")
        emit('joined', {'room': room}, room=room)

    logger.info('WebSocket event handlers registered')
    return socketio 