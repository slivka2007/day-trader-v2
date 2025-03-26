"""
API resources for the Day Trader application.

This package contains REST API resources using Flask-RESTX.
"""
# Common imports for resources
from flask import request, current_app
from flask_restx import Namespace, Resource, fields, abort

# Database session management
from sqlalchemy.orm import Session
from app.services.database import get_db_session

# Make common imports available
__all__ = [
    'Namespace',
    'Resource',
    'fields',
    'abort',
    'request',
    'current_app',
    'get_db_session',
] 