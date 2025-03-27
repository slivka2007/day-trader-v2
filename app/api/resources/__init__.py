"""
API resources for the Day Trader application.

This package contains REST API resources using Flask-RESTX.
"""
# Common imports for resources
from flask import request, current_app
from flask_restx import Namespace, Resource, fields, abort, Api

# Database session management
from sqlalchemy.orm import Session
from app.services.database import get_db_session

# Import all resources
from app.api.resources.stocks import api as stocks_api
from app.api.resources.stock_prices import api as stock_prices_api
from app.api.resources.trading_services import api as trading_services_api
from app.api.resources.trading_transactions import api as trading_transactions_api
from app.api.resources.system import api as system_api

# Make common imports available
__all__ = [
    'Namespace',
    'Resource',
    'fields',
    'abort',
    'request',
    'current_app',
    'get_db_session',
    'register_resources',
    'api_resources',
]

# Create an aggregated list of resources for easy importing
api_resources = [
    stocks_api,
    stock_prices_api,
    trading_services_api,
    trading_transactions_api,
    system_api
]

def register_resources(api: Api):
    """
    Register all REST API resources with the provided API instance.
    
    Args:
        api: The Flask-RESTX API instance
    """
    for resource in api_resources:
        api.add_namespace(resource) 