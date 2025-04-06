"""Test utilities for the Day Trader application.

This module contains helper functions for testing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from requests import Response

    from app.models import Stock, User

from app.services.session_manager import SessionManager
from app.services.stock_service import StockService
from app.services.user_service import UserService


def create_test_user(admin: bool = False) -> User:
    """Create a test user for authentication.

    Args:
        admin: Whether the user should have admin privileges

    Returns:
        The created user

    """
    with SessionManager() as session:
        # Create a test user
        user_data: dict[str, object] = {
            "username": "testuser" if not admin else "testadmin",
            "email": "test@example.com" if not admin else "admin@example.com",
            "password": "TestPassword123!",
            "is_admin": admin,
        }

        # Check if user already exists
        existing_user: User | None = UserService.find_by_username(
            session,
            user_data["username"],
        )
        if existing_user:
            # Make sure admin privileges are set correctly
            if admin and not existing_user.is_admin:
                existing_user.is_admin = True
                session.commit()
                session.refresh(existing_user)

            # Access the username attribute to ensure it's loaded before session closes
            username: str = existing_user.username
            email: str = existing_user.email
            return existing_user

        # Create the user
        user: User = UserService.create_user(session, user_data)

        # Double-check admin privileges were set correctly
        if admin and not user.is_admin:
            user.is_admin = True
            session.commit()
            session.refresh(user)

        # Access the username attribute to ensure it's loaded before session closes
        username: str = user.username
        email: str = user.email
        return user


def get_auth_token(client: FlaskClient, *, admin: bool = False) -> str:
    """Get an authentication token for API requests.

    Args:
        client: The Flask test client
        admin: Whether to get a token for an admin user

    Returns:
        The JWT token

    """
    # Create the user if it doesn't exist
    try:
        create_test_user(admin)
    except Exception as e:
        print(f"Error creating test user: {e}")
        raise

    # Use fixed values instead of accessing User attributes
    username = "testadmin" if admin else "testuser"
    password = "TestPassword123!"

    # Login to get the token
    login_data = {
        "username": username,
        "password": password,
    }

    # Debug info
    print(f"Attempting login with username={username}, password={password}")

    response = client.post(
        "/api/v1/auth/login",
        json=login_data,
        headers={"Content-Type": "application/json"},
    )

    print(f"Login response status: {response.status_code}")
    print(f"Login response data: {response.data}")

    if response.status_code == 200:
        data = response.get_json()
        if data and "access_token" in data:
            token = data["access_token"]
            print(f"Successfully obtained token (first 20 chars): {token[:20]}...")
            return token

    print(f"Failed to get auth token. Response data: {response.data}")
    raise RuntimeError(f"Failed to get auth token. Status: {response.status_code}")


def create_test_stock() -> dict[str, object]:
    """Create a test stock for testing.

    Returns:
        The created stock as a dictionary

    """
    # Define test stock data
    stock_data: dict[str, object] = {
        "symbol": "TEST",
        "name": "Test Company",
        "sector": "Technology",
        "description": "A test company for integration tests",
    }

    with SessionManager() as session:
        # Check if stock already exists
        existing_stock: Stock | None = StockService.find_by_symbol(
            session,
            stock_data["symbol"],
        )
        if existing_stock:
            return existing_stock.to_dict()

        # Create the stock
        stock: Stock = StockService.create_stock(session, stock_data)
        return stock.to_dict()


def authenticated_request(
    client: FlaskClient,
    method: str,
    url: str,
    *,
    admin: bool = False,
    **kwargs: object,
) -> Response:
    """Make an authenticated request to the API.

    Args:
        client: The Flask test client
        method: The HTTP method to use
        url: The URL to request
        admin: Whether to use an admin token
        **kwargs: Additional arguments to pass to the request

    Returns:
        The response from the API

    """
    # Get authentication token
    token: str = get_auth_token(client, admin=admin)

    # Add token to headers
    headers: dict[str, str] = kwargs.pop("headers", {})

    # Ensure the Authorization header is set correctly
    headers["Authorization"] = f"Bearer {token}"

    # Make sure Content-Type is set for POST and PUT requests
    if method.lower() in ("post", "put") and "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"

    # Add follow_redirects if not already specified
    if "follow_redirects" not in kwargs:
        kwargs["follow_redirects"] = True

    # Make the request with Flask testing client
    request_method: Callable = getattr(client, method.lower())
    response = request_method(url, headers=headers, **kwargs)

    # Debug output for auth problems
    if response.status_code in (401, 403):
        print(f"AUTH PROBLEM: Status {response.status_code}, Token: {token[:20]}...")
        print(f"Headers sent: {headers}")
        print(f"Response data: {response.data}")

    return response
