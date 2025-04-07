"""Integration tests for the Stock API.

This module contains integration tests for the Stock API endpoints.
"""

# ruff: noqa: S101  # Allow assert usage in tests

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flask.testing import FlaskClient

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from requests import Response


from app.utils.constants import ApiConstants
from test.utils import authenticated_request, create_test_stock


class TestStockAPI:
    """Integration tests for the Stock API."""

    @pytest.fixture(autouse=True)
    def setup(self, client: FlaskClient, **_kwargs: object) -> None:
        """Set up test data."""
        self.client: FlaskClient = client
        self.base_url: str = "/api/v1/stocks"
        self.test_stock: dict[str, object] = create_test_stock()

    def test_get_stocks(self) -> None:
        """Test getting a list of stocks."""
        # Make request to get stocks
        response: Response = authenticated_request(
            self.client,
            "get",
            self.base_url,
            admin=False,
        )

        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert "items" in data
        assert "pagination" in data
        assert len(data["items"]) > 0

    def test_get_stock_by_id(self) -> None:
        """Test getting a stock by ID."""
        # Make request to get stock by ID
        response: Response = self.client.get(
            f"{self.base_url}/{self.test_stock['id']}",
            follow_redirects=True,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert data["id"] == self.test_stock["id"]
        assert data["symbol"] == self.test_stock["symbol"]
        assert data["name"] == self.test_stock["name"]

    def test_get_stock_by_symbol(self) -> None:
        """Test getting a stock by symbol."""
        # Make request to get stock by symbol
        response: Response = self.client.get(
            f"{self.base_url}/symbol/{self.test_stock['symbol']}",
            follow_redirects=True,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert data["id"] == self.test_stock["id"]
        assert data["symbol"] == self.test_stock["symbol"]
        assert data["name"] == self.test_stock["name"]

    def test_search_stocks(self) -> None:
        """Test searching for stocks."""
        # Make request to search for stocks using part of the test stock's name
        response: Response = self.client.get(
            f"{self.base_url}/search?q={self.test_stock['name'][:3]}",
            follow_redirects=True,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert "results" in data
        assert "count" in data
        assert data["count"] > 0
        # Check if our test stock is in the results
        symbol_found = False
        for stock in data["results"]:
            if stock["symbol"] == self.test_stock["symbol"]:
                symbol_found = True
                break
        assert symbol_found is True

    def test_create_stock_unauthorized(self) -> None:
        """Test creating a stock without authentication."""
        # Prepare test data
        new_stock_data: dict[str, object] = {
            "symbol": "GOOG",
            "name": "Alphabet Inc.",
            "is_active": True,
            "sector": "Technology",
            "description": "Test stock for integration testing",
        }

        # Make request to create stock without authentication
        response: Response = self.client.post(
            self.base_url,
            json=new_stock_data,
            follow_redirects=True,
        )

        # Verify response indicates unauthorized
        assert response.status_code == ApiConstants.HTTP_UNAUTHORIZED

    def test_create_stock_authorized(self) -> None:
        """Test creating a stock with admin authentication."""
        # Prepare test data
        new_stock_data: dict[str, object] = {
            "symbol": "MSFT",
            "name": "Microsoft Corporation",
            "is_active": True,
            "sector": "Technology",
            "description": "Test stock for integration testing",
        }

        # Make request to create stock with admin authentication
        response: Response = authenticated_request(
            self.client,
            "post",
            self.base_url,
            admin=True,
            json=new_stock_data,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_CREATED
        assert data["symbol"] == new_stock_data["symbol"]
        assert data["name"] == new_stock_data["name"]
        assert data["is_active"] == new_stock_data["is_active"]

    def test_update_stock(self) -> None:
        """Test updating a stock."""
        # Prepare update data
        update_data: dict[str, object] = {
            "name": "Updated Apple Inc.",
            "description": "Updated test stock description",
        }

        # Make request to update stock with admin authentication
        response: Response = authenticated_request(
            self.client,
            "put",
            f"{self.base_url}/{self.test_stock['id']}",
            admin=True,
            json=update_data,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert data["id"] == self.test_stock["id"]
        assert data["symbol"] == self.test_stock["symbol"]
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]

    def test_toggle_stock_active(self) -> None:
        """Test toggling a stock's active status."""
        # Make request to toggle stock active status with admin authentication
        response: Response = authenticated_request(
            self.client,
            "post",
            f"{self.base_url}/{self.test_stock['id']}/toggle-active",
            admin=True,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert data["id"] == self.test_stock["id"]
        assert data["is_active"] != self.test_stock["is_active"]

        # Toggle back to original state
        authenticated_request(
            self.client,
            "post",
            f"{self.base_url}/{self.test_stock['id']}/toggle-active",
            admin=True,
        )

    def test_delete_stock_unauthorized(self) -> None:
        """Test deleting a stock without authentication."""
        # Create a temporary stock to delete
        temp_stock_data: dict[str, object] = {
            "symbol": "TEMP",
            "name": "Temporary Stock",
            "is_active": True,
        }
        response: Response = authenticated_request(
            self.client,
            "post",
            self.base_url,
            admin=True,
            json=temp_stock_data,
        )

        # Check if the stock was created successfully
        if response.status_code != ApiConstants.HTTP_CREATED:
            pytest.skip("Failed to create test stock for deletion test")

        temp_stock: dict[str, object] = response.get_json()

        # Make sure the ID field exists
        if "id" not in temp_stock:
            pytest.skip("Stock ID not found in response")

        # Make request to delete stock without authentication
        response: Response = self.client.delete(
            f"{self.base_url}/{temp_stock['id']}",
            follow_redirects=True,
        )

        # Verify response indicates unauthorized
        assert response.status_code == ApiConstants.HTTP_UNAUTHORIZED

    def test_delete_stock_authorized(self) -> None:
        """Test deleting a stock with admin authentication."""
        # Create a temporary stock to delete
        temp_stock_data: dict[str, object] = {
            "symbol": "DEL",
            "name": "Stock to Delete",
            "is_active": True,
        }
        response: Response = authenticated_request(
            self.client,
            "post",
            self.base_url,
            admin=True,
            json=temp_stock_data,
        )

        # Check if the stock was created successfully
        if response.status_code != ApiConstants.HTTP_CREATED:
            pytest.skip("Failed to create test stock for deletion test")

        temp_stock: dict[str, object] = response.get_json()

        # Make sure the ID field exists
        if "id" not in temp_stock:
            pytest.skip("Stock ID not found in response")

        # Make request to delete stock with admin authentication
        response: Response = authenticated_request(
            self.client,
            "delete",
            f"{self.base_url}/{temp_stock['id']}",
            admin=True,
        )

        # Verify response
        assert response.status_code in (
            ApiConstants.HTTP_OK,
            ApiConstants.HTTP_NO_CONTENT,
        )
