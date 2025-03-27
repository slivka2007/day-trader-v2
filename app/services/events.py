"""
Event emission service for WebSocket notifications.

This module centralizes WebSocket event emission logic to ensure consistent
formatting and behavior across the application.
"""
import logging
from typing import Dict, Any, Optional
from flask import current_app

from app.utils.current_datetime import get_current_datetime

logger = logging.getLogger(__name__)


class EventService:
    """Service for emitting standardized WebSocket events."""
    
    @staticmethod
    def emit(event_type: str, data: Dict[str, Any], room: str, 
             include_timestamp: bool = True) -> None:
        """
        Emit a WebSocket event to a specific room.
        
        Args:
            event_type: The event type (e.g., 'service_update', 'price_update')
            data: The event payload
            room: The room to emit to (e.g., 'services', 'service_123')
            include_timestamp: Whether to include a timestamp in the payload
        """
        try:
            # Ensure socketio is available
            if not hasattr(current_app, 'socketio'):
                logger.warning("SocketIO not initialized, skipping event emission")
                return
                
            # Add timestamp if requested
            if include_timestamp and 'timestamp' not in data:
                data['timestamp'] = get_current_datetime().isoformat()
                
            # Emit the event
            current_app.socketio.emit(event_type, data, room=room)
            logger.debug(f"Emitted {event_type} event to room {room}")
            
        except Exception as e:
            logger.error(f"Error emitting {event_type} event: {str(e)}")
    
    @classmethod
    def emit_service_update(cls, action: str, service_data: Dict[str, Any], 
                          service_id: Optional[int] = None) -> None:
        """
        Emit a service update event.
        
        Args:
            action: The action that occurred (e.g., 'created', 'updated', 'state_changed')
            service_data: The service data (typically from service_schema.dump())
            service_id: The service ID for room-specific events
        """
        payload = {
            'action': action,
            'service': service_data
        }
        
        # Emit to general services room
        cls.emit('service_update', payload, room='services')
        
        # If service_id is provided, also emit to the specific service room
        if service_id:
            cls.emit('service_update', payload, room=f'service_{service_id}')

    @classmethod
    def emit_transaction_update(cls, action: str, transaction_data: Dict[str, Any], 
                              service_id: Optional[int] = None,
                              additional_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Emit a transaction update event.
        
        Args:
            action: The action that occurred (e.g., 'created', 'completed', 'cancelled')
            transaction_data: The transaction data
            service_id: The associated service ID
            additional_data: Any additional data to include in the payload
        """
        payload = {
            'action': action,
            'transaction': transaction_data
        }
        
        # Add any additional data
        if additional_data:
            payload.update(additional_data)
            
        # Emit to general transactions room
        cls.emit('transaction_update', payload, room='transactions')
        
        # If service_id is provided, emit service-specific update
        if service_id:
            service_payload = {
                'action': f'transaction_{action}',
                'transaction_id': transaction_data.get('id'),
                'service_id': service_id
            }
            
            if additional_data:
                service_payload.update(additional_data)
                
            cls.emit('service_update', service_payload, room=f'service_{service_id}')
    
    @classmethod
    def emit_price_update(cls, action: str, price_data: Dict[str, Any], 
                        stock_symbol: str) -> None:
        """
        Emit a price update event.
        
        Args:
            action: The action that occurred (e.g., 'created')
            price_data: The price data
            stock_symbol: The stock symbol
        """
        payload = {
            'action': action,
            'price': price_data,
            'stock_symbol': stock_symbol
        }
        
        # Emit to general price_updates room
        cls.emit('price_update', payload, room='price_updates')
        
        # Emit to stock-specific room
        cls.emit('price_update', payload, room=f'stock_{stock_symbol}')

    @classmethod
    def emit_error(cls, error_message: str, error_code: int = 500, 
                 details: Optional[Dict[str, Any]] = None) -> None:
        """
        Emit an error event.
        
        Args:
            error_message: The error message
            error_code: The error code (similar to HTTP status codes)
            details: Additional error details
        """
        payload = {
            'error': True,
            'message': error_message,
            'code': error_code
        }
        
        if details:
            payload['details'] = details
            
        cls.emit('error', payload, room='errors') 