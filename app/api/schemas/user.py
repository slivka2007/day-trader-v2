"""
User model schemas.
"""
import re
from marshmallow import fields, post_load, validates, validates_schema, ValidationError, validate
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from app.models import User
from app.api.schemas import Schema
from app.services.database import get_db_session
from app.utils.current_datetime import get_current_datetime

class UserSchema(SQLAlchemyAutoSchema):
    """Schema for serializing/deserializing User models."""
    
    class Meta:
        model = User
        include_relationships = False
        load_instance = True
        exclude = ('created_at', 'updated_at', 'password_hash')
    
    # Don't expose the password hash
    password = fields.String(load_only=True, required=False)
    
    # Add computed properties
    has_services = fields.Method("check_has_services", dump_only=True)
    last_login_days_ago = fields.Method("get_last_login_days", dump_only=True)
    service_count = fields.Method("count_services", dump_only=True)
    
    def check_has_services(self, obj):
        """Check if the user has any trading services."""
        return len(obj.services) > 0 if obj.services else False
    
    def get_last_login_days(self, obj):
        """Get the number of days since last login."""
        if not obj.last_login:
            return None
        delta = get_current_datetime() - obj.last_login
        return delta.days
    
    def count_services(self, obj):
        """Count the number of trading services the user has."""
        return len(obj.services) if obj.services else 0

# Create instances for easy importing
user_schema = UserSchema()
users_schema = UserSchema(many=True)

# Schema for creating a new user
class UserCreateSchema(Schema):
    """Schema for creating a new User."""
    username = fields.String(required=True, validate=validate.Length(min=3, max=50))
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=8))
    password_confirm = fields.String(required=True)
    is_active = fields.Boolean(default=True)
    is_admin = fields.Boolean(default=False)
    
    @validates('username')
    def validate_username(self, username):
        """Validate username format."""
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            raise ValidationError('Username must contain only letters, numbers and underscores')
        
        # Check if username already exists
        with get_db_session() as session:
            existing_user = session.query(User).filter_by(username=username).first()
            if existing_user:
                raise ValidationError('Username already exists')
    
    @validates('email')
    def validate_email(self, email):
        """Validate email format and uniqueness."""
        # Check if email already exists
        with get_db_session() as session:
            existing_user = session.query(User).filter_by(email=email).first()
            if existing_user:
                raise ValidationError('Email address already exists')
    
    @validates('password')
    def validate_password(self, password):
        """Validate password strength."""
        if not any(char.isdigit() for char in password):
            raise ValidationError('Password must contain at least one number')
        if not any(char.isupper() for char in password):
            raise ValidationError('Password must contain at least one uppercase letter')
        if not any(char.islower() for char in password):
            raise ValidationError('Password must contain at least one lowercase letter')
        if not any(char in '!@#$%^&*()_+-=[]{}|;:,.<>?/~`' for char in password):
            raise ValidationError('Password must contain at least one special character')
    
    @validates_schema
    def validate_passwords_match(self, data, **kwargs):
        """Validate password and confirmation match."""
        if data.get('password') != data.get('password_confirm'):
            raise ValidationError("Passwords do not match")
    
    @post_load
    def make_user(self, data, **kwargs):
        """Create a User instance from validated data."""
        # Remove password_confirm as it's not needed for user creation
        if 'password_confirm' in data:
            del data['password_confirm']
            
        user = User(
            username=data['username'],
            email=data['email'],
            is_active=data.get('is_active', True),
            is_admin=data.get('is_admin', False)
        )
        user.password = data['password']
        return user

# Schema for updating an existing user
class UserUpdateSchema(Schema):
    """Schema for updating an existing User."""
    username = fields.String(validate=validate.Length(min=3, max=50))
    email = fields.Email()
    password = fields.String(validate=validate.Length(min=8))
    password_confirm = fields.String()
    is_active = fields.Boolean()
    is_admin = fields.Boolean()
    
    @validates('username')
    def validate_username(self, username):
        """Validate username format."""
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            raise ValidationError('Username must contain only letters, numbers and underscores')
    
    @validates('password')
    def validate_password(self, password):
        """Validate password strength."""
        if not any(char.isdigit() for char in password):
            raise ValidationError('Password must contain at least one number')
        if not any(char.isupper() for char in password):
            raise ValidationError('Password must contain at least one uppercase letter')
        if not any(char.islower() for char in password):
            raise ValidationError('Password must contain at least one lowercase letter')
        if not any(char in '!@#$%^&*()_+-=[]{}|;:,.<>?/~`' for char in password):
            raise ValidationError('Password must contain at least one special character')
    
    @validates_schema
    def validate_passwords_match(self, data, **kwargs):
        """Validate password and confirmation match."""
        if 'password' in data and 'password_confirm' in data:
            if data.get('password') != data.get('password_confirm'):
                raise ValidationError("Passwords do not match")

# Schema for deleting a user
class UserDeleteSchema(Schema):
    """Schema for confirming user deletion."""
    confirm = fields.Boolean(required=True)
    user_id = fields.Integer(required=True)
    password = fields.String(required=True)  # Require password for security
    
    @validates_schema
    def validate_deletion(self, data, **kwargs):
        """Validate deletion confirmation and password."""
        if not data.get('confirm'):
            raise ValidationError("Must confirm deletion by setting 'confirm' to true")
        
        # Verify the user exists and password is correct
        with get_db_session() as session:
            user = session.query(User).filter_by(id=data['user_id']).first()
            if not user:
                raise ValidationError("User not found")
                
            if not user.verify_password(data['password']):
                raise ValidationError("Invalid password")
            
            # Check if user has active services
            if user.services and any(service.is_active for service in user.services):
                raise ValidationError("Cannot delete user with active trading services")

# Schema for user login
class UserLoginSchema(Schema):
    """Schema for user login."""
    username = fields.String(required=True)
    password = fields.String(required=True)
    
    @validates_schema
    def validate_credentials(self, data, **kwargs):
        """Validate username exists."""
        with get_db_session() as session:
            user = session.query(User).filter_by(username=data.get('username')).first()
            if not user:
                raise ValidationError("Invalid username or password")
            
            # We only validate that the username exists here
            # The actual password verification will be done in the resource
            # to prevent timing attacks

# Schema for changing password
class PasswordChangeSchema(Schema):
    """Schema for changing a user's password."""
    current_password = fields.String(required=True)
    new_password = fields.String(required=True, validate=validate.Length(min=8))
    confirm_password = fields.String(required=True)
    
    @validates('new_password')
    def validate_password(self, password):
        """Validate password strength."""
        if not any(char.isdigit() for char in password):
            raise ValidationError('Password must contain at least one number')
        if not any(char.isupper() for char in password):
            raise ValidationError('Password must contain at least one uppercase letter')
        if not any(char.islower() for char in password):
            raise ValidationError('Password must contain at least one lowercase letter')
        if not any(char in '!@#$%^&*()_+-=[]{}|;:,.<>?/~`' for char in password):
            raise ValidationError('Password must contain at least one special character')
    
    @validates_schema
    def validate_passwords_match(self, data, **kwargs):
        """Validate new password and confirmation match."""
        if data.get('new_password') != data.get('confirm_password'):
            raise ValidationError("New passwords do not match")

# Create instances for easy importing
user_create_schema = UserCreateSchema()
user_update_schema = UserUpdateSchema()
user_delete_schema = UserDeleteSchema()
user_login_schema = UserLoginSchema()
password_change_schema = PasswordChangeSchema() 