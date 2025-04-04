"""WebSocket event handlers for the Day Trader application.

This module provides comprehensive event handlers for real-time updates via WebSockets.
It handles connections, room management, and various event subscriptions.
"""

from __future__ import annotations

import functools
import logging
from json import JSONDecodeError
from typing import Callable

from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.exceptions import HTTPException

from app.utils.constants import ApiConstants
from app.utils.current_datetime import get_current_datetime
from app.utils.errors import APIError, ValidationError

logger: logging.Logger = logging.getLogger(__name__)

# Store for active socket connections
active_connections: dict[str, any] = {}


# Standardized error response
def create_error_response(
    message: str,
    code: int = ApiConstants.HTTP_BAD_REQUEST,
    details: dict | None = None,
) -> dict:
    """Create a standardized error response for WebSocket events.

    Args:
        message (str): The error message
        code (int): The error code (similar to HTTP status codes)
        details (dict, optional): Additional error details

    Returns:
        dict: Standardized error response

    """
    response: dict = {
        "error": True,
        "code": code,
        "message": message,
        "timestamp": get_current_datetime().isoformat(),
    }

    if details:
        response["details"] = details

    return response


def socketio_handler(event_name: str) -> Callable:
    """Decorate SocketIO event handlers with error handling and logging.

    Args:
        event_name (str): The name of the event

    Returns:
        Decorated function

    """

    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def wrapped(*args: any, **kwargs: any) -> any:
            logger.debug("Received '%s' event: %s", event_name, args)
            try:
                return f(*args, **kwargs)
            except (ValueError, TypeError, JSONDecodeError) as e:
                logger.exception(
                    "Data validation error in '%s' handler",
                    event_name,
                )
                error_response: dict = create_error_response(
                    message=str(e),
                    code=ApiConstants.HTTP_BAD_REQUEST,
                    details={"event": event_name},
                )
                emit("error", error_response)
            except ValidationError as e:
                logger.exception(
                    "Validation error in '%s' handler",
                    event_name,
                )
                error_response: dict = create_error_response(
                    message=e.message,
                    code=e.status_code,
                    details={"event": event_name, **e.to_dict()},
                )
                emit("error", error_response)
            except HTTPException as e:
                logger.exception(
                    "HTTP error in '%s' handler",
                    event_name,
                )
                error_response: dict = create_error_response(
                    message=str(e),
                    code=e.code,
                    details={"event": event_name},
                )
                emit("error", error_response)
            except APIError as e:
                logger.exception(
                    "API error in '%s' handler",
                    event_name,
                )
                error_response: dict = create_error_response(
                    message=e.message,
                    code=e.status_code,
                    details={"event": event_name, **e.to_dict()},
                )
                emit("error", error_response)
            except RuntimeError as e:
                logger.exception(
                    "Runtime error in '%s' handler",
                    event_name,
                )
                error_response: dict = create_error_response(
                    message=str(e),
                    code=ApiConstants.HTTP_INTERNAL_SERVER_ERROR,
                    details={"event": event_name},
                )
                emit("error", error_response)

        return wrapped

    return decorator


def register_connection_handlers(socketio: SocketIO) -> None:
    """Register connection-related event handlers."""

    @socketio.on("connect")
    @socketio_handler("connect")
    def handle_connect() -> None:
        """Handle client connection."""
        logger.info("Client connected to WebSocket")
        emit("connection_response", {"status": ApiConstants.STATUS_SUCCESS})

    @socketio.on("disconnect")
    @socketio_handler("disconnect")
    def handle_disconnect() -> None:
        """Handle client disconnection."""
        logger.info("Client disconnected from WebSocket")


def register_room_handlers(socketio: SocketIO) -> None:
    """Register room management event handlers."""

    @socketio.on("join")
    @socketio_handler("join")
    def handle_join(data: dict) -> None:
        if not isinstance(data, dict) or "room" not in data:
            emit("error", create_error_response("Invalid join request format"))
            return

        room: str = data["room"]
        logger.info("Client joining room: %s", room)
        join_room(room)
        emit(
            "join_response",
            {"status": ApiConstants.STATUS_SUCCESS, "room": room},
            to=room,
        )

    @socketio.on("leave")
    @socketio_handler("leave")
    def handle_leave(data: dict) -> None:
        if not isinstance(data, dict) or "room" not in data:
            emit("error", create_error_response("Invalid leave request format"))
            return

        room: str = data["room"]
        logger.info("Client leaving room: %s", room)
        leave_room(room)
        emit("leave_response", {"status": ApiConstants.STATUS_SUCCESS, "room": room})


def register_service_handlers(socketio: SocketIO) -> None:
    """Register service-related event handlers."""

    @socketio.on("service_watch")
    @socketio_handler("service_watch")
    def handle_service_watch(data: dict) -> None:
        if not isinstance(data, dict) or "service_id" not in data:
            emit(
                "error",
                create_error_response(
                    "Invalid service watch request",
                    details={"required_fields": ["service_id"]},
                ),
            )
            return

        service_id: str = data["service_id"]
        room: str = f"service_{service_id}"
        logger.info("Client watching service ID: %s", service_id)
        join_room(room)
        emit(
            "watch_response",
            {
                "status": ApiConstants.STATUS_SUCCESS,
                "type": "service",
                "id": service_id,
            },
        )

    @socketio.on("join_services")
    @socketio_handler("join_services")
    def join_services() -> None:
        room: str = "services"
        join_room(room)
        logger.debug("Client joined services room")
        emit("joined", {"room": room}, to=room)


def register_stock_handlers(socketio: SocketIO) -> None:
    """Register stock-related event handlers."""

    @socketio.on("stock_watch")
    @socketio_handler("stock_watch")
    def handle_stock_watch(data: dict) -> None:
        if not isinstance(data, dict) or "symbol" not in data:
            emit(
                "error",
                create_error_response(
                    "Invalid stock watch request",
                    details={"required_fields": ["symbol"]},
                ),
            )
            return

        symbol: str = data["symbol"].upper()
        room: str = f"stock_{symbol}"
        logger.info("Client watching stock: %s", symbol)
        join_room(room)
        emit(
            "watch_response",
            {"status": ApiConstants.STATUS_SUCCESS, "type": "stock", "symbol": symbol},
        )

    @socketio.on("join_price_updates")
    @socketio_handler("join_price_updates")
    def join_price_updates() -> None:
        room: str = "price_updates"
        join_room(room)
        logger.debug("Client joined price updates room")
        emit("joined", {"room": room}, to=room)


def register_user_handlers(socketio: SocketIO) -> None:
    """Register user-related event handlers."""

    @socketio.on("user_watch")
    @socketio_handler("user_watch")
    def handle_user_watch(data: dict) -> None:
        if not isinstance(data, dict) or "user_id" not in data:
            emit(
                "error",
                create_error_response(
                    "Invalid user watch request",
                    details={"required_fields": ["user_id"]},
                ),
            )
            return

        user_id: str = data["user_id"]
        room: str = f"user_{user_id}"
        logger.info("Client watching user ID: %s", user_id)
        join_room(room)
        emit(
            "watch_response",
            {"status": ApiConstants.STATUS_SUCCESS, "type": "user", "id": user_id},
        )

    @socketio.on("join_users")
    @socketio_handler("join_users")
    def join_users() -> None:
        room: str = "users"
        join_room(room)
        logger.debug("Client joined users room")
        emit("joined", {"room": room}, to=room)


def register_system_handlers(socketio: SocketIO) -> None:
    """Register system-related event handlers."""

    @socketio.on("join_system")
    @socketio_handler("join_system")
    def join_system(data: dict | None = None) -> None:
        severity: str | None = None
        if isinstance(data, dict) and "severity" in data:
            severity = data["severity"]
            if severity not in ["info", "warning", "error", "critical"]:
                emit(
                    "error",
                    create_error_response(
                        "Invalid severity level",
                        details={
                            "valid_levels": ["info", "warning", "error", "critical"],
                        },
                    ),
                )
                return

        room: str = "system" if severity is None else f"system_{severity}"
        join_room(room)
        logger.debug("Client joined system notifications room: %s", room)
        emit("joined", {"room": room}, to=room)


def register_handlers(socketio: SocketIO) -> SocketIO:
    """Register all WebSocket event handlers."""
    register_connection_handlers(socketio)
    register_room_handlers(socketio)
    register_service_handlers(socketio)
    register_stock_handlers(socketio)
    register_user_handlers(socketio)
    register_system_handlers(socketio)

    logger.info("WebSocket event handlers registered")
    return socketio
