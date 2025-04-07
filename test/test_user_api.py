"""Integration tests for the User API.

This module contains integration tests for the User API endpoints.
"""

# ruff: noqa: S101  # Allow assert usage in tests

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from requests import Response

from app.utils.constants import ApiConstants
from test.utils import authenticated_request, create_test_user


class TestUserAPI:
    """Integration tests for the User API."""

    @pytest.fixture(autouse=True)
    def setup(self, client: FlaskClient, **_kwargs: object) -> None:
        """Set up test data."""
        self.client: FlaskClient = client
        self.base_url: str = "/api/v1/users"

        # Create test users and store their IDs
        self.test_user_id: int = create_test_user(admin=False)
        self.test_admin_id: int = create_test_user(admin=True)

    def test_get_users_unauthorized(self) -> None:
        """Test getting a list of users without admin credentials."""
        # Make request to get users with non-admin authentication
        response: Response = authenticated_request(
            self.client,
            "get",
            self.base_url,
            admin=False,
        )

        # Non-admins should get unauthorized when trying to list all users
        assert response.status_code == ApiConstants.HTTP_UNAUTHORIZED

    def test_get_users_authorized(self) -> None:
        """Test getting a list of users with admin credentials."""
        # Make request to get users with admin authentication
        response: Response = authenticated_request(
            self.client,
            "get",
            self.base_url,
            admin=True,
        )

        # Admins should be able to list users
        assert response.status_code == ApiConstants.HTTP_OK

    def test_get_user_by_id_unauthorized(self) -> None:
        """Test getting another user by ID without admin credentials."""
        # Make request to get admin user by non-admin
        response: Response = authenticated_request(
            self.client,
            "get",
            f"{self.base_url}/{self.test_admin_id}",
            admin=False,
        )

        # Verify response indicates unauthorized
        assert response.status_code == ApiConstants.HTTP_UNAUTHORIZED

    def test_get_user_by_id_self(self) -> None:
        """Test getting own user profile by ID."""
        # Make request to get self by non-admin
        response: Response = authenticated_request(
            self.client,
            "get",
            f"{self.base_url}/{self.test_user_id}",
            admin=False,
        )

        # Users should be able to get their own profile
        assert response.status_code == ApiConstants.HTTP_OK

    def test_get_user_by_id_admin(self) -> None:
        """Test getting any user by ID with admin credentials."""
        # Make request to get user by admin
        response: Response = authenticated_request(
            self.client,
            "get",
            f"{self.base_url}/{self.test_user_id}",
            admin=True,
        )

        # Admins should be able to get any user profile
        assert response.status_code == ApiConstants.HTTP_OK

    def test_create_user(self) -> None:
        """Test creating a new user."""
        # Prepare test data
        new_user_data: dict[str, object] = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "NewPassword123!",
            "password_confirm": "NewPassword123!",
            "is_active": True,
            "is_admin": False,
        }

        # Make request to create user
        response: Response = self.client.post(
            self.base_url,
            json=new_user_data,
            follow_redirects=True,
        )

        # Should return CREATED status code
        assert response.status_code == ApiConstants.HTTP_CREATED

    def test_create_user_validation_error(self) -> None:
        """Test creating a user with invalid data."""
        # Prepare invalid test data (password mismatch)
        invalid_user_data: dict[str, object] = {
            "username": "invaliduser",
            "email": "invalid@example.com",
            "password": "Password123!",
            "password_confirm": "DifferentPassword123!",
            "is_active": True,
        }

        # Make request to create user with invalid data
        response: Response = self.client.post(
            self.base_url,
            json=invalid_user_data,
            follow_redirects=True,
        )

        # Should return BAD REQUEST status code
        assert response.status_code == ApiConstants.HTTP_BAD_REQUEST

    def test_update_user_unauthorized(self) -> None:
        """Test updating a user without proper authorization."""
        # Prepare update data
        update_data: dict[str, object] = {
            "email": "updated@example.com",
        }

        # Make request to update admin user by non-admin
        response: Response = authenticated_request(
            self.client,
            "put",
            f"{self.base_url}/{self.test_admin_id}",
            admin=False,
            json=update_data,
        )

        # Verify response indicates unauthorized
        assert response.status_code == ApiConstants.HTTP_UNAUTHORIZED

    def test_update_user_self(self) -> None:
        """Test updating own user profile."""
        # Prepare update data
        update_data: dict[str, object] = {
            "email": "updated_self@example.com",
        }

        # Make request to update self by non-admin
        response: Response = authenticated_request(
            self.client,
            "put",
            f"{self.base_url}/{self.test_user_id}",
            admin=False,
            json=update_data,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert data["id"] == self.test_user_id
        assert data["email"] == update_data["email"]

    def test_update_user_admin(self) -> None:
        """Test updating any user with admin credentials."""
        # Prepare update data
        update_data: dict[str, object] = {
            "email": "admin_updated@example.com",
            "is_active": False,
        }

        # Make request to update user by admin
        response: Response = authenticated_request(
            self.client,
            "put",
            f"{self.base_url}/{self.test_user_id}",
            admin=True,
            json=update_data,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert data["id"] == self.test_user_id
        assert data["email"] == update_data["email"]
        assert data["is_active"] == update_data["is_active"]

        # Reset user to active state for other tests
        authenticated_request(
            self.client,
            "put",
            f"{self.base_url}/{self.test_user_id}",
            admin=True,
            json={"is_active": True},
        )

    def test_delete_user_unauthorized(self) -> None:
        """Test deleting a user without admin credentials."""
        # Create a temporary user to delete
        temp_user_data: dict[str, object] = {
            "username": "tempuser",
            "email": "temp@example.com",
            "password": "TempPassword123!",
            "password_confirm": "TempPassword123!",
        }
        response: Response = self.client.post(
            self.base_url,
            json=temp_user_data,
            follow_redirects=True,
        )
        temp_user: dict[str, object] = response.get_json()

        # Make request to delete user without admin authentication
        response: Response = authenticated_request(
            self.client,
            "delete",
            f"{self.base_url}/{temp_user['id']}",
            admin=False,
            json={"confirm": True, "user_id": temp_user["id"], "password": "wrong"},
        )

        # Verify response indicates unauthorized
        assert response.status_code == ApiConstants.HTTP_UNAUTHORIZED

    def test_delete_user_authorized(self) -> None:
        """Test deleting a user with admin credentials."""
        # Create a temporary user to delete
        temp_user_data: dict[str, object] = {
            "username": "userdelete",
            "email": "delete@example.com",
            "password": "DeletePassword123!",
            "password_confirm": "DeletePassword123!",
        }
        response: Response = self.client.post(
            self.base_url,
            json=temp_user_data,
            follow_redirects=True,
        )
        temp_user: dict[str, object] = response.get_json()

        # Make request to delete user with admin authentication
        response: Response = authenticated_request(
            self.client,
            "delete",
            f"{self.base_url}/{temp_user['id']}",
            admin=True,
            json={
                "confirm": True,
                "user_id": temp_user["id"],
                "password": "TestPassword123!",
            },
        )

        # Verify response
        assert response.status_code == ApiConstants.HTTP_NO_CONTENT

        # Verify user is deleted by trying to get it
        response: Response = authenticated_request(
            self.client,
            "get",
            f"{self.base_url}/{temp_user['id']}",
            admin=True,
        )
        assert response.status_code == ApiConstants.HTTP_NOT_FOUND

    def test_login(self) -> None:
        """Test user login."""
        # Prepare login data
        login_data: dict[str, object] = {
            "username": "testuser",
            "password": "TestPassword123!",
        }

        # Make login request
        response: Response = self.client.post(
            "/api/v1/auth/login",
            json=login_data,
            follow_redirects=True,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_invalid_credentials(self) -> None:
        """Test login with invalid credentials."""
        # Prepare invalid login data
        invalid_login_data: dict[str, object] = {
            "username": "testuser",
            "password": "WrongPassword123!",
        }

        # Make login request with invalid credentials
        response: Response = self.client.post(
            "/api/v1/auth/login",
            json=invalid_login_data,
            follow_redirects=True,
        )

        # Verify response indicates unauthorized
        assert response.status_code == ApiConstants.HTTP_UNAUTHORIZED

    def test_change_password(self) -> None:
        """Test changing password."""
        # Create a temporary user for password change
        temp_user_data: dict[str, object] = {
            "username": "pwuser",
            "email": "pw@example.com",
            "password": "OrigPassword123!",
            "password_confirm": "OrigPassword123!",
        }
        response: Response = self.client.post(
            self.base_url,
            json=temp_user_data,
            follow_redirects=True,
        )

        # Login with this user to get token
        login_data: dict[str, object] = {
            "username": "pwuser",
            "password": "OrigPassword123!",
        }
        response: Response = self.client.post(
            "/api/v1/auth/login",
            json=login_data,
            follow_redirects=True,
        )
        login_data: dict[str, object] = response.get_json()
        token: str = login_data["access_token"]

        # Prepare password change data
        password_change_data: dict[str, object] = {
            "current_password": "OrigPassword123!",
            "new_password": "NewPassword456!",
            "confirm_password": "NewPassword456!",
        }

        # Make password change request
        headers: dict[str, str] = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        response: Response = self.client.post(
            f"{self.base_url}/change-password",
            json=password_change_data,
            headers=headers,
            follow_redirects=True,
        )

        # Verify password change success
        assert response.status_code == ApiConstants.HTTP_OK

        # Verify we can login with the new password
        login_data: dict[str, object] = {
            "username": "pwuser",
            "password": "NewPassword456!",
        }
        response: Response = self.client.post(
            f"{self.base_url}/login",
            json=login_data,
            follow_redirects=True,
        )
        # Should succeed with new password
        assert response.status_code == ApiConstants.HTTP_OK

    def test_token_refresh(self) -> None:
        """Test refreshing access token."""
        # Login to get tokens
        login_data: dict[str, object] = {
            "username": "testuser",
            "password": "TestPassword123!",
        }
        response: Response = self.client.post(
            "/api/v1/auth/login",
            json=login_data,
            follow_redirects=True,
        )
        tokens: dict[str, object] = response.get_json()
        refresh_token: str = tokens["refresh_token"]

        # Make refresh token request
        headers: dict[str, str] = {
            "Authorization": f"Bearer {refresh_token}",
            "Content-Type": "application/json",
        }
        response: Response = self.client.post(
            f"{self.base_url}/refresh",
            headers=headers,
            follow_redirects=True,
        )
        data: dict[str, object] = response.get_json()

        # Verify response contains a new access token
        assert response.status_code == ApiConstants.HTTP_OK
        assert "access_token" in data

    def test_toggle_user_active_status(self) -> None:
        """Test toggling user active status."""
        # Make request to toggle user active status with admin authentication
        response: Response = authenticated_request(
            self.client,
            "post",
            f"{self.base_url}/{self.test_user_id}/toggle-active",
            admin=True,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert data["id"] == self.test_user_id
        # Status should be toggled to inactive
        assert not data["is_active"]

        # Toggle back to active
        response: Response = authenticated_request(
            self.client,
            "post",
            f"{self.base_url}/{self.test_user_id}/toggle-active",
            admin=True,
        )
        data: dict[str, object] = response.get_json()

        # Verify status was toggled back to active
        assert data["is_active"]

    def test_get_current_user(self) -> None:
        """Test getting current user information."""
        # Make request to get current user
        response: Response = authenticated_request(
            self.client,
            "get",
            f"{self.base_url}/me",
            admin=False,
        )
        data: dict[str, object] = response.get_json()

        # Verify response
        assert response.status_code == ApiConstants.HTTP_OK
        assert data["username"] == "testuser"
        assert not data["is_admin"]

        # Make request to get current admin user
        response: Response = authenticated_request(
            self.client,
            "get",
            f"{self.base_url}/me",
            admin=True,
        )
        data: dict[str, object] = response.get_json()

        # Verify response for admin
        assert response.status_code == ApiConstants.HTTP_OK
        assert data["username"] == "testadmin"
        assert data["is_admin"]
