"""Event emission service for WebSocket notifications.

This module centralizes WebSocket event emission logic to ensure consistent
formatting and behavior across the application.
"""

from __future__ import annotations

import logging
from typing import TypedDict, cast

from flask import Flask, current_app

from app.utils.current_datetime import get_current_datetime

logger: logging.Logger = logging.getLogger(__name__)


# Type definitions for payload dictionaries
class PayloadDict(TypedDict, total=False):
    """Type definition for event payload dictionaries with optional fields."""

    timestamp: str
    action: str
    message: str
    type: str
    error: bool
    code: int
    details: dict[str, any]
    operation: str
    status: str
    target: str


class EventService:
    """Service for emitting standardized WebSocket events."""

    @staticmethod
    def emit(
        event_type: str,
        data: dict[str, any],
        room: str,
        *,
        include_timestamp: bool = True,
    ) -> None:
        """Emit a WebSocket event to a specific room.

        Args:
            event_type: The event type (e.g., 'service_update', 'price_update')
            data: The event payload
            room: The room to emit to (e.g., 'services', 'service_123')
            include_timestamp: Whether to include a timestamp in the payload

        """
        try:
            # Check if we're in an application context first
            try:
                app: Flask = cast("Flask", current_app)

            except RuntimeError:
                # No application context available (likely in a test environment)
                logger.debug(
                    "No application context available, skipping event emission",
                )
                return

            # Ensure socketio is available
            if not hasattr(app, "socketio"):
                logger.warning("SocketIO not initialized, skipping event emission")
                return

            # Add timestamp if requested
            if include_timestamp and "timestamp" not in data:
                data["timestamp"] = get_current_datetime().isoformat()

            # Emit the event
            app.socketio.emit(event_type, data, room=room)
            logger.debug("Emitted %s event to room %s", event_type, room)

        except Exception:
            logger.exception("Error emitting %s event", event_type)

    @classmethod
    def emit_test(cls, message: str, room: str = "test") -> None:
        """Emit a test event for WebSocket functionality verification.

        Args:
            message: The test message
            room: The room to emit to (default: 'test')

        """
        payload: dict[str, any] = {"message": message, "type": "test_event"}

        cls.emit("test", payload, room=room)

    @classmethod
    def emit_stock_update(
        cls,
        action: str,
        stock_data: dict[str, any],
        stock_symbol: str | None = None,
    ) -> None:
        """Emit a stock update event.

        Args:
            action: The action that occurred (e.g., 'created', 'updated',
            'status_changed')
            stock_data: The stock data (typically from stock_schema.dump())
            stock_symbol: The stock symbol for room-specific events

        """
        payload: dict[str, any] = {"action": action, "stock": stock_data}

        # Emit to general stocks room
        cls.emit("stock_update", payload, room="stocks")

        # If stock_symbol is provided, also emit to the specific stock room
        if stock_symbol:
            cls.emit("stock_update", payload, room=f"stock_{stock_symbol}")

    @classmethod
    def emit_service_update(
        cls,
        action: str,
        service_data: dict[str, any],
        service_id: int | None = None,
    ) -> None:
        """Emit a service update event.

        Args:
            action: The action that occurred (e.g., 'created', 'updated',
            'state_changed')
            service_data: The service data (typically from service_schema.dump())
            service_id: The service ID for room-specific events

        """
        payload: dict[str, any] = {"action": action, "service": service_data}

        # Emit to general services room
        cls.emit("service_update", payload, room="services")

        # If service_id is provided, also emit to the specific service room
        if service_id:
            cls.emit("service_update", payload, room=f"service_{service_id}")

    @classmethod
    def emit_user_update(
        cls,
        action: str,
        user_data: dict[str, any],
        user_id: int | None = None,
        *,
        include_sensitive: bool = False,
    ) -> None:
        """Emit a user update event.

        Args:
            action: The action that occurred (e.g., 'created', 'updated', 'activated',
            'deactivated')
            user_data: The user data (typically from user_schema.dump())
            user_id: The user ID for room-specific events
            include_sensitive: Whether to include sensitive user data (default: False)

        """
        # Filter out sensitive data if needed
        payload_user_data: dict[str, any] = user_data.copy()
        if not include_sensitive:
            # Remove sensitive fields that should not be broadcast
            sensitive_fields: list[str] = ["password", "last_login_days_ago"]
            for field in sensitive_fields:
                payload_user_data.pop(field, None)

        payload: dict[str, any] = {"action": action, "user": payload_user_data}

        # Emit to admin room (for admin dashboards)
        cls.emit("user_update", payload, room="users")

        # If user_id is provided, also emit to the specific user's room
        if user_id:
            cls.emit("user_update", payload, room=f"user_{user_id}")

    @classmethod
    def emit_transaction_update(
        cls,
        action: str,
        transaction_data: dict[str, any],
        service_id: int | None = None,
        additional_data: dict[str, any] | None = None,
    ) -> None:
        """Emit a transaction update event.

        Args:
            action: The action that occurred (e.g., 'created', 'completed', 'cancelled')
            transaction_data: The transaction data
            service_id: The associated service ID
            additional_data: Additional data to include in the payload

        """
        payload: dict[str, any] = {"action": action, "transaction": transaction_data}

        # Add any additional data
        if additional_data:
            payload.update(additional_data)

        # Emit to general transactions room
        cls.emit("transaction_update", payload, room="transactions")

        # If service_id is provided, emit service-specific update
        if service_id:
            service_payload: dict[str, any] = {
                "action": f"transaction_{action}",
                "transaction_id": transaction_data.get("id"),
                "service_id": service_id,
            }

            if additional_data:
                service_payload.update(additional_data)

            cls.emit("service_update", service_payload, room=f"service_{service_id}")

    @classmethod
    def emit_price_update(
        cls,
        action: str,
        price_data: dict[str, any],
        stock_symbol: str,
    ) -> None:
        """Emit a price update event.

        Args:
            action: The action that occurred (e.g., 'created', 'updated')
            price_data: The price data
            stock_symbol: The stock symbol

        """
        payload: dict[str, any] = {
            "action": action,
            "price": price_data,
            "stock_symbol": stock_symbol,
        }

        # Emit to general price_updates room
        cls.emit("price_update", payload, room="price_updates")

        # Emit to stock-specific room
        cls.emit("price_update", payload, room=f"stock_{stock_symbol}")

        # Emit consolidated price update for data feeds
        cls.emit(
            "data_feed",
            {"type": "price_update", "data": payload},
            room="data_feeds",
        )

    @classmethod
    def emit_error(
        cls,
        error_message: str,
        error_code: int = 500,
        details: dict[str, any] | None = None,
    ) -> None:
        """Emit an error event.

        Args:
            error_message: The error message
            error_code: The error code (similar to HTTP status codes)
            details: Additional error details

        """
        payload: dict[str, any] = {
            "error": True,
            "message": error_message,
            "code": error_code,
        }

        if details:
            payload["details"] = details

        cls.emit("error", payload, room="errors")

    @classmethod
    def emit_metrics_update(
        cls,
        metric_type: str,
        metric_data: dict[str, any],
        resource_id: int | None = None,
        resource_type: str | None = None,
    ) -> None:
        """Emit a metrics update event for analytics dashboards.

        Args:
            metric_type: The type of metrics (e.g., 'performance', 'transaction_stats')
            metric_data: The metrics data
            resource_id: Optional ID of the related resource
            resource_type: Optional type of the related resource

        """
        payload: dict[str, any] = {"type": metric_type, "metrics": metric_data}

        if resource_id is not None and resource_type:
            payload["resource"] = {"id": resource_id, "type": resource_type}

        # Emit to general metrics room
        cls.emit("metrics_update", payload, room="metrics")

        # If resource details are provided, also emit to resource-specific room
        if resource_id is not None and resource_type:
            cls.emit(
                "metrics_update",
                payload,
                room=f"{resource_type}_{resource_id}_metrics",
            )

    @classmethod
    def emit_system_notification(
        cls,
        notification_type: str,
        message: str,
        severity: str = "info",
        details: dict[str, any] | None = None,
    ) -> None:
        """Emit a system-wide notification event.

        Args:
            notification_type: The type of notification (e.g., 'maintenance', 'alert')
            message: The notification message
            severity: The severity level ('info', 'warning', 'error', 'critical')
            details: Optional additional details

        """
        payload: dict[str, any] = {
            "type": notification_type,
            "message": message,
            "severity": severity,
        }

        if details:
            payload["details"] = details

        # Emit to system notifications room
        cls.emit("system_notification", payload, room="system")

        # Also emit to severity-specific room for filtered subscriptions
        cls.emit("system_notification", payload, room=f"system_{severity}")

    @classmethod
    def emit_database_event(
        cls,
        operation: str,
        status: str,
        target: str | None = None,
        details: dict[str, any] | None = None,
    ) -> None:
        """Emit a database operation event.

        Args:
            operation: The operation performed (e.g., 'backup', 'restore', 'migration')
            status: The operation status ('started', 'completed', 'failed')
            target: Optional target of the operation (e.g., table name or backup file)
            details: Optional additional details

        """
        payload: dict[str, any] = {"operation": operation, "status": status}

        if target:
            payload["target"] = target

        if details:
            payload["details"] = details

        # Emit to database events room
        cls.emit("database_event", payload, room="database_admin")
