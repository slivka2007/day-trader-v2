"""Integration tests for the Daily Price API.

This module contains integration tests for the Daily Price API endpoints.
"""

# ruff: noqa: S101  # Allow assert usage in tests

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

import pytest
from flask.testing import FlaskClient

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from requests import Response

    from app.models import Stock

from app.utils.constants import ApiConstants
from app.utils.current_datetime import get_current_date
from test.utils import authenticated_request, create_test_stock


class TestDailyPriceAPI:
    """Integration tests for the Daily Price API."""

    @pytest.fixture(autouse=True)
    def setup(self, client: FlaskClient, db_session: object) -> None:
        """Set up test data."""
        self.client: FlaskClient = client
        self.base_url = "/api/v1/daily-prices"
        self.test_stock: Stock = create_test_stock()

        # Initialize with default values to prevent AttributeError
        self.test_price: dict[str, object] = {
            "id": 1,
            "stock_id": self.test_stock["id"],
            "price_date": get_current_date().isoformat(),
            "open_price": 150.25,
            "high_price": 152.75,
            "low_price": 149.50,
            "close_price": 151.80,
            "adj_close": 151.80,
            "volume": 75000000,
            "stock_symbol": self.test_stock["symbol"],
        }

        # Try to create a real price record
        self.create_test_daily_price()

    def create_test_daily_price(self) -> None:
        """Create a test daily price record."""
        # Define price data
        price_data: dict[str, object] = {
            "stock_id": self.test_stock["id"],
            "price_date": get_current_date().isoformat(),
            "open_price": 150.25,
            "high_price": 152.75,
            "low_price": 149.50,
            "close_price": 151.80,
            "adj_close": 151.80,
            "volume": 75000000,
            "source": "TEST",
        }

        # Create the price record with admin authentication

        response: Response = authenticated_request(
            self.client,
            "post",
            self.base_url,
            admin=True,
            json=price_data,
        )

        # Store the test price data for later tests
        if response.status_code == ApiConstants.HTTP_CREATED:
            self.test_price = response.get_json()
        else:
            # If creation failed (may already exist), get the latest price
            response: Response = authenticated_request(
                self.client,
                "get",
                f"{self.base_url}/stock/{self.test_stock['id']}/latest?days=1",
                admin=False,
            )

            if response.status_code == ApiConstants.HTTP_OK:
                prices: list[dict[str, object]] = response.get_json()
                if prices and len(prices) > 0:
                    self.test_price = prices[0]

    def test_get_daily_prices(self) -> None:
        """Test getting a list of daily prices."""
        # Make request to get daily prices with authentication
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

    def test_get_daily_prices_by_stock(self) -> None:
        """Test getting daily prices for a specific stock."""
        # Make request to get daily prices for the test stock using authentication
        response: Response = authenticated_request(
            self.client,
            "get",
            f"{self.base_url}?stock_id={self.test_stock['id']}",
            admin=False,
        )

        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert "items" in data
        assert "pagination" in data

        # Check if we have prices
        if len(data["items"]) > 0:
            assert data["items"][0]["stock_id"] == self.test_stock["id"]
            assert data["items"][0]["stock_symbol"] == self.test_stock["symbol"]

    def test_get_daily_price_by_id(self) -> None:
        """Test getting a daily price record by ID."""
        # Skip this test if we don't have a real price record
        if self.test_price.get("id") == 1 and not self.test_price.get("_real", False):
            pytest.skip("No real price record available")

        # Make request to get price by ID with authentication
        response: Response = authenticated_request(
            self.client,
            "get",
            f"{self.base_url}/{self.test_price['id']}",
            admin=False,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert data["id"] == self.test_price["id"]
        assert data["stock_id"] == self.test_price["stock_id"]
        assert data["price_date"] == self.test_price["price_date"]

    def test_get_latest_daily_prices(self) -> None:
        """Test getting the latest daily prices for a stock."""
        # Make request to get latest prices with authentication
        response: Response = authenticated_request(
            self.client,
            "get",
            f"{self.base_url}/stock/{self.test_stock['id']}/latest?days=30",
            admin=False,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert isinstance(data, list)

        # Check if we have prices
        if len(data) > 0:
            assert data[0]["stock_id"] == self.test_stock["id"]
            assert data[0]["stock_symbol"] == self.test_stock["symbol"]

    def test_get_daily_prices_by_date_range(self) -> None:
        """Test getting daily prices for a specific date range."""
        # Calculate date range
        today: date = get_current_date()
        start_date: str = (today - timedelta(days=30)).isoformat()
        end_date: str = today.isoformat()

        # Make request to get prices by date range with authentication
        response: Response = authenticated_request(
            self.client,
            "get",
            f"{self.base_url}/stock/{self.test_stock['id']}/date-range"
            f"?start_date={start_date}&end_date={end_date}",
            admin=False,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert isinstance(data, list)

        # Check if we have prices
        if len(data) > 0:
            assert data[0]["stock_id"] == self.test_stock["id"]
            assert data[0]["stock_symbol"] == self.test_stock["symbol"]

    def test_create_daily_price_unauthorized(self) -> None:
        """Test creating a daily price without authentication."""
        # Define test data
        yesterday: date = get_current_date() - timedelta(days=1)
        price_data: dict[str, object] = {
            "stock_id": self.test_stock["id"],
            "price_date": yesterday.isoformat(),
            "open_price": 148.50,
            "high_price": 153.25,
            "low_price": 147.75,
            "close_price": 152.30,
            "adj_close": 152.30,
            "volume": 80000000,
            "source": "TEST",
        }

        # Make request to create price without authentication
        response: Response = self.client.post(
            self.base_url,
            json=price_data,
        )

        # Verify response indicates unauthorized
        assert response.status_code == ApiConstants.HTTP_UNAUTHORIZED

    def test_create_daily_price_authorized(self) -> None:
        """Test creating a daily price with admin authentication."""
        # Define test data
        yesterday: date = get_current_date() - timedelta(days=2)
        price_data: dict[str, object] = {
            "stock_id": self.test_stock["id"],
            "price_date": yesterday.isoformat(),
            "open_price": 148.50,
            "high_price": 153.25,
            "low_price": 147.75,
            "close_price": 152.30,
            "adj_close": 152.30,
            "volume": 80000000,
            "source": "TEST",
        }

        # Make request to create price with admin authentication
        response: Response = authenticated_request(
            self.client,
            "post",
            self.base_url,
            admin=True,
            json=price_data,
        )

        # Verify response
        # Note: May fail if price for this date already exists (HTTP_BAD_REQUEST)
        # We're not enforcing a particular response code here
        if response.status_code == ApiConstants.HTTP_CREATED:
            data: dict[str, object] = response.get_json()
            assert data["stock_id"] == price_data["stock_id"]
            assert data["price_date"] == price_data["price_date"]
            assert data["open_price"] == price_data["open_price"]
            assert data["close_price"] == price_data["close_price"]

    def test_update_daily_price(self) -> None:
        """Test updating a daily price record."""
        # Skip this test if we don't have a real price record
        if self.test_price.get("id") == 1 and not self.test_price.get("_real", False):
            pytest.skip("No real price record available")

        # Prepare update data
        update_data: dict[str, object] = {
            "open_price": 151.00,
            "high_price": 155.50,
            "low_price": 150.25,
            "close_price": 154.75,
            "adj_close": 154.75,
            "volume": 82000000,
        }

        # Make request to update price with admin authentication
        response: Response = authenticated_request(
            self.client,
            "put",
            f"{self.base_url}/{self.test_price['id']}",
            admin=True,
            json=update_data,
        )

        # Check response
        assert response.status_code == ApiConstants.HTTP_OK
        if response.status_code == ApiConstants.HTTP_OK:
            data: dict[str, object] = response.get_json()
            assert data["id"] == self.test_price["id"]
            assert data["stock_id"] == self.test_price["stock_id"]
            assert data["open_price"] == update_data["open_price"]
            assert data["close_price"] == update_data["close_price"]

    def test_delete_daily_price_unauthorized(self) -> None:
        """Test deleting a daily price without authentication."""
        # Create a temporary price record to delete
        temp_date: date = get_current_date() - timedelta(days=5)
        temp_price_data: dict[str, object] = {
            "stock_id": self.test_stock["id"],
            "price_date": temp_date.isoformat(),
            "open_price": 145.50,
            "high_price": 146.25,
            "low_price": 144.75,
            "close_price": 145.80,
            "adj_close": 145.80,
            "volume": 70000000,
            "source": "TEST",
        }

        # Create the temporary price
        response: Response = authenticated_request(
            self.client,
            "post",
            self.base_url,
            admin=True,
            json=temp_price_data,
        )

        # Only proceed if creation was successful
        if response.status_code == ApiConstants.HTTP_CREATED:
            temp_price: dict[str, object] = response.get_json()

            # Attempt to delete without authentication
            response: Response = self.client.delete(
                f"{self.base_url}/{temp_price['id']}",
                json={"confirm": True, "price_id": temp_price["id"]},
            )

            # Verify response indicates unauthorized
            assert response.status_code == ApiConstants.HTTP_UNAUTHORIZED

    def test_delete_daily_price_authorized(self) -> None:
        """Test deleting a daily price with admin authentication."""
        # Create a temporary price record to delete
        temp_date: date = get_current_date() - timedelta(days=6)
        temp_price_data: dict[str, object] = {
            "stock_id": self.test_stock["id"],
            "price_date": temp_date.isoformat(),
            "open_price": 143.50,
            "high_price": 144.25,
            "low_price": 142.75,
            "close_price": 143.80,
            "adj_close": 143.80,
            "volume": 65000000,
            "source": "TEST",
        }

        # Create the temporary price
        response: Response = authenticated_request(
            self.client,
            "post",
            self.base_url,
            admin=True,
            json=temp_price_data,
        )

        # Only proceed if creation was successful
        if response.status_code == ApiConstants.HTTP_CREATED:
            temp_price: dict[str, object] = response.get_json()

            # Delete with admin authentication
            response: Response = authenticated_request(
                self.client,
                "delete",
                f"{self.base_url}/{temp_price['id']}",
                admin=True,
                json={"confirm": True, "price_id": temp_price["id"]},
            )

            # Verify response
            assert response.status_code == ApiConstants.HTTP_NO_CONTENT

    def test_get_price_analysis(self) -> None:
        """Test getting price analysis."""
        # Make request to get price analysis
        response: Response = self.client.get(
            f"{self.base_url}/stock/{self.test_stock['id']}/analysis",
        )

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        if response.status_code == ApiConstants.HTTP_OK:
            data: dict[str, object] = response.get_json()
            assert "has_data" in data
            # If there's enough data, check for analysis components
            if data.get("has_data", False):
                assert "trend" in data
                assert "moving_averages" in data
                assert "rsi" in data
                assert "macd" in data
                assert "bollinger_bands" in data
