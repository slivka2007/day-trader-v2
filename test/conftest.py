"""Test configuration for the Day Trader application.

This module contains pytest fixtures for setting up the Flask app and test client.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from collections.abc import Generator

    from flask import Flask


import pytest
from flask_jwt_extended import JWTManager

from app import create_app
from app.services.session_manager import SessionManager

# Set up logger
logger: logging.Logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def app() -> Flask:
    """Create and configure a Flask app for testing."""

    # Create the Flask app using our create_app function
    class TestConfig:
        TESTING: bool = True
        SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"
        JWT_SECRET_KEY: str = "test-secret-key"  # noqa: S105
        JWT_TOKEN_LOCATION: ClassVar[list[str]] = ["headers"]
        JWT_HEADER_NAME: str = "Authorization"
        JWT_HEADER_TYPE: str = "Bearer"
        JWT_ACCESS_TOKEN_EXPIRES: bool = False  # Don't expire during tests
        SERVER_NAME: str = "localhost"  # Set server name for URL generation
        PREFERRED_URL_SCHEME: str = "http"
        HTTP_REDIRECT_WITH_GET: bool = False  # Prevent redirects changing POST to GET

    # Create app with test configuration
    test_app: Flask = create_app(TestConfig)

    logger.info("Setting up test Flask app")

    # Initialize JWT Manager
    try:
        jwt: JWTManager = JWTManager(test_app)
        logger.info("JWT Manager initialized: %s", jwt)
    except (RuntimeError, ValueError, ImportError):
        logger.exception("Error initializing JWT")

    # Mock the SocketIO implementation to prevent errors during tests
    test_app.socketio = MagicMock()
    test_app.socketio.emit = MagicMock()
    logger.info("Mocked SocketIO initialized")

    # Create all tables in the database
    with test_app.app_context():
        # Initialize database
        from app.services.database import init_db

        logger.info("Initializing database...")
        init_db()
        logger.info("Database initialized")

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
