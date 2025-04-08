"""Integration tests for the Trading Service API.

This module contains integration tests for the Trading Service API endpoints.
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


class TestTradingServiceAPI:
    """Integration tests for the Trading Service API."""

    @pytest.fixture(autouse=True)
    def setup(self, client: FlaskClient, **_kwargs: object) -> None:
        """Set up test data."""
        self.client: FlaskClient = client
        self.base_url: str = "/api/v1/services"
        self.test_stock: dict[str, object] = create_test_stock()

        # Create test trading service
        new_service_data: dict[str, object] = {
            "name": "Test Trading Service",
            "stock_symbol": self.test_stock["symbol"],
            "description": "Test service for integration testing",
            "initial_balance": 10000.0,
            "minimum_balance": 1000.0,
            "allocation_percent": 0.1,
            "buy_threshold": 0.02,
            "sell_threshold": 0.03,
            "stop_loss_percent": 0.05,
            "take_profit_percent": 0.1,
            "is_active": True,
        }

        # Create the service with authentication
        response: Response = authenticated_request(
            self.client,
            "post",
            self.base_url,
            admin=False,
            json=new_service_data,
        )

        self.test_service: dict[str, object] = response.get_json()

    def test_get_services(self) -> None:
        """Test getting a list of trading services."""
        # Make request to get services
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

    def test_get_service_by_id(self) -> None:
        """Test getting a trading service by ID."""
        # Make request to get service by ID
        response: Response = authenticated_request(
            self.client,
            "get",
            f"{self.base_url}/{self.test_service['id']}",
            admin=False,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert data["id"] == self.test_service["id"]
        assert data["name"] == self.test_service["name"]
        assert data["stock_symbol"] == self.test_service["stock_symbol"]

    def test_search_services(self) -> None:
        """Test searching for trading services."""
        # Make request to search for services using part of the test service's name
        response: Response = authenticated_request(
            self.client,
            "get",
            f"{self.base_url}/search?q={self.test_service['name'][:5]}",
            admin=False,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert "items" in data
        assert "pagination" in data
        assert len(data["items"]) > 0

        # Check if our test service is in the results
        service_found = False
        for service in data["items"]:
            if service["id"] == self.test_service["id"]:
                service_found = True
                break
        assert service_found is True

    def test_create_service_unauthorized(self) -> None:
        """Test creating a trading service without authentication."""
        # Prepare test data
        new_service_data: dict[str, object] = {
            "name": "Unauthorized Service",
            "stock_symbol": self.test_stock["symbol"],
            "initial_balance": 10000.0,
        }

        # Make request to create service without authentication
        response: Response = self.client.post(
            self.base_url,
            json=new_service_data,
            follow_redirects=True,
        )

        # Verify response indicates unauthorized
        assert response.status_code == ApiConstants.HTTP_UNAUTHORIZED

    def test_create_service_authorized(self) -> None:
        """Test creating a trading service with authentication."""
        # Prepare test data
        new_service_data: dict[str, object] = {
            "name": "New Test Service",
            "stock_symbol": self.test_stock["symbol"],
            "description": "New test service for integration testing",
            "initial_balance": 20000.0,
            "minimum_balance": 2000.0,
            "allocation_percent": 0.2,
            "buy_threshold": 0.03,
            "sell_threshold": 0.04,
            "stop_loss_percent": 0.06,
            "take_profit_percent": 0.12,
            "is_active": True,
        }

        # Make request to create service with authentication
        response: Response = authenticated_request(
            self.client,
            "post",
            self.base_url,
            admin=False,
            json=new_service_data,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_CREATED
        assert data["name"] == new_service_data["name"]
        assert data["stock_symbol"] == new_service_data["stock_symbol"]
        assert data["initial_balance"] == new_service_data["initial_balance"]

    def test_update_service(self) -> None:
        """Test updating a trading service."""
        # Prepare update data
        update_data: dict[str, object] = {
            "name": "Updated Test Service",
            "description": "Updated test service description",
            "minimum_balance": 1500.0,
        }

        # Make request to update service with authentication
        response: Response = authenticated_request(
            self.client,
            "put",
            f"{self.base_url}/{self.test_service['id']}",
            admin=False,
            json=update_data,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert data["id"] == self.test_service["id"]
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]
        assert data["minimum_balance"] == update_data["minimum_balance"]

    def test_toggle_service_active(self) -> None:
        """Test toggling a trading service's active status."""
        # Make request to toggle service active status
        response: Response = authenticated_request(
            self.client,
            "post",
            f"{self.base_url}/{self.test_service['id']}/toggle",
            admin=False,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert data["id"] == self.test_service["id"]
        assert data["is_active"] != self.test_service["is_active"]

        # Update test_service to reflect the change
        self.test_service["is_active"] = data["is_active"]

        # Toggle back to original state
        authenticated_request(
            self.client,
            "post",
            f"{self.base_url}/{self.test_service['id']}/toggle",
            admin=False,
        )

    def test_change_service_state(self) -> None:
        """Test changing a trading service's state."""
        # Prepare state change data
        state_data: dict[str, object] = {
            "state": "INACTIVE",
        }

        # Make request to change service state
        response: Response = authenticated_request(
            self.client,
            "put",
            f"{self.base_url}/{self.test_service['id']}/state",
            admin=False,
            json=state_data,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert data["id"] == self.test_service["id"]
        assert data["state"] == state_data["state"]

        # Change back to ACTIVE
        authenticated_request(
            self.client,
            "put",
            f"{self.base_url}/{self.test_service['id']}/state",
            admin=False,
            json={"state": "ACTIVE"},
        )

    def test_change_service_mode(self) -> None:
        """Test changing a trading service's mode."""
        # Prepare mode change data
        mode_data: dict[str, object] = {
            "mode": "SELL",
        }

        # Make request to change service mode
        response: Response = authenticated_request(
            self.client,
            "put",
            f"{self.base_url}/{self.test_service['id']}/mode",
            admin=False,
            json=mode_data,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert data["id"] == self.test_service["id"]
        assert data["mode"] == mode_data["mode"]

        # Change back to BUY
        authenticated_request(
            self.client,
            "put",
            f"{self.base_url}/{self.test_service['id']}/mode",
            admin=False,
            json={"mode": "BUY"},
        )

    def test_check_buy_decision(self) -> None:
        """Test checking a buy decision."""
        # Make request to check buy decision
        response: Response = authenticated_request(
            self.client,
            "get",
            f"{self.base_url}/{self.test_service['id']}/check-buy",
            admin=False,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert "should_proceed" in data
        assert "reason" in data
        assert "timestamp" in data
        assert "service_id" in data
        assert data["service_id"] == self.test_service["id"]

    def test_check_sell_decision(self) -> None:
        """Test checking a sell decision."""
        # Make request to check sell decision
        response: Response = authenticated_request(
            self.client,
            "get",
            f"{self.base_url}/{self.test_service['id']}/check-sell",
            admin=False,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert "should_proceed" in data
        assert "reason" in data
        assert "timestamp" in data
        assert "service_id" in data
        assert data["service_id"] == self.test_service["id"]

    def test_delete_service_unauthorized(self) -> None:
        """Test deleting a trading service without authentication."""
        # Create a temporary service to delete
        temp_service_data: dict[str, object] = {
            "name": "Temporary Service",
            "stock_symbol": self.test_stock["symbol"],
            "initial_balance": 5000.0,
        }

        # Create the service with authentication
        response: Response = authenticated_request(
            self.client,
            "post",
            self.base_url,
            admin=False,
            json=temp_service_data,
        )

        # Check if the service was created successfully
        if response.status_code != ApiConstants.HTTP_CREATED:
            pytest.skip("Failed to create test service for deletion test")

        temp_service: dict[str, object] = response.get_json()

        # Make sure the ID field exists
        if "id" not in temp_service:
            pytest.skip("Service ID not found in response")

        # Make request to delete service without authentication
        response: Response = self.client.delete(
            f"{self.base_url}/{temp_service['id']}",
            follow_redirects=True,
        )

        # Verify response indicates unauthorized
        assert response.status_code == ApiConstants.HTTP_UNAUTHORIZED

    def test_delete_service_authorized(self) -> None:
        """Test deleting a trading service with authentication."""
        # Create a temporary service to delete
        temp_service_data: dict[str, object] = {
            "name": "Service to Delete",
            "stock_symbol": self.test_stock["symbol"],
            "initial_balance": 5000.0,
        }

        # Create the service with authentication
        response: Response = authenticated_request(
            self.client,
            "post",
            self.base_url,
            admin=False,
            json=temp_service_data,
        )

        # Check if the service was created successfully
        if response.status_code != ApiConstants.HTTP_CREATED:
            pytest.skip("Failed to create test service for deletion test")

        temp_service: dict[str, object] = response.get_json()
        service_id: int = temp_service["id"]

        # Make request to delete service with authentication
        response: Response = authenticated_request(
            self.client,
            "delete",
            f"{self.base_url}/{service_id}",
            admin=False,
        )

        # Verify response
        assert response.status_code == ApiConstants.HTTP_NO_CONTENT

        # Verify the service was deleted by checking the service list
        response: Response = authenticated_request(
            self.client,
            "get",
            self.base_url,
            admin=False,
        )

        assert response.status_code == ApiConstants.HTTP_OK
        services_data: dict[str, object] = response.get_json()

        # Check that the deleted service is not in the returned list
        service_ids: list[int] = [service["id"] for service in services_data["items"]]
        assert service_id not in service_ids
