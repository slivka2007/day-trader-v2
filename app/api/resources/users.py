"""User API resources.

This module provides the API resources for managing users. It includes endpoints
for listing users, creating new users, updating existing users, deleting users,
and changing passwords.

The module uses the Flask-RESTx framework for building the API and the
Flask-JWT-Extended library for handling JWT tokens.

The module also uses the app.api.schemas.user module for validating user input
and the app.models.user module for defining the User model.

The module also uses the app.services.session_manager module for managing
the database session and the app.services.user_service module for managing
the user service.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from flask import current_app, g, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)
from flask_restx import Model, Namespace, Resource, fields

if TYPE_CHECKING:
    from app.models import User

from app.api.schemas.user import (
    password_change_schema,
    user_create_schema,
    user_delete_schema,
    user_login_schema,
    user_schema,
    user_update_schema,
    users_schema,
)
from app.services.session_manager import SessionManager
from app.services.user_service import UserService
from app.utils.auth import admin_required
from app.utils.constants import ApiConstants, PaginationConstants
from app.utils.errors import (
    AuthorizationError,
    BusinessLogicError,
    ResourceNotFoundError,
    UserError,
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
            required=True,
            description="Unique username (letters, numbers, underscores)",
        ),
        "email": fields.String(required=True, description="Unique email address"),
        "password": fields.String(
            required=True,
            description="Password (min 8 chars with number, upper, lower, special)",
        ),
        "password_confirm": fields.String(
            required=True,
            description="Confirm password",
        ),
        "is_active": fields.Boolean(description="Is user account active"),
        "is_admin": fields.Boolean(description="Is user an administrator"),
    },
)

user_update_model: Model = ns.model(
    "UserUpdate",
    {
        "username": fields.String(
            description="Unique username (letters, numbers, underscores)",
        ),
        "email": fields.String(description="Unique email address"),
        "password": fields.String(
            description="Password (min 8 chars with number, upper, lower, special)",
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
            required=True,
            description="Admin password for verification",
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
            required=True,
            description="Current password",
        ),
        "new_password": fields.String(
            required=True,
            description="New password (min 8 chars with number, upper, lower, special)",
        ),
        "confirm_password": fields.String(
            required=True,
            description="Confirm new password",
        ),
    },
)

# Add pagination model
pagination_model: Model = ns.model(
    "Pagination",
    {
        "page": fields.Integer(description="Current page number"),
        "page_size": fields.Integer(description="Number of items per page"),
        "total_items": fields.Integer(description="Total number of items"),
        "total_pages": fields.Integer(description="Total number of pages"),
        "has_next": fields.Boolean(description="Whether there is a next page"),
        "has_prev": fields.Boolean(description="Whether there is a previous page"),
    },
)

# Add paginated list model
user_list_model: Model = ns.model(
    "UserList",
    {
        "items": fields.List(fields.Nested(user_model), description="List of users"),
        "pagination": fields.Nested(
            pagination_model,
            description="Pagination information",
        ),
    },
)


# Helper functions for validation
def validate_user_access(current_user: User, target_user_id: int) -> None:
    """Validate if user has access to view/edit another user."""
    if not current_user.is_admin and current_user.id != target_user_id:
        raise AuthorizationError(AuthorizationError.ADMIN_ONLY)


def validate_admin_status_change(current_user: User, data: dict[str, any]) -> None:
    """Validate if user can change admin status."""
    if not current_user.is_admin and "is_admin" in data:
        raise AuthorizationError(AuthorizationError.ADMIN_ONLY)


def validate_self_modification(
    current_user: User,
    target_user_id: int,
    action: str,
) -> None:
    """Validate if user is trying to modify their own account."""
    if current_user.id == target_user_id and action in ["delete", "deactivate"]:
        raise BusinessLogicError(UserError.ACTIVE_SERVICES)


def validate_duplicate_username(username: str) -> None:
    """Validate if username already exists."""
    raise BusinessLogicError(UserError.USERNAME_EXISTS.format(username))


def validate_password(user: User, password: str) -> None:
    """Validate user password."""
    if not user.verify_password(password):
        raise AuthorizationError(ValidationError.INVALID_PASSWORD)


def validate_user_active(user: User) -> None:
    """Validate if user account is active."""
    if not user.is_active:
        raise AuthorizationError(AuthorizationError.ACCOUNT_INACTIVE)


def validate_user_exists() -> None:
    """Validate if user exists."""
    raise AuthorizationError(ValidationError.INVALID_CREDENTIALS)


# User list resource
@ns.route("/")
class UserList(Resource):
    """Shows a list of all users and creates new users."""

    @jwt_required()
    @ns.doc(
        "list_users",
        params={
            "page": f"Page number (default: {PaginationConstants.DEFAULT_PAGE})",
            "page_size": (
                f"Number of items per page (default: "
                f"{PaginationConstants.DEFAULT_PER_PAGE}, "
                f"max: {PaginationConstants.MAX_PER_PAGE})"
            ),
            "username": "Filter by username (exact match)",
            "username_like": "Filter by username (partial match)",
            "is_active": "Filter by active status (true/false)",
            "is_admin": "Filter by admin status (true/false)",
            "sort": "Sort field (e.g., username, email)",
            "order": "Sort order (asc or desc, default: asc)",
        },
    )
    @ns.marshal_with(user_list_model)
    @ns.response(ApiConstants.HTTP_OK, "Success")
    @ns.response(ApiConstants.HTTP_UNAUTHORIZED, "Not authorized to list users")
    def get(self) -> tuple[dict[str, any], int]:
        """Get all users with filtering and pagination."""
        try:
            # Check if user is admin
            if not g.user.is_admin:
                return {
                    "error": True,
                    "message": "Admin privileges required",
                    "status_code": ApiConstants.HTTP_UNAUTHORIZED,
                }, ApiConstants.HTTP_UNAUTHORIZED

            # Parse query parameters
            page: int = request.args.get(
                "page",
                default=PaginationConstants.DEFAULT_PAGE,
                type=int,
            )
            per_page: int = request.args.get(
                "per_page",
                default=PaginationConstants.DEFAULT_PER_PAGE,
                type=int,
            )

            with SessionManager() as session:
                # Get filtered and paginated users using the UserService
                result: dict[str, any] = UserService.get_filtered_users(
                    session=session,
                    filters=request.args,
                    page=page,
                    per_page=per_page,
                )

                # Serialize the results
                result["items"] = users_schema.dump(result["items"])

                return result, ApiConstants.HTTP_OK

        except ValidationError as e:
            logger.warning("Validation error listing users: %s", str(e))
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except Exception as e:
            current_app.logger.exception("Error listing users")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR

    @ns.doc("create_user")
    @ns.expect(user_create_model)
    @ns.marshal_with(user_model)
    @ns.response(ApiConstants.HTTP_CREATED, "User created successfully")
    @ns.response(ApiConstants.HTTP_BAD_REQUEST, "Invalid input")
    @ns.response(ApiConstants.HTTP_CONFLICT, "User with this username already exists")
    def post(self) -> tuple[dict[str, any], int]:
        """Create a new user."""
        try:
            data: dict[str, any] = request.json or {}

            # Validate input data
            validated_data: User = user_create_schema.load(
                data,
            )  # This now returns a User object

            with SessionManager() as session:
                # Check if username already exists (now using the User object's
                # attributes)
                existing_user: User | None = UserService.find_by_username(
                    session,
                    validated_data.username,
                )
                if existing_user:
                    validate_duplicate_username(validated_data.username)

                # Add the user to the session and commit
                session.add(validated_data)
                session.commit()
                session.refresh(validated_data)

                return user_schema.dump(validated_data), ApiConstants.HTTP_CREATED

        except ValidationError as e:
            logger.warning("Validation error creating user: %s", str(e))
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except BusinessLogicError as e:
            logger.warning("Business logic error creating user: %s", str(e))
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_CONFLICT
        except Exception as e:
            current_app.logger.exception("Error creating user")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


# User detail resource
@ns.route("/<int:user_id>")
@ns.param("user_id", "The user identifier")
@ns.response(ApiConstants.HTTP_NOT_FOUND, "User not found")
class UserDetail(Resource):
    """Show a single user and update or delete it."""

    @jwt_required()
    @ns.doc("get_user")
    @ns.marshal_with(user_model)
    @ns.response(ApiConstants.HTTP_OK, "Success")
    @ns.response(ApiConstants.HTTP_NOT_FOUND, "User not found")
    @ns.response(ApiConstants.HTTP_UNAUTHORIZED, "Not authorized to view this user")
    def get(self, user_id: int) -> tuple[dict[str, any], int]:
        """Get a user by ID."""
        try:
            # Only admins can view other users
            if not g.user.is_admin and g.user.id != user_id:
                validate_user_access(g.user, user_id)

            with SessionManager() as session:
                user: User = UserService.get_or_404(session, user_id)
                return user_schema.dump(user), ApiConstants.HTTP_OK

        except ResourceNotFoundError as e:
            logger.warning("User not found: %d, %s", user_id, str(e))
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except AuthorizationError as e:
            logger.warning(
                "Authorization error retrieving user %d: %s",
                user_id,
                str(e),
            )
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except Exception as e:
            current_app.logger.exception("Error retrieving user")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR

    @jwt_required()
    @ns.doc("update_user")
    @ns.expect(user_update_model)
    @ns.marshal_with(user_model)
    @ns.response(ApiConstants.HTTP_OK, "User updated successfully")
    @ns.response(ApiConstants.HTTP_BAD_REQUEST, "Invalid input")
    @ns.response(ApiConstants.HTTP_NOT_FOUND, "User not found")
    @ns.response(ApiConstants.HTTP_UNAUTHORIZED, "Not authorized to update this user")
    def put(self, user_id: int) -> tuple[dict[str, any], int]:
        """Update a user."""
        try:
            # Only admins or the user themselves can update
            validate_user_access(g.user, user_id)

            data: dict[str, any] = request.json or {}

            # Validate input data
            validated_data: dict[str, any] = user_update_schema.load(data, partial=True)

            with SessionManager() as session:
                user: User = UserService.get_or_404(session, user_id)

                # Non-admins cannot set admin status
                validate_admin_status_change(g.user, validated_data)

                # Use UserService to update user
                updated_user: User = UserService.update_user(
                    session,
                    user,
                    validated_data,
                )
                return user_schema.dump(updated_user), ApiConstants.HTTP_OK

        except ValidationError as e:
            current_app.logger.exception("Validation error updating user")
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except ResourceNotFoundError as e:
            logger.warning("User not found: %d, %s", user_id, str(e))
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except AuthorizationError as e:
            logger.warning(
                "Authorization error updating user %d: %s",
                user_id,
                str(e),
            )
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except BusinessLogicError as e:
            current_app.logger.exception("Business logic error updating user")
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_CONFLICT
        except Exception as e:
            current_app.logger.exception("Error updating user")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR

    @jwt_required()
    @admin_required
    @ns.doc("delete_user")
    @ns.expect(user_delete_model)
    @ns.response(ApiConstants.HTTP_NO_CONTENT, "User deleted")
    @ns.response(ApiConstants.HTTP_BAD_REQUEST, "Invalid input")
    @ns.response(ApiConstants.HTTP_NOT_FOUND, "User not found")
    @ns.response(ApiConstants.HTTP_UNAUTHORIZED, "Invalid admin password")
    @ns.response(ApiConstants.HTTP_CONFLICT, "Cannot delete your own account")
    def delete(self, user_id: int) -> tuple[any, int]:
        """Delete a user."""
        try:
            data: dict[str, any] = request.json or {}
            data["user_id"] = user_id  # Ensure the ID matches the URL

            # Validate deletion request
            validated_data: dict[str, any] = user_delete_schema.load(data)

            # Verify admin password
            validate_password(g.user, validated_data["password"])

            with SessionManager() as session:
                user: User = UserService.get_or_404(session, user_id)

                # Cannot delete self
                validate_self_modification(g.user, user_id, "delete")

                # Use UserService to delete user
                UserService.delete_user(session, user)

                # Log the deletion
                logger.info("User %d deleted by admin %d", user_id, g.user.id)

                return "", ApiConstants.HTTP_NO_CONTENT

        except ValidationError as e:
            current_app.logger.exception("Validation error deleting user")
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except ResourceNotFoundError as e:
            logger.warning("User not found: %d, %s", user_id, str(e))
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except AuthorizationError as e:
            logger.warning(
                "Authorization error deleting user %d: %s",
                user_id,
                str(e),
            )
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except BusinessLogicError as e:
            current_app.logger.exception("Business logic error deleting user")
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_CONFLICT
        except Exception as e:
            current_app.logger.exception("Error deleting user")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


# Login resource
@ns.route("/login")
class UserLogin(Resource):
    """User login resource."""

    @ns.doc("login")
    @ns.expect(login_model)
    @ns.response(ApiConstants.HTTP_OK, "Login successful", token_model)
    @ns.response(ApiConstants.HTTP_UNAUTHORIZED, "Authentication failed")
    @ns.response(ApiConstants.HTTP_BAD_REQUEST, "Invalid input")
    def post(self) -> tuple[dict[str, str], int]:
        """Authenticate a user and return tokens."""
        try:
            data: dict[str, any] = request.json or {}

            # Validate input data
            validated_data: dict[str, any] = user_login_schema.load(data)

            username: str = validated_data.get("username", "")
            password: str = validated_data.get("password", "")

            with SessionManager() as session:
                user: User | None = UserService.find_by_username(session, username)

                # Check if user exists and password is correct
                if not user or not user.verify_password(password):
                    validate_user_exists()

                # Check if user is active
                validate_user_active(user)

                # Record login with UserService
                UserService.login(session, user)

                # Generate tokens
                access_token: str = create_access_token(identity=str(user.id))
                refresh_token: str = create_refresh_token(identity=str(user.id))

                return {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                }, ApiConstants.HTTP_OK

        except ValidationError as e:
            current_app.logger.exception("Validation error during login")
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except AuthorizationError as e:
            logger.warning("Login failed: %s", str(e))
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except Exception as e:
            current_app.logger.exception("Error during login")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


# Password change resource
@ns.route("/change-password")
class PasswordChange(Resource):
    """Resource for changing user password."""

    @jwt_required()
    @ns.doc("change_password")
    @ns.expect(password_change_model)
    @ns.response(ApiConstants.HTTP_OK, "Password changed successfully")
    @ns.response(ApiConstants.HTTP_BAD_REQUEST, "Invalid input")
    @ns.response(ApiConstants.HTTP_UNAUTHORIZED, "Authentication failed")
    def post(self) -> tuple[dict[str, str], int]:
        """Change user password."""
        try:
            data: dict[str, any] = request.json or {}

            # Validate input data
            validated_data: dict[str, any] = password_change_schema.load(data)

            current_password: str = validated_data.get("current_password", "")
            new_password: str = validated_data.get("new_password", "")

            # Get the current user
            user_id = get_jwt_identity()

            # Convert user_id to integer if it's a string
            if isinstance(user_id, str):
                user_id = int(user_id)

            with SessionManager() as session:
                user: User = UserService.get_or_404(session, user_id)

                # Use UserService to change password
                UserService.change_password(
                    session,
                    user,
                    current_password,
                    new_password,
                )

                # Log the password change
                logger.info("Password changed for user %d", user_id)

                return {
                    "message": "Password changed successfully",
                }, ApiConstants.HTTP_OK

        except ValidationError as e:
            current_app.logger.exception("Validation error changing password")
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_BAD_REQUEST
        except ResourceNotFoundError as e:
            logger.warning("User not found when changing password: %s", str(e))
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except AuthorizationError as e:
            logger.warning("Authorization error changing password: %s", str(e))
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except Exception as e:
            current_app.logger.exception("Error changing password")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


# Token refresh resource
@ns.route("/refresh")
class TokenRefresh(Resource):
    """Resource for refreshing access token."""

    @jwt_required(refresh=True)
    @ns.doc("refresh_token")
    @ns.response(ApiConstants.HTTP_OK, "Token refreshed", token_model)
    @ns.response(ApiConstants.HTTP_UNAUTHORIZED, "Invalid refresh token")
    @ns.response(ApiConstants.HTTP_NOT_FOUND, "User not found")
    def post(self) -> tuple[dict[str, str], int]:
        """Refresh access token."""
        try:
            # Get user identity from refresh token
            user_id: int = get_jwt_identity()

            with SessionManager() as session:
                user: User = UserService.get_or_404(session, user_id)

                # Check if user is still active
                validate_user_active(user)

                # Generate new access token
                access_token: str = create_access_token(identity=str(user_id))

                return {"access_token": access_token}, ApiConstants.HTTP_OK

        except ResourceNotFoundError as e:
            logger.warning("User not found during token refresh: %s", str(e))
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except AuthorizationError as e:
            logger.warning("Token refresh failed: %s", str(e))
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_UNAUTHORIZED
        except Exception as e:
            current_app.logger.exception("Error refreshing token")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


# User toggle active status
@ns.route("/<int:user_id>/toggle-active")
@ns.param("user_id", "The user identifier")
@ns.response(ApiConstants.HTTP_NOT_FOUND, "User not found")
class UserToggleActive(Resource):
    """Resource for toggling user active status."""

    @jwt_required()
    @admin_required
    @ns.doc("toggle_user_active")
    @ns.marshal_with(user_model)
    @ns.response(ApiConstants.HTTP_OK, "Status toggled")
    @ns.response(ApiConstants.HTTP_NOT_FOUND, "User not found")
    @ns.response(ApiConstants.HTTP_CONFLICT, "Cannot deactivate your own account")
    def post(self, user_id: int) -> tuple[dict[str, any], int]:
        """Toggle user active status."""
        try:
            with SessionManager() as session:
                user: User = UserService.get_or_404(session, user_id)

                # Cannot deactivate self
                validate_self_modification(g.user, user_id, "deactivate")

                # Use UserService to toggle active status
                updated_user: User = UserService.toggle_active(session, user)

                return user_schema.dump(updated_user), ApiConstants.HTTP_OK

        except ResourceNotFoundError as e:
            logger.warning("User not found when toggling active status: %s", str(e))
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except BusinessLogicError as e:
            logger.warning(
                "Business logic error toggling user %d active status: %s",
                user_id,
                str(e),
            )
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_CONFLICT
        except Exception as e:
            current_app.logger.exception("Error toggling user active status")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR


# Current user resource
@ns.route("/me")
class CurrentUser(Resource):
    """Resource for getting current user information."""

    @jwt_required()
    @ns.doc("get_current_user")
    @ns.marshal_with(user_model)
    @ns.response(ApiConstants.HTTP_OK, "Success")
    @ns.response(ApiConstants.HTTP_NOT_FOUND, "User not found")
    def get(self) -> tuple[dict[str, any], int]:
        """Get current user information."""
        try:
            user_id: int = get_jwt_identity()

            with SessionManager() as session:
                user: User = UserService.get_or_404(session, user_id)
                return user_schema.dump(user), ApiConstants.HTTP_OK

        except ResourceNotFoundError as e:
            logger.warning("Current user not found: %s", str(e))
            return {"error": True, "message": str(e)}, ApiConstants.HTTP_NOT_FOUND
        except Exception as e:
            current_app.logger.exception("Error retrieving current user")
            return {
                "error": True,
                "message": f"An unexpected error occurred: {e!s}",
            }, ApiConstants.HTTP_INTERNAL_SERVER_ERROR
