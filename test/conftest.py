"""Test configuration for the Day Trader application.

This module contains pytest fixtures for setting up the Flask app and test client.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator


import pytest
from flask import Flask
from flask_jwt_extended import JWTManager

from app.api import api_bp, init_websockets
from app.services.session_manager import SessionManager


@pytest.fixture(scope="session")
def app() -> Flask:
    """Create and configure a Flask app for testing."""
    # Create the Flask app
    test_app = Flask(__name__)

    # Configure the app for testing
    test_app.config["TESTING"] = True
    test_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    test_app.config["JWT_SECRET_KEY"] = "test-secret-key"  # noqa: S105
    test_app.config["JWT_TOKEN_LOCATION"] = ["headers"]
    test_app.config["JWT_HEADER_NAME"] = "Authorization"
    test_app.config["JWT_HEADER_TYPE"] = "Bearer"
    test_app.config["JWT_ACCESS_TOKEN_EXPIRES"] = False  # Don't expire during tests
    test_app.config["SERVER_NAME"] = "localhost"  # Set server name for URL generation
    test_app.config["PREFERRED_URL_SCHEME"] = "http"
    test_app.config["HTTP_REDIRECT_WITH_GET"] = (
        False  # Prevent redirects changing POST to GET
    )

    print("Setting up test Flask app")

    # Initialize JWT Manager
    try:
        jwt = JWTManager(test_app)
        print(f"JWT Manager initialized: {jwt}")
    except Exception as e:
        print(f"Error initializing JWT: {e}")

    # Register API blueprint
    test_app.register_blueprint(api_bp)

    # Initialize WebSockets
    init_websockets(test_app)

    # Create all tables in the database
    with test_app.app_context():
        # Initialize database
        from app.services.database import init_db

        print("Initializing database...")
        init_db()
        print("Database initialized")

    return test_app


@pytest.fixture
def client(app: Flask) -> Generator[Any, None, None]:
    """Create a test client for the Flask app."""
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def db_session() -> Generator[Any, None, None]:
    """Create a database session for testing."""
    with SessionManager() as session:
        yield session
        # This will automatically commit or rollback based on exceptions
