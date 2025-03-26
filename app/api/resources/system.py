"""
System API resources.
"""
from flask import request, current_app
from flask_restx import Namespace, Resource, fields
import platform
import sys
import os
from datetime import datetime

# Create namespace
api = Namespace('system', description='System information and operations')

# Define API models
health_model = api.model('Health', {
    'status': fields.String(description='System status'),
    'timestamp': fields.DateTime(description='Current timestamp')
})

info_model = api.model('SystemInfo', {
    'python_version': fields.String(description='Python version'),
    'platform': fields.String(description='Operating system platform'),
    'app_name': fields.String(description='Application name'),
    'environment': fields.String(description='Runtime environment')
})

websocket_test_model = api.model('WebSocketTest', {
    'status': fields.String(description='Test status'),
    'message': fields.String(description='Test message'),
    'timestamp': fields.DateTime(description='Timestamp')
})

# Define WebSocket documentation model
websocket_event_model = api.model('WebSocketEvent', {
    'name': fields.String(description='Event name'),
    'description': fields.String(description='Event description'),
    'direction': fields.String(description='Direction (server-to-client or client-to-server)'),
    'payload': fields.String(description='Example payload'),
    'rooms': fields.List(fields.String, description='Applicable rooms (if any)'),
})

websocket_room_model = api.model('WebSocketRoom', {
    'name': fields.String(description='Room name'),
    'description': fields.String(description='Room description'),
    'subscribe_event': fields.String(description='Event to emit to join this room'),
    'events': fields.List(fields.String, description='Events broadcast to this room'),
})

websocket_docs_model = api.model('WebSocketDocs', {
    'events': fields.List(fields.Nested(websocket_event_model), description='Available WebSocket events'),
    'rooms': fields.List(fields.Nested(websocket_room_model), description='Available rooms for subscription'),
})

@api.route('/health')
class Health(Resource):
    """Resource for system health check."""
    
    @api.doc('get_health')
    @api.marshal_with(health_model)
    def get(self):
        """Get the current system health status."""
        return {
            'status': 'ok',
            'timestamp': datetime.now()
        }

@api.route('/info')
class Info(Resource):
    """Resource for system information."""
    
    @api.doc('get_info')
    @api.marshal_with(info_model)
    def get(self):
        """Get system information."""
        return {
            'python_version': sys.version,
            'platform': platform.platform(),
            'app_name': current_app.name,
            'environment': os.environ.get('FLASK_ENV', 'development')
        }

@api.route('/websocket-test')
class WebSocketTest(Resource):
    """Resource for testing WebSocket functionality."""
    
    @api.doc('test_websocket')
    @api.marshal_with(websocket_test_model)
    def post(self):
        """Test WebSocket functionality by emitting an event."""
        message = request.json.get('message', 'Test WebSocket message')
        timestamp = datetime.now()
        
        # Emit the test event to all connected clients
        current_app.socketio.emit('test', {
            'message': message, 
            'timestamp': timestamp.isoformat()
        })
        
        return {
            'status': 'ok',
            'message': 'WebSocket test event emitted',
            'timestamp': timestamp
        }

@api.route('/websocket-docs')
class WebSocketDocs(Resource):
    """Resource for WebSocket documentation."""
    
    @api.doc('get_websocket_docs')
    @api.marshal_with(websocket_docs_model)
    def get(self):
        """Get documentation for WebSocket events and rooms."""
        # Document all WebSocket events
        events = [
            {
                'name': 'service_update',
                'description': 'Emitted when a trading service is created, updated, or deleted',
                'direction': 'server-to-client',
                'payload': '{"action": "created|updated|deleted|toggled", "service": {...}}',
                'rooms': ['services', 'service_{id}'],
            },
            {
                'name': 'transaction_update',
                'description': 'Emitted when a transaction is created or completed',
                'direction': 'server-to-client',
                'payload': '{"action": "created|completed", "transaction": {...}}',
                'rooms': ['transactions'],
            },
            {
                'name': 'price_update',
                'description': 'Emitted when new price data is available',
                'direction': 'server-to-client',
                'payload': '{"type": "daily|intraday", "stock_symbol": "...", "stock_id": 1, ...}',
                'rooms': ['price_updates'],
            },
            {
                'name': 'test',
                'description': 'Test event for verifying WebSocket connectivity',
                'direction': 'server-to-client',
                'payload': '{"message": "...", "timestamp": "..."}',
                'rooms': [],
            },
            {
                'name': 'error',
                'description': 'Emitted when an error occurs during event processing',
                'direction': 'server-to-client',
                'payload': '{"error": true, "code": 400, "message": "...", "timestamp": "...", "details": {...}}',
                'rooms': [],
            },
            {
                'name': 'connect',
                'description': 'Emitted when a client connects',
                'direction': 'client-to-server',
                'payload': '{}',
                'rooms': [],
            },
            {
                'name': 'disconnect',
                'description': 'Emitted when a client disconnects',
                'direction': 'client-to-server',
                'payload': '{}',
                'rooms': [],
            },
            {
                'name': 'join_service',
                'description': 'Join a room for a specific service',
                'direction': 'client-to-server',
                'payload': '{"service_id": 1}',
                'rooms': [],
            },
            {
                'name': 'leave_service',
                'description': 'Leave a room for a specific service',
                'direction': 'client-to-server',
                'payload': '{"service_id": 1}',
                'rooms': [],
            },
            {
                'name': 'join_services',
                'description': 'Join the room for all services updates',
                'direction': 'client-to-server',
                'payload': '{}',
                'rooms': [],
            },
            {
                'name': 'join_transactions',
                'description': 'Join the room for transaction updates',
                'direction': 'client-to-server',
                'payload': '{}',
                'rooms': [],
            },
            {
                'name': 'join_price_updates',
                'description': 'Join the room for price updates',
                'direction': 'client-to-server',
                'payload': '{}',
                'rooms': [],
            },
        ]
        
        # Document all rooms
        rooms = [
            {
                'name': 'service_{id}',
                'description': 'Room for updates about a specific trading service',
                'subscribe_event': 'join_service',
                'events': ['service_update'],
            },
            {
                'name': 'services',
                'description': 'Room for updates about all trading services',
                'subscribe_event': 'join_services',
                'events': ['service_update'],
            },
            {
                'name': 'transactions',
                'description': 'Room for transaction updates',
                'subscribe_event': 'join_transactions',
                'events': ['transaction_update'],
            },
            {
                'name': 'price_updates',
                'description': 'Room for stock price updates',
                'subscribe_event': 'join_price_updates',
                'events': ['price_update'],
            },
        ]
        
        return {
            'events': events,
            'rooms': rooms,
        } 