"""
API routes for the Day Trader application.

This package contains all the API routes for the application,
organized into modules by functionality.
"""

from flask import Blueprint

# Create the API blueprint
bp = Blueprint("api", __name__, url_prefix="/api")

# Import route modules
# Note: these imports must come after the blueprint is created
from app.deprecated.routes.api import services, system, transactions

__all__ = ["bp"]
