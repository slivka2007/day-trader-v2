"""System API resources.

This module provides API endpoints for system health checks, information, and
WebSocket documentation.

"""

from __future__ import annotations

from flask import request
from flask_restx import Model, Namespace, OrderedModel, Resource, fields

from app.services.system_service import SystemService

# Create namespace
api: Namespace = Namespace("system", description="System information and operations")

# Define API models
health_model: Model | OrderedModel = api.model(
    "Health",
    {
        "status": fields.String(description="System status"),
        "timestamp": fields.DateTime(description="Current timestamp"),
    },
)

info_model: Model | OrderedModel = api.model(
    "SystemInfo",
    {
        "python_version": fields.String(description="Python version"),
        "platform": fields.String(description="Operating system platform"),
        "app_name": fields.String(description="Application name"),
        "environment": fields.String(description="Runtime environment"),
    },
)

websocket_test_model: Model | OrderedModel = api.model(
    "WebSocketTest",
    {
        "status": fields.String(description="Test status"),
        "message": fields.String(description="Test message"),
        "timestamp": fields.DateTime(description="Timestamp"),
    },
)

# Define WebSocket documentation model
websocket_event_model: Model | OrderedModel = api.model(
    "WebSocketEvent",
    {
        "name": fields.String(description="Event name"),
        "description": fields.String(description="Event description"),
        "direction": fields.String(
            description="Direction (server-to-client or client-to-server)",
        ),
        "payload": fields.String(description="Example payload"),
        "rooms": fields.List(fields.String, description="Applicable rooms (if any)"),
    },
)

websocket_room_model: Model | OrderedModel = api.model(
    "WebSocketRoom",
    {
        "name": fields.String(description="Room name"),
        "description": fields.String(description="Room description"),
        "subscribe_event": fields.String(description="Event to emit to join this room"),
        "events": fields.List(
            fields.String,
            description="Events broadcast to this room",
        ),
    },
)

websocket_docs_model: Model | OrderedModel = api.model(
    "WebSocketDocs",
    {
        "events": fields.List(
            fields.Nested(websocket_event_model),
            description="Available WebSocket events",
        ),
        "rooms": fields.List(
            fields.Nested(websocket_room_model),
            description="Available rooms for subscription",
        ),
    },
)


@api.route("/health")
class Health(Resource):
    """Resource for system health check."""

    @api.doc("get_health")
    @api.marshal_with(health_model)
    def get(self) -> dict[str, any]:
        """Get the current system health status."""
        return SystemService.get_health_status()


@api.route("/info")
class Info(Resource):
    """Resource for system information."""

    @api.doc("get_info")
    @api.marshal_with(info_model)
    def get(self) -> dict[str, any]:
        """Get information about the system environment."""
        return SystemService.get_system_info()


@api.route("/websocket-test")
class WebSocketTest(Resource):
    """Resource for testing WebSocket functionality."""

    @api.doc("test_websocket")
    @api.marshal_with(websocket_test_model)
    def post(self) -> dict[str, any]:
        """Test WebSocket functionality by emitting an event."""
        message: str = (request.json or {}).get("message", "Test WebSocket message")
        return SystemService.test_websocket(message)


@api.route("/websocket-docs")
class WebSocketDocs(Resource):
    """Resource for WebSocket documentation."""

    @api.doc("get_websocket_docs")
    @api.marshal_with(websocket_docs_model)
    def get(self) -> dict[str, any]:
        """Get documentation for WebSocket events and rooms."""
        # Document all WebSocket events
        events: list[dict[str, any]] = [
            {
                "name": "service_update",
                "description": (
                    "Emitted when a trading service is created, updated, or deleted"
                ),
                "direction": "server-to-client",
                "payload": (
                    '{"action": "created|updated|deleted|toggled", "service": {...}}'
                ),
                "rooms": ["services", "service_{id}"],
            },
            {
                "name": "user_update",
                "description": (
                    "Emitted when a user is created, updated, or has status changed"
                ),
                "direction": "server-to-client",
                "payload": (
                    '{"action": "created|updated|activated|deactivated", "user": {...}}'
                ),
                "rooms": ["users", "user_{id}"],
            },
            {
                "name": "transaction_update",
                "description": ("Emitted when a transaction is created or completed"),
                "direction": "server-to-client",
                "payload": ('{"action": "created|completed", "transaction": {...}}'),
                "rooms": ["transactions"],
            },
            {
                "name": "price_update",
                "description": "Emitted when new price data is available",
                "direction": "server-to-client",
                "payload": (
                    '{"type": "daily|intraday", '
                    '"stock_symbol": "...", '
                    '"stock_id": 1, ...}'
                ),
                "rooms": ["price_updates"],
            },
            {
                "name": "test",
                "description": "Test event for verifying WebSocket connectivity",
                "direction": "server-to-client",
                "payload": (
                    '{"message": "...", "type": "test_event", "timestamp": "..."}'
                ),
                "rooms": ["test"],
            },
            {
                "name": "data_feed",
                "description": "Consolidated data feed for multiple event types",
                "direction": "server-to-client",
                "payload": ('{"type": "price_update|stock_update", "data": {...}}'),
                "rooms": ["data_feeds"],
            },
            {
                "name": "error",
                "description": "Emitted when an error occurs during event processing",
                "direction": "server-to-client",
                "payload": (
                    '{"error": true, "code": 400, "message": "...", '
                    '"timestamp": "...", "details": {...}}'
                ),
                "rooms": ["errors"],
            },
            {
                "name": "join_room",
                "description": "Event to join a specific room",
                "direction": "client-to-server",
                "payload": '{"room": "room_name"}',
                "rooms": [],
            },
            {
                "name": "leave_room",
                "description": "Event to leave a specific room",
                "direction": "client-to-server",
                "payload": '{"room": "room_name"}',
                "rooms": [],
            },
        ]

        # Document all rooms
        rooms: list[dict[str, any]] = [
            {
                "name": "service_{id}",
                "description": "Room for updates about a specific trading service",
                "subscribe_event": "join_service",
                "events": ["service_update"],
            },
            {
                "name": "services",
                "description": "Room for updates about all trading services",
                "subscribe_event": "join_services",
                "events": ["service_update"],
            },
            {
                "name": "user_{id}",
                "description": "Room for updates about a specific user",
                "subscribe_event": "join_user",
                "events": ["user_update"],
            },
            {
                "name": "users",
                "description": "Room for updates about all users (admin only)",
                "subscribe_event": "join_users",
                "events": ["user_update"],
            },
            {
                "name": "transactions",
                "description": "Room for transaction updates",
                "subscribe_event": "join_transactions",
                "events": ["transaction_update"],
            },
            {
                "name": "price_updates",
                "description": "Room for stock price updates",
                "subscribe_event": "join_price_updates",
                "events": ["price_update"],
            },
            {
                "name": "test",
                "description": "Room for testing WebSocket connectivity",
                "subscribe_event": "join_test",
                "events": ["test"],
            },
            {
                "name": "data_feeds",
                "description": "Room for consolidated data feeds",
                "subscribe_event": "join_data_feeds",
                "events": ["data_feed"],
            },
            {
                "name": "errors",
                "description": "Room for error notifications",
                "subscribe_event": "join_errors",
                "events": ["error"],
            },
        ]

        return {
            "events": events,
            "rooms": rooms,
        }
