"""
User API resources.
"""

import logging
from typing import Literal

from flask import g, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)
from flask_restx import Model, Namespace, Resource, fields

from app.api.schemas.user import (
    password_change_schema,
    user_create_schema,
    user_delete_schema,
    user_login_schema,
    user_schema,
    user_update_schema,
    users_schema,
)
from app.models import User
from app.services.session_manager import SessionManager
from app.services.user_service import UserService
from app.utils.auth import admin_required
from app.utils.errors import (
    AuthorizationError,
    BusinessLogicError,
    ResourceNotFoundError,
    ValidationError,
)

# Set up logging
logger: logging.Logger = logging.getLogger(__name__)

# Create namespace
ns: Namespace = Namespace("users", description="User operations")

# API models for Swagger documentation
user_model: Model = ns.model(
    "User",
    {
        "id": fields.Integer(readonly=True, description="User identifier"),
        "username": fields.String(required=True, description="User unique name"),
        "email": fields.String(required=True, description="User email address"),
        "is_active": fields.Boolean(description="Is user account active"),
        "is_admin": fields.Boolean(description="Is user an administrator"),
        "has_services": fields.Boolean(description="Whether user has trading services"),
        "service_count": fields.Integer(description="Number of trading services"),
        "last_login": fields.DateTime(description="Last login timestamp"),
        "last_login_days_ago": fields.Integer(description="Days since last login"),
        "created_at": fields.DateTime(description="Creation timestamp"),
        "updated_at": fields.DateTime(description="Last update timestamp"),
    },
)

user_create_model: Model = ns.model(
    "UserCreate",
    {
        "username": fields.String(
            required=True, description="Unique username (letters, numbers, underscores)"
        ),
        "email": fields.String(required=True, description="Unique email address"),
        "password": fields.String(
            required=True,
            description="Password (min 8 chars with number, upper, lower, special)",
        ),
        "password_confirm": fields.String(
            required=True, description="Confirm password"
        ),
        "is_active": fields.Boolean(description="Is user account active"),
        "is_admin": fields.Boolean(description="Is user an administrator"),
    },
)

user_update_model: Model = ns.model(
    "UserUpdate",
    {
        "username": fields.String(
            description="Unique username (letters, numbers, underscores)"
        ),
        "email": fields.String(description="Unique email address"),
        "password": fields.String(
            description="Password (min 8 chars with number, upper, lower, special)"
        ),
        "password_confirm": fields.String(description="Confirm password"),
        "is_active": fields.Boolean(description="Is user account active"),
        "is_admin": fields.Boolean(description="Is user an administrator"),
    },
)

user_delete_model: Model = ns.model(
    "UserDelete",
    {
        "confirm": fields.Boolean(required=True, description="Confirmation flag"),
        "user_id": fields.Integer(required=True, description="User ID to delete"),
        "password": fields.String(
            required=True, description="Admin password for verification"
        ),
    },
)

login_model: Model = ns.model(
    "Login",
    {
        "username": fields.String(required=True, description="Username"),
        "password": fields.String(required=True, description="Password"),
    },
)

token_model: Model = ns.model(
    "Token",
    {
        "access_token": fields.String(description="JWT access token"),
        "refresh_token": fields.String(description="JWT refresh token"),
    },
)

password_change_model: Model = ns.model(
    "PasswordChange",
    {
        "current_password": fields.String(
            required=True, description="Current password"
        ),
        "new_password": fields.String(
            required=True,
            description="New password (min 8 chars with number, upper, lower, special)",
        ),
        "confirm_password": fields.String(
            required=True, description="Confirm new password"
        ),
    },
)


# User list resource
@ns.route("/")
class UserList(Resource):
    """Shows a list of all users and creates new users."""

    @jwt_required()
    @admin_required
    @ns.doc("list_users")
    @ns.response(200, "Success", [user_model])
    def get(self) -> any | list[any] | list | dict:
        """Get all users."""
        try:
            with SessionManager() as session:
                users: list[User] = UserService.get_all(session)
                return users_schema.dump(users)
        except Exception as e:
            logger.error(f"Error listing users: {str(e)}")
            raise BusinessLogicError(f"Error retrieving users: {str(e)}") from e

    @ns.doc("create_user")
    @ns.expect(user_create_model)
    @ns.response(201, "User created", user_model)
    @ns.response(400, "Validation error")
    def post(self) -> tuple[any | list[any] | list | dict, Literal[201]]:
        """Create a new user."""
        try:
            data: dict[str, any] = request.json or {}
            # Validate input with schema
            errors: list[str] = user_create_schema.validate(data)
            if errors:
                raise ValidationError(f"Invalid input data: {errors}")

            with SessionManager() as session:
                # Use the user service to create user
                created_user: User = UserService.create_user(session, data)
                return user_schema.dump(created_user), 201

        except ValidationError as e:
            logger.warning(f"Validation error creating user: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            raise BusinessLogicError(f"Could not create user: {str(e)}") from e


# User detail resource
@ns.route("/<int:id>")
@ns.param("id", "The user identifier")
class UserDetail(Resource):
    """Show a single user and update or delete it."""

    @jwt_required()
    @ns.doc("get_user")
    @ns.response(200, "Success", user_model)
    @ns.response(404, "User not found")
    def get(self, id: int) -> any:
        """Get a user by ID."""
        try:
            # Only admins can view other users
            if not g.user.is_admin and g.user.id != id:
                raise AuthorizationError("Not authorized to view this user")

            with SessionManager() as session:
                user: User = UserService.get_or_404(session, id)
                return user_schema.dump(user)
        except (ResourceNotFoundError, AuthorizationError) as e:
            logger.warning(f"Error retrieving user {id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error retrieving user {id}: {str(e)}")
            raise BusinessLogicError(f"Error retrieving user: {str(e)}") from e

    @jwt_required()
    @ns.doc("update_user")
    @ns.expect(user_update_model)
    @ns.response(200, "Success", user_model)
    @ns.response(400, "Validation error")
    @ns.response(404, "User not found")
    def put(self, id: int) -> any:
        """Update a user."""
        try:
            # Only admins or the user themselves can update
            if not g.user.is_admin and g.user.id != id:
                raise AuthorizationError("Not authorized to update this user")

            data: dict[str, any] = request.json or {}
            # Validate input with schema
            errors: list[str] = user_update_schema.validate(data)
            if errors:
                raise ValidationError(f"Invalid input data: {errors}")

            with SessionManager() as session:
                user: User = UserService.get_or_404(session, id)

                # Non-admins cannot set admin status
                if not g.user.is_admin and "is_admin" in data:
                    raise AuthorizationError("Not authorized to set admin status")

                # Use UserService to update user
                updated_user: User = UserService.update_user(session, user, data)
                return user_schema.dump(updated_user)

        except (ValidationError, ResourceNotFoundError, AuthorizationError) as e:
            logger.warning(f"Error updating user {id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error updating user {id}: {str(e)}")
            raise BusinessLogicError(f"Error updating user: {str(e)}") from e

    @jwt_required()
    @admin_required
    @ns.doc("delete_user")
    @ns.expect(user_delete_model)
    @ns.response(204, "User deleted")
    @ns.response(400, "Validation error")
    @ns.response(404, "User not found")
    def delete(self, id: int) -> tuple[any, Literal[204]]:
        """Delete a user."""
        try:
            data: dict[str, any] = request.json or {}
            data["user_id"] = id  # Ensure the ID matches the URL

            # Validate deletion request
            errors: list[str] = user_delete_schema.validate(data)
            if errors:
                raise ValidationError(f"Invalid deletion request: {errors}")

            # Verify admin password
            if not g.user.verify_password(data["password"]):
                raise AuthorizationError("Invalid admin password")

            with SessionManager() as session:
                user: User = UserService.get_or_404(session, id)

                # Cannot delete self
                if g.user.id == id:
                    raise BusinessLogicError("Cannot delete your own account")

                # Use UserService to delete user
                UserService.delete_user(session, user)

                # Log the deletion
                logger.info(f"User {id} deleted by admin {g.user.id}")

                return "", 204

        except (
            ValidationError,
            ResourceNotFoundError,
            AuthorizationError,
            BusinessLogicError,
        ) as e:
            logger.warning(f"Error deleting user {id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error deleting user {id}: {str(e)}")
            raise BusinessLogicError(f"Error deleting user: {str(e)}") from e


# Login resource
@ns.route("/login")
class UserLogin(Resource):
    """User login resource."""

    @ns.doc("login")
    @ns.expect(login_model)
    @ns.response(200, "Login successful", token_model)
    @ns.response(401, "Authentication failed")
    def post(self) -> tuple[dict[str, str], Literal[200]]:
        """Authenticate a user and return tokens."""
        try:
            data: dict[str, any] = request.json or {}
            # Validate input format
            errors: list[str] = user_login_schema.validate(data)
            if errors:
                raise ValidationError(f"Invalid login data: {errors}")

            username: str = data.get("username", "")
            password: str = data.get("password", "")

            with SessionManager() as session:
                user: User | None = UserService.find_by_username(session, username)

                # Check if user exists and password is correct
                if not user or not user.verify_password(password):
                    raise AuthorizationError("Invalid username or password")

                # Check if user is active
                if not user.is_active.scalar():
                    raise AuthorizationError("Account is disabled")

                # Record login with UserService
                UserService.login(session, user)

                # Generate tokens
                access_token: str = create_access_token(identity=user.id)
                refresh_token: str = create_refresh_token(identity=user.id)

                return {"access_token": access_token, "refresh_token": refresh_token}

        except (ValidationError, AuthorizationError) as e:
            logger.warning(f"Login failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error during login: {str(e)}")
            raise BusinessLogicError(f"Login error: {str(e)}") from e


# Password change resource
@ns.route("/change-password")
class PasswordChange(Resource):
    """Resource for changing user password."""

    @jwt_required()
    @ns.doc("change_password")
    @ns.expect(password_change_model)
    @ns.response(200, "Password changed")
    @ns.response(400, "Validation error")
    @ns.response(401, "Authentication failed")
    def post(self) -> dict[str, str]:
        """Change user password."""
        try:
            data: dict[str, any] = request.json or {}
            # Validate input format
            errors: list[str] = password_change_schema.validate(data)
            if errors:
                raise ValidationError(f"Invalid password change data: {errors}")

            current_password: str = data.get("current_password", "")
            new_password: str = data.get("new_password", "")

            # Get the current user
            user_id: int = get_jwt_identity()

            with SessionManager() as session:
                user: User = UserService.get_or_404(session, user_id)

                # Use UserService to change password
                UserService.change_password(
                    session, user, current_password, new_password
                )

                # Log the password change
                logger.info(f"Password changed for user {user_id}")

                return {"message": "Password changed successfully"}

        except (ValidationError, ResourceNotFoundError, AuthorizationError) as e:
            logger.warning(f"Password change failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error changing password: {str(e)}")
            raise BusinessLogicError(f"Password change error: {str(e)}") from e


# Token refresh resource
@ns.route("/refresh")
class TokenRefresh(Resource):
    """Resource for refreshing access token."""

    @jwt_required(refresh=True)
    @ns.doc("refresh_token")
    @ns.response(200, "Token refreshed", token_model)
    @ns.response(401, "Invalid refresh token")
    def post(self) -> dict[str, str]:
        """Refresh access token."""
        try:
            # Get user identity from refresh token
            user_id: int = get_jwt_identity()

            with SessionManager() as session:
                user: User = UserService.get_or_404(session, user_id)

                # Check if user is still active
                if not user.is_active.scalar():
                    raise AuthorizationError("Account is disabled")

                # Generate new access token
                access_token: str = create_access_token(identity=user_id)

                return {"access_token": access_token}

        except (ResourceNotFoundError, AuthorizationError) as e:
            logger.warning(f"Token refresh failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            raise BusinessLogicError(f"Token refresh error: {str(e)}") from e


# User toggle active status
@ns.route("/<int:id>/toggle-active")
@ns.param("id", "The user identifier")
class UserToggleActive(Resource):
    """Resource for toggling user active status."""

    @jwt_required()
    @admin_required
    @ns.doc("toggle_user_active")
    @ns.response(200, "Status toggled", user_model)
    @ns.response(404, "User not found")
    def post(self, id: int) -> any:
        """Toggle user active status."""
        try:
            with SessionManager() as session:
                user: User = UserService.get_or_404(session, id)

                # Cannot deactivate self
                if g.user.id == id:
                    raise BusinessLogicError("Cannot deactivate your own account")

                # Use UserService to toggle active status
                updated_user: User = UserService.toggle_active(session, user)

                return user_schema.dump(updated_user)

        except (ResourceNotFoundError, BusinessLogicError) as e:
            logger.warning(f"Error toggling user {id} active status: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error toggling user {id} active status: {str(e)}")
            raise BusinessLogicError(
                f"Error toggling user active status: {str(e)}"
            ) from e


# Current user resource
@ns.route("/me")
class CurrentUser(Resource):
    """Resource for getting current user information."""

    @jwt_required()
    @ns.doc("get_current_user")
    @ns.response(200, "Success", user_model)
    def get(self) -> any:
        """Get current user information."""
        try:
            user_id: int = get_jwt_identity()

            with SessionManager() as session:
                user: User = UserService.get_or_404(session, user_id)
                return user_schema.dump(user)

        except ResourceNotFoundError as e:
            logger.warning(f"Error retrieving current user: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error retrieving current user: {str(e)}")
            raise BusinessLogicError(f"Error retrieving current user: {str(e)}") from e
