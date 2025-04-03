"""User model schemas.

This module contains the schemas for the User model.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import timedelta

from marshmallow import (
    fields,
    post_load,
    validate,
    validates,
    validates_schema,
)
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from sqlalchemy import select

from app.api.schemas import Schema
from app.models import User
from app.services.session_manager import SessionManager
from app.utils.current_datetime import get_current_datetime
from app.utils.errors import ValidationError


class UserSchema(SQLAlchemyAutoSchema):
    """Schema for serializing/deserializing User models."""

    class Meta:
        """Metaclass defining schema configuration."""

        model = User
        include_relationships = False
        load_instance = True
        exclude: tuple[
            Literal["created_at"],
            Literal["updated_at"],
            Literal["password_hash"],
        ] = (
            "created_at",
            "updated_at",
            "password_hash",
        )

    # Don't expose the password hash
    password = fields.String(load_only=True, required=False)

    # Add computed properties
    has_services: fields.Method = fields.Method("check_has_services", dump_only=True)
    last_login_days_ago: fields.Method = fields.Method(
        "get_last_login_days",
        dump_only=True,
    )
    service_count: fields.Method = fields.Method("count_services", dump_only=True)

    def check_has_services(self, obj: User) -> bool:
        """Check if the user has any trading services."""
        return len(obj.services) > 0 if obj.services else False

    def get_last_login_days(self, obj: User) -> int | None:
        """Get the number of days since last login."""
        if not obj.last_login:
            return None
        delta: timedelta = get_current_datetime() - obj.last_login
        return delta.days

    def count_services(self, obj: User) -> int:
        """Count the number of trading services the user has."""
        return len(obj.services) if obj.services else 0

    @validates("username")
    def validate_username(self, username: str) -> None:
        """Validate username format."""
        if not re.match(r"^[a-zA-Z0-9_]+$", username):
            raise ValidationError(ValidationError.INVALID_USERNAME)

        # Check if username already exists
        with SessionManager() as session:
            existing_user: User | None = session.execute(
                select(User).where(User.username == username),
            ).scalar_one_or_none()
            if existing_user:
                raise ValidationError(ValidationError.USERNAME_EXISTS.format(username))


# Create instances for easy importing
user_schema = UserSchema()
users_schema = UserSchema(many=True)


# Schema for creating a new user
class UserCreateSchema(Schema):
    """Schema for creating a new User."""

    username: fields.String = fields.String(
        required=True,
        validate=validate.Length(min=3, max=50),
    )
    email: fields.Email = fields.Email(required=True)
    password: fields.String = fields.String(
        required=True,
        validate=validate.Length(min=8),
    )
    password_confirm: fields.String = fields.String(required=True)
    is_active: fields.Boolean = fields.Boolean(default=True)
    is_admin: fields.Boolean = fields.Boolean(default=False)

    @validates("username")
    def validate_username(self, username: str) -> None:
        """Validate username format."""
        if not re.match(r"^[a-zA-Z0-9_]+$", username):
            raise ValidationError(ValidationError.INVALID_USERNAME)

        # Check if username already exists
        with SessionManager() as session:
            existing_user: User | None = session.execute(
                select(User).where(User.username == username),
            ).scalar_one_or_none()
            if existing_user:
                raise ValidationError(ValidationError.USERNAME_EXISTS.format(username))

    @validates("email")
    def validate_email(self, email: str) -> None:
        """Validate email format and uniqueness."""
        # Check if email already exists
        with SessionManager() as session:
            existing_user: User | None = session.execute(
                select(User).where(User.email == email),
            ).scalar_one_or_none()
            if existing_user:
                raise ValidationError(ValidationError.EMAIL_EXISTS.format(email))

    @validates("password")
    def validate_password(self, password: str) -> None:
        """Validate password strength."""
        if not any(char.isdigit() for char in password):
            raise ValidationError(ValidationError.PASSWORD_NUMBER)
        if not any(char.isupper() for char in password):
            raise ValidationError(ValidationError.PASSWORD_UPPER)
        if not any(char.islower() for char in password):
            raise ValidationError(ValidationError.PASSWORD_LOWER)
        if not any(char in "!@#$%^&*()_+-=[]{}|;:,.<>?/~`" for char in password):
            raise ValidationError(ValidationError.PASSWORD_SPECIAL)

    @validates_schema
    def validate_passwords_match(self, data: dict) -> None:
        """Validate password and confirmation match."""
        if data.get("password") != data.get("password_confirm"):
            raise ValidationError(ValidationError.PASSWORDS_MISMATCH)

    @post_load
    def make_user(self, data: dict) -> User:
        """Create a User instance from validated data."""
        # Remove password_confirm as it's not needed for user creation
        data.pop("password_confirm", None)

        user: User = User(
            username=data["username"],
            email=data["email"],
            is_active=data.get("is_active", True),
            is_admin=data.get("is_admin", False),
        )
        user.password = data["password"]
        return user


# Schema for updating an existing user
class UserUpdateSchema(Schema):
    """Schema for updating an existing User."""

    username: fields.String = fields.String(validate=validate.Length(min=3, max=50))
    email: fields.Email = fields.Email()
    password: fields.String = fields.String(validate=validate.Length(min=8))
    password_confirm: fields.String = fields.String()
    is_active: fields.Boolean = fields.Boolean()
    is_admin: fields.Boolean = fields.Boolean()

    @validates("username")
    def validate_username(self, username: str) -> None:
        """Validate username format."""
        if not re.match(r"^[a-zA-Z0-9_]+$", username):
            raise ValidationError(ValidationError.INVALID_USERNAME)

    @validates("password")
    def validate_password(self, password: str) -> None:
        """Validate password strength."""
        if not any(char.isdigit() for char in password):
            raise ValidationError(ValidationError.PASSWORD_NUMBER)
        if not any(char.isupper() for char in password):
            raise ValidationError(ValidationError.PASSWORD_UPPER)
        if not any(char.islower() for char in password):
            raise ValidationError(ValidationError.PASSWORD_LOWER)
        if not any(char in "!@#$%^&*()_+-=[]{}|;:,.<>?/~`" for char in password):
            raise ValidationError(ValidationError.PASSWORD_SPECIAL)

    @validates_schema
    def validate_passwords_match(self, data: dict) -> None:
        """Validate password and confirmation match."""
        if (
            "password" in data
            and "password_confirm" in data
            and data.get("password") != data.get("password_confirm")
        ):
            raise ValidationError(ValidationError.PASSWORDS_MISMATCH)


# Schema for deleting a user
class UserDeleteSchema(Schema):
    """Schema for confirming user deletion."""

    confirm: fields.Boolean = fields.Boolean(required=True)
    user_id: fields.Integer = fields.Integer(required=True)
    password: fields.String = fields.String(
        required=True,
    )  # Require password for security

    @validates_schema
    def validate_deletion(self, data: dict) -> None:
        """Validate deletion confirmation and password."""
        if not data.get("confirm"):
            raise ValidationError(ValidationError.MUST_CONFIRM)

        # Verify the user exists and password is correct
        with SessionManager() as session:
            user: User | None = session.execute(
                select(User).where(User.id == data["user_id"]),
            ).scalar_one_or_none()
            if not user:
                raise ValidationError(ValidationError.USER_NOT_FOUND)

            if not user.verify_password(data["password"]):
                raise ValidationError(ValidationError.INVALID_PASSWORD)

            # Check if user has active services
            if user.services and any(service.is_active for service in user.services):
                raise ValidationError(ValidationError.ACTIVE_SERVICES)


# Schema for user login
class UserLoginSchema(Schema):
    """Schema for user login."""

    username: fields.String = fields.String(required=True)
    password: fields.String = fields.String(required=True)

    @validates_schema
    def validate_credentials(self, data: dict) -> None:
        """Validate username exists."""
        with SessionManager() as session:
            user: User | None = session.execute(
                select(User).where(User.username == data.get("username")),
            ).scalar_one_or_none()
            if not user:
                raise ValidationError(ValidationError.INVALID_CREDENTIALS)

            # We only validate that the username exists here
            # The actual password verification will be done in the resource
            # to prevent timing attacks


# Schema for changing password
class PasswordChangeSchema(Schema):
    """Schema for changing a user's password."""

    current_password: fields.String = fields.String(required=True)
    new_password: fields.String = fields.String(
        required=True,
        validate=validate.Length(min=8),
    )
    confirm_password: fields.String = fields.String(required=True)

    @validates("new_password")
    def validate_password(self, password: str) -> None:
        """Validate password strength."""
        if not any(char.isdigit() for char in password):
            raise ValidationError(ValidationError.PASSWORD_NUMBER)
        if not any(char.isupper() for char in password):
            raise ValidationError(ValidationError.PASSWORD_UPPER)
        if not any(char.islower() for char in password):
            raise ValidationError(ValidationError.PASSWORD_LOWER)
        if not any(char in "!@#$%^&*()_+-=[]{}|;:,.<>?/~`" for char in password):
            raise ValidationError(ValidationError.PASSWORD_SPECIAL)

    @validates_schema
    def validate_passwords_match(self, data: dict) -> None:
        """Validate new password and confirmation match."""
        if data.get("new_password") != data.get("confirm_password"):
            raise ValidationError(ValidationError.PASSWORDS_MISMATCH)


# Create instances for easy importing
user_create_schema = UserCreateSchema()
user_update_schema = UserUpdateSchema()
user_delete_schema = UserDeleteSchema()
user_login_schema = UserLoginSchema()
password_change_schema = PasswordChangeSchema()
