"""Authentication API resources.

This module contains JWT-based authentication endpoints and helpers.
"""

from __future__ import annotations

from typing import Callable

from flask import request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
)
from flask_restx import Model, Namespace, OrderedModel, Resource, fields
from sqlalchemy import select

from app.models import User
from app.services.session_manager import SessionManager
from app.utils.auth import get_current_user
from app.utils.constants import ApiConstants
from app.utils.current_datetime import get_current_datetime
from app.utils.errors import AuthorizationError, UserError, ValidationError

# Create namespace
api = Namespace("auth", description="Authentication operations")

# Define API models
login_model: Model | OrderedModel = api.model(
    "Login",
    {
        "username": fields.String(required=True, description="Username"),
        "password": fields.String(required=True, description="Password"),
    },
)

register_model: Model | OrderedModel = api.model(
    "Register",
    {
        "username": fields.String(
            required=True,
            description=UserError.USERNAME_REQUIREMENTS,
        ),
        "email": fields.String(required=True, description="Email"),
        "password": fields.String(
            required=True,
            description=UserError.PASSWORD_REQUIREMENTS,
        ),
        "password_confirm": fields.String(
            required=True,
            description="Confirm password",
        ),
    },
)

token_model: Model | OrderedModel = api.model(
    "Token",
    {
        "access_token": fields.String(description="JWT access token"),
        "refresh_token": fields.String(description="JWT refresh token"),
        "user": fields.Nested(
            api.model(
                "UserInfo",
                {
                    "id": fields.Integer(description="User ID"),
                    "username": fields.String(description="Username"),
                    "email": fields.String(description="Email"),
                    "is_admin": fields.Boolean(description="Admin status"),
                },
            ),
        ),
    },
)


# JWT error handlers
@api.errorhandler(Exception)
def handle_auth_error(error: Exception) -> tuple[dict[str, str], int]:
    """Return a custom error message and appropriate status code."""
    if isinstance(error, AuthorizationError):
        return {"message": str(error)}, error.status_code
    if isinstance(error, ValidationError):
        return {
            "message": str(error),
            "validation_errors": error.payload,
        }, error.status_code
    return {"message": str(error)}, ApiConstants.HTTP_UNAUTHORIZED


@api.route("/register")
class Register(Resource):
    """Resource for user registration."""

    @api.doc("register_user")
    @api.expect(register_model)
    @api.marshal_with(token_model)
    def post(self) -> dict[str, any]:
        """Register a new user and return access tokens."""
        data: dict[str, any] = request.json

        with SessionManager() as session:
            # Check if username already exists
            existing_user: User | None = session.execute(
                select(User).where(User.username == data["username"]),
            ).scalar_one_or_none()
            if existing_user:
                raise ValidationError(
                    UserError.USERNAME_EXISTS.format(data["username"]),
                    status_code=ApiConstants.HTTP_CONFLICT,
                )

            # Check if email already exists
            existing_email: User | None = session.execute(
                select(User).where(User.email == data["email"]),
            ).scalar_one_or_none()
            if existing_email:
                raise ValidationError(
                    UserError.EMAIL_EXISTS.format(data["email"]),
                    status_code=ApiConstants.HTTP_CONFLICT,
                )

            try:
                # Create new user
                user: User = User(
                    username=data["username"],
                    email=data["email"],
                    is_active=True,
                    is_admin=False,
                    last_login=get_current_datetime(),
                )
                user.password = data["password"]  # This will validate the password

                session.add(user)
                session.commit()
                session.refresh(user)

                # Create tokens
                access_token: str = create_access_token(identity=user.id)
                refresh_token: str = create_refresh_token(identity=user.id)

            except ValueError as e:
                raise ValidationError(
                    str(e),
                    status_code=ApiConstants.HTTP_BAD_REQUEST,
                ) from e

            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "is_admin": user.is_admin,
                },
            }


@api.route("/login")
class Login(Resource):
    """Resource for user login."""

    @api.doc("login_user")
    @api.expect(login_model)
    @api.marshal_with(token_model)
    def post(self) -> dict[str, any]:
        """Log in a user and return access tokens."""
        data: dict[str, any] = request.json

        with SessionManager() as session:
            # Find user by username
            user: User | None = session.execute(
                select(User).where(User.username == data["username"]),
            ).scalar_one_or_none()

            # Check if user exists and password is valid
            if not user or not user.verify_password(data["password"]):
                raise AuthorizationError(
                    UserError.INVALID_CREDENTIALS,
                    status_code=ApiConstants.HTTP_UNAUTHORIZED,
                )

            # Check if user is active
            if not user.is_active:
                raise AuthorizationError(
                    AuthorizationError.ACCOUNT_INACTIVE,
                    status_code=ApiConstants.HTTP_FORBIDDEN,
                )

            # Update last login timestamp
            user.update_last_login()
            session.commit()

            # Create tokens
            access_token: str = create_access_token(identity=user.id)
            refresh_token: str = create_refresh_token(identity=user.id)

            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "is_admin": user.is_admin,
                },
            }


@api.route("/refresh")
class Refresh(Resource):
    """Resource for refreshing access tokens."""

    @api.doc("refresh_token")
    @jwt_required(refresh=True)
    @api.marshal_with(token_model)
    def post(self) -> dict[str, any]:
        """Refresh the access token using a refresh token."""
        with SessionManager() as session:
            # Use the auth utility to get the current user
            user: User | None = get_current_user(session)

            # Check if user exists and is active
            if not user:
                raise AuthorizationError(
                    UserError.USER_NOT_FOUND,
                    status_code=ApiConstants.HTTP_NOT_FOUND,
                )
            if not user.is_active:
                raise AuthorizationError(
                    AuthorizationError.ACCOUNT_INACTIVE,
                    status_code=ApiConstants.HTTP_FORBIDDEN,
                )

            # Create new access token
            access_token: str = create_access_token(identity=user.id)

            return {
                "access_token": access_token,
                "refresh_token": request.cookies.get("refresh_token"),
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "is_admin": user.is_admin,
                },
            }


# Expose decorators for other endpoints to use
jwt_auth: Callable[[Callable[[], any]], Callable[[], any]] = jwt_required()
