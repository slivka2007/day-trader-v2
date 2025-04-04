"""REST API package for the Day Trader application.

This package contains all the API resources, models, and schemas for the application.
"""

from __future__ import annotations

from flask import Blueprint, Flask
from flask_restx import Api
from flask_socketio import SocketIO

from app.api.error_handlers import register_error_handlers
from app.api.resources import register_resources
from app.api.sockets import register_handlers

# Create API blueprint
api_bp: Blueprint = Blueprint("api", __name__, url_prefix="/api/v1")

# Initialize Flask-RESTX API
api: Api = Api(
    api_bp,
    version="1.0",
    title="Day Trader API",
    description="RESTful API for the Day Trader application",
    doc="/docs",
    validate=True,
    authorizations={
        "Bearer Auth": {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": "Add a JWT with ** Bearer &lt;JWT&gt; ** to authorize",
        },
    },
    security="Bearer Auth",
)

# Register API resources and error handlers
register_resources(api)
register_error_handlers(api_bp)

# Initialize WebSockets for real-time updates
socketio: SocketIO = SocketIO(cors_allowed_origins="*")


def init_websockets(app: Flask) -> SocketIO:
    """Initialize WebSocket handlers."""
    socketio.init_app(app)
    register_handlers(socketio)
    app.socketio = socketio  # Store reference in app for easy access
    return socketio


__all__: list[str] = [
    "api",
    "api_bp",
    "init_websockets",
    "socketio",
]
