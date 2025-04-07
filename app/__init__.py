"""Day Trader V1 Application.

This module provides the entry point for the Day Trader V1 application.
"""

from __future__ import annotations

from flask import Flask

from app.api import api_bp, init_websockets
from app.utils.auth import load_user_from_request


def create_app(config: object | None = None) -> Flask:
    """Create and configure the Flask application.

    Args:
        config: The configuration object to use

    Returns:
        The configured Flask application

    """
    app = Flask(__name__)

    # Set some basic default config values
    app.config.update(
        SECRET_KEY="dev-key-for-development-only",  # noqa: S106
        TESTING=False,
        DEBUG=True,
    )

    # Override with provided config if any
    if config:
        app.config.from_object(config)

    # Register API blueprint
    app.register_blueprint(api_bp)

    # Initialize websockets
    init_websockets(app)

    # Register before_request handler to load the current user
    app.before_request(load_user_from_request)

    return app
