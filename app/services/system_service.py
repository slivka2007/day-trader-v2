"""System service for managing system-related operations.

This service encapsulates system-level operations like health checks,
system information gathering, and WebSocket testing.
"""

from __future__ import annotations

import logging
import platform
import sys
from typing import cast

from app.services.events import EventService
from app.utils.current_datetime import get_current_datetime

# Set up logging
logger: logging.Logger = logging.getLogger(__name__)


class SystemService:
    """Service for system-related operations."""

    @staticmethod
    def get_system_info() -> dict[str, str]:
        """Get information about the system environment."""
        return {
            "python_version": cast("str", sys.version.split()[0]),
            "platform": platform.platform(),
            "app_name": "Day Trader",
            "environment": "development",  # Should be configurable in a real environment
        }

    @staticmethod
    def get_health_status() -> dict[str, any]:
        """Get the current health status of the system."""
        return {
            "status": "ok",
            "timestamp": get_current_datetime(),
        }

    @staticmethod
    def test_websocket(message: str) -> dict[str, any]:
        """Emit a test WebSocket event and return the result.

        Args:
            message: The test message to emit

        Returns:
            A dictionary containing the test result

        """
        try:
            # Use EventService to emit the test event
            EventService.emit_test(
                message=message,
                room="test",  # Use a dedicated test room
            )

            return {
                "status": "ok",
                "message": "WebSocket test event emitted",
                "timestamp": get_current_datetime(),
            }
        except Exception as e:
            logger.exception("Error emitting test WebSocket event")
            return {
                "status": "error",
                "message": f"Error emitting WebSocket event: {e!s}",
                "timestamp": get_current_datetime(),
            }

    @staticmethod
    def emit_system_notification(
        notification_type: str,
        message: str,
        severity: str = "info",
        details: dict[str, any] | None = None,
    ) -> dict[str, any]:
        """Emit a system notification and return the result.

        Args:
            notification_type: The type of notification (e.g., 'maintenance', 'alert')
            message: The notification message
            severity: The severity level ('info', 'warning', 'error', 'critical')
            details: Optional additional details

        Returns:
            A dictionary containing the notification result

        """
        try:
            # Use EventService to emit the system notification
            EventService.emit_system_notification(
                notification_type=notification_type,
                message=message,
                severity=severity,
                details=details,
            )

            return {
                "status": "ok",
                "message": f"System notification emitted with severity {severity}",
                "timestamp": get_current_datetime(),
            }
        except Exception as e:
            logger.exception("Error emitting system notification")
            return {
                "status": "error",
                "message": f"Error emitting system notification: {e!s}",
                "timestamp": get_current_datetime(),
            }
