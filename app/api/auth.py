"""
Authentication API resources.

This module contains JWT-based authentication endpoints and helpers.
"""
from flask import request, current_app, jsonify
from flask_restx import Namespace, Resource, fields, abort
from flask_jwt_extended import (
    create_access_token, 
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
    get_jwt
)
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

from app.services.database import get_db_session
from app.models import User

# Create namespace
api = Namespace('auth', description='Authentication operations')

# Define API models
login_model = api.model('Login', {
    'username': fields.String(required=True, description='Username'),
    'password': fields.String(required=True, description='Password'),
})

register_model = api.model('Register', {
    'username': fields.String(required=True, description='Username'),
    'email': fields.String(required=True, description='Email'),
    'password': fields.String(required=True, description='Password'),
})

token_model = api.model('Token', {
    'access_token': fields.String(description='JWT access token'),
    'refresh_token': fields.String(description='JWT refresh token'),
    'user': fields.Nested(api.model('UserInfo', {
        'id': fields.Integer(description='User ID'),
        'username': fields.String(description='Username'),
        'email': fields.String(description='Email'),
        'is_admin': fields.Boolean(description='Admin status'),
    }))
})

# JWT error handlers
@api.errorhandler(Exception)
def handle_auth_error(error):
    """Return a custom error message and 401 status code."""
    return {'message': str(error)}, 401

# Helper functions for role checking
def admin_required(fn):
    """Decorator to check if the user has admin privileges."""
    @jwt_required()
    def wrapper(*args, **kwargs):
        # Get user ID from token
        user_id = get_jwt_identity()
        
        # Check if user is admin
        with get_db_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user or not user.is_admin:
                abort(403, "Admin privileges required")
        
        return fn(*args, **kwargs)
    
    return wrapper

@api.route('/register')
class Register(Resource):
    """Resource for user registration."""
    
    @api.doc('register_user')
    @api.expect(register_model)
    @api.marshal_with(token_model)
    def post(self):
        """Register a new user and return access tokens."""
        data = request.json
        
        with get_db_session() as session:
            # Check if username already exists
            existing_user = session.query(User).filter_by(username=data['username']).first()
            if existing_user:
                abort(409, "Username already exists")
            
            # Check if email already exists
            existing_email = session.query(User).filter_by(email=data['email']).first()
            if existing_email:
                abort(409, "Email already exists")
            
            # Create new user
            user = User(
                username=data['username'],
                email=data['email'],
                is_active=True,
                is_admin=False,
                last_login=datetime.utcnow()
            )
            user.password = data['password']
            
            session.add(user)
            session.commit()
            session.refresh(user)
            
            # Create tokens
            access_token = create_access_token(identity=user.id)
            refresh_token = create_refresh_token(identity=user.id)
            
            return {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'is_admin': user.is_admin
                }
            }

@api.route('/login')
class Login(Resource):
    """Resource for user login."""
    
    @api.doc('login_user')
    @api.expect(login_model)
    @api.marshal_with(token_model)
    def post(self):
        """Log in a user and return access tokens."""
        data = request.json
        
        with get_db_session() as session:
            # Find user by username
            user = session.query(User).filter_by(username=data['username']).first()
            
            # Check if user exists and password is valid
            if not user or not user.verify_password(data['password']):
                abort(401, "Invalid username or password")
            
            # Check if user is active
            if not user.is_active:
                abort(403, "Account is inactive")
            
            # Update last login timestamp
            user.update_last_login()
            session.commit()
            
            # Create tokens
            access_token = create_access_token(identity=user.id)
            refresh_token = create_refresh_token(identity=user.id)
            
            return {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'is_admin': user.is_admin
                }
            }

@api.route('/refresh')
class Refresh(Resource):
    """Resource for refreshing access tokens."""
    
    @api.doc('refresh_token')
    @jwt_required(refresh=True)
    @api.marshal_with(token_model)
    def post(self):
        """Refresh the access token using a refresh token."""
        # Get user ID from refresh token
        user_id = get_jwt_identity()
        
        with get_db_session() as session:
            # Find user by ID
            user = session.query(User).filter_by(id=user_id).first()
            
            # Check if user exists and is active
            if not user or not user.is_active:
                abort(403, "Account is inactive or not found")
            
            # Create new access token
            access_token = create_access_token(identity=user.id)
            
            return {
                'access_token': access_token,
                'refresh_token': request.cookies.get('refresh_token'),
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'is_admin': user.is_admin
                }
            }

# Expose decorators for other endpoints to use
jwt_auth = jwt_required() 