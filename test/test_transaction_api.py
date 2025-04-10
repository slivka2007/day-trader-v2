"""Integration tests for the Trading Transaction API.

This module contains integration tests for the Trading Transaction API endpoints.
"""

# ruff: noqa: S101  # Allow assert usage in tests

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flask.testing import FlaskClient

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from requests import Response

from app.models.enums import ServiceState, TransactionState
from app.utils.constants import ApiConstants
from test.utils import authenticated_request, create_test_stock

# Constants
FLOAT_COMPARISON_TOLERANCE: float = 0.01  # Tolerance for floating point comparisons


class TestTransactionAPI:
    """Integration tests for the Trading Transaction API."""

    @pytest.fixture(autouse=True)
    def setup(self, client: FlaskClient, **_kwargs: object) -> None:
        """Set up test data."""
        self.client: FlaskClient = client
        self.base_url: str = "/api/v1/transactions"
        self.test_stock: dict[str, object] = create_test_stock()

        # Create test trading service
        new_service_data: dict[str, object] = {
            "name": "Transaction Test Service",
            "stock_symbol": self.test_stock["symbol"],
            "description": "Service for transaction testing",
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
            "/api/v1/services",
            admin=False,
            json=new_service_data,
        )

        self.test_service: dict[str, object] = response.get_json()

        # Activate the service
        response: Response = authenticated_request(
            self.client,
            "put",
            f"/api/v1/services/{self.test_service['id']}/state",
            admin=False,
            json={"state": ServiceState.ACTIVE.value},
        )

        # Create a test transaction (buy)
        new_transaction_data: dict[str, object] = {
            "service_id": self.test_service["id"],
            "stock_symbol": self.test_stock["symbol"],
            "shares": 10.0,
            "purchase_price": 100.0,
        }

        # Create the transaction with authentication
        response: Response = authenticated_request(
            self.client,
            "post",
            self.base_url,
            admin=False,
            json=new_transaction_data,
        )

        self.test_transaction: dict[str, object] = response.get_json()

    def test_get_transactions(self) -> None:
        """Test getting a list of transactions."""
        # Make request to get transactions
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

    def test_get_transaction_by_id(self) -> None:
        """Test getting a transaction by ID."""
        # Make request to get transaction by ID
        response: Response = authenticated_request(
            self.client,
            "get",
            f"{self.base_url}/{self.test_transaction['id']}",
            admin=False,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert data["id"] == self.test_transaction["id"]
        assert data["service_id"] == self.test_transaction["service_id"]
        assert data["stock_symbol"] == self.test_transaction["stock_symbol"]
        assert data["shares"] == self.test_transaction["shares"]
        assert data["purchase_price"] == self.test_transaction["purchase_price"]
        assert data["state"] == TransactionState.OPEN.value

    def test_get_transactions_by_service(self) -> None:
        """Test getting transactions for a specific service."""
        # Make request to get transactions for the test service
        response: Response = authenticated_request(
            self.client,
            "get",
            f"{self.base_url}/services/{self.test_service['id']}",
            admin=False,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert "items" in data
        assert "pagination" in data
        assert len(data["items"]) > 0

        # Check if our test transaction is in the results
        transaction_found = False
        for transaction in data["items"]:
            if transaction["id"] == self.test_transaction["id"]:
                transaction_found = True
                break
        assert transaction_found is True

    def test_create_transaction_unauthorized(self) -> None:
        """Test creating a transaction without authentication."""
        # Prepare test data
        new_transaction_data: dict[str, object] = {
            "service_id": self.test_service["id"],
            "stock_symbol": self.test_stock["symbol"],
            "shares": 5.0,
            "purchase_price": 110.0,
        }

        # Make request to create transaction without authentication
        response: Response = self.client.post(
            self.base_url,
            json=new_transaction_data,
            follow_redirects=True,
        )

        # Verify response indicates unauthorized
        assert response.status_code == ApiConstants.HTTP_UNAUTHORIZED

    def test_complete_transaction(self) -> None:
        """Test completing (selling) a transaction."""
        # Prepare complete (sell) data
        complete_data: dict[str, object] = {
            "sale_price": 120.0,
        }

        # Make request to complete transaction with authentication
        response: Response = authenticated_request(
            self.client,
            "post",
            f"{self.base_url}/{self.test_transaction['id']}/complete",
            admin=False,
            json=complete_data,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert data["id"] == self.test_transaction["id"]
        assert data["state"] == TransactionState.CLOSED.value
        assert data["sale_price"] == complete_data["sale_price"]
        assert "sale_date" in data
        assert data["sale_date"] is not None

        # Check profit calculation
        expected_profit: float = (data["sale_price"] - data["purchase_price"]) * data[
            "shares"
        ]
        assert (
            abs(data["gain_loss"] - expected_profit) < FLOAT_COMPARISON_TOLERANCE
        )  # Allow for small floating point differences

    def test_create_transaction_authorized(self) -> None:
        """Test creating a transaction with authentication."""
        # Prepare test data
        new_transaction_data: dict[str, object] = {
            "service_id": self.test_service["id"],
            "stock_symbol": self.test_stock["symbol"],
            "shares": 5.0,
            "purchase_price": 110.0,
        }

        # Make request to create transaction with authentication
        response: Response = authenticated_request(
            self.client,
            "post",
            self.base_url,
            admin=False,
            json=new_transaction_data,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_CREATED
        assert data["service_id"] == new_transaction_data["service_id"]
        assert data["stock_symbol"] == new_transaction_data["stock_symbol"]
        assert data["shares"] == new_transaction_data["shares"]
        assert data["purchase_price"] == new_transaction_data["purchase_price"]
        assert data["state"] == TransactionState.OPEN.value

    def test_cancel_transaction(self) -> None:
        """Test cancelling a transaction."""
        # First create a new transaction to cancel
        new_transaction_data: dict[str, object] = {
            "service_id": self.test_service["id"],
            "stock_symbol": self.test_stock["symbol"],
            "shares": 3.0,
            "purchase_price": 105.0,
        }

        response: Response = authenticated_request(
            self.client,
            "post",
            self.base_url,
            admin=False,
            json=new_transaction_data,
        )
        new_transaction: dict[str, object] = response.get_json()

        # Prepare cancel data
        cancel_data: dict[str, object] = {
            "reason": "Test cancellation",
        }

        # Make request to cancel transaction with authentication
        response: Response = authenticated_request(
            self.client,
            "post",
            f"{self.base_url}/{new_transaction['id']}/cancel",
            admin=False,
            json=cancel_data,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert data["id"] == new_transaction["id"]
        assert data["state"] == TransactionState.CANCELLED.value
        assert cancel_data["reason"] in data["notes"]

    def test_update_transaction_notes(self) -> None:
        """Test updating transaction notes."""
        # Prepare notes data
        notes_data: dict[str, object] = {
            "notes": "These are test notes for the transaction",
        }

        # Make request to update notes with authentication
        response: Response = authenticated_request(
            self.client,
            "put",
            f"{self.base_url}/{self.test_transaction['id']}/notes",
            admin=False,
            json=notes_data,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert data["id"] == self.test_transaction["id"]
        assert data["notes"] == notes_data["notes"]

    def test_get_transaction_metrics(self) -> None:
        """Test getting transaction metrics for a service."""
        # Make request to get transaction metrics
        response: Response = authenticated_request(
            self.client,
            "get",
            f"{self.base_url}/services/{self.test_service['id']}/metrics",
            admin=False,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert "total_transactions" in data
        assert "open_transactions" in data
        assert "closed_transactions" in data
        assert "cancelled_transactions" in data
        assert "win_rate" in data

    def test_delete_transaction_unauthorized(self) -> None:
        """Test deleting a transaction without authentication."""
        # First create a transaction to delete
        new_transaction_data: dict[str, object] = {
            "service_id": self.test_service["id"],
            "stock_symbol": self.test_stock["symbol"],
            "shares": 2.0,
            "purchase_price": 115.0,
        }

        response: Response = authenticated_request(
            self.client,
            "post",
            self.base_url,
            admin=False,
            json=new_transaction_data,
        )
        transaction_to_delete: dict[str, object] = response.get_json()

        # Complete the transaction so it can be deleted
        complete_data: dict[str, object] = {
            "sale_price": 120.0,
        }
        authenticated_request(
            self.client,
            "post",
            f"{self.base_url}/{transaction_to_delete['id']}/complete",
            admin=False,
            json=complete_data,
        )

        # Make request to delete transaction without authentication
        response: Response = self.client.delete(
            f"{self.base_url}/{transaction_to_delete['id']}",
            follow_redirects=True,
        )

        # Verify response indicates unauthorized
        assert response.status_code == ApiConstants.HTTP_UNAUTHORIZED

    def test_delete_transaction_authorized(self) -> None:
        """Test deleting a transaction with authentication."""
        # First create a transaction to delete
        new_transaction_data: dict[str, object] = {
            "service_id": self.test_service["id"],
            "stock_symbol": self.test_stock["symbol"],
            "shares": 2.0,
            "purchase_price": 115.0,
        }

        response: Response = authenticated_request(
            self.client,
            "post",
            self.base_url,
            admin=False,
            json=new_transaction_data,
        )
        transaction_to_delete: dict[str, object] = response.get_json()

        # Complete the transaction so it can be deleted
        complete_data: dict[str, object] = {
            "sale_price": 120.0,
        }
        authenticated_request(
            self.client,
            "post",
            f"{self.base_url}/{transaction_to_delete['id']}/complete",
            admin=False,
            json=complete_data,
        )

        # Make request to delete transaction with authentication
        response: Response = authenticated_request(
            self.client,
            "delete",
            f"{self.base_url}/{transaction_to_delete['id']}",
            admin=False,
        )

        # Verify response
        assert response.status_code == ApiConstants.HTTP_NO_CONTENT

        # Verify transaction is gone
        response: Response = authenticated_request(
            self.client,
            "get",
            self.base_url,
            admin=False,
        )
        assert response.status_code == ApiConstants.HTTP_OK
        transactions_data: dict[str, object] = response.get_json()

        # Check that the deleted transaction is not in the returned list
        transaction_ids: list[int] = [
            transaction["id"] for transaction in transactions_data["items"]
        ]
        assert transaction_to_delete["id"] not in transaction_ids
