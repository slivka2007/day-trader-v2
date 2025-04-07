"""API resources for the Day Trader application.

This package contains REST API resources using Flask-RESTX.
"""

# Common imports for resources
from flask import current_app, request
from flask_restx import Api, Namespace, Resource, abort, fields

# Import all resources
from app.api.resources.auth import api as auth_api
from app.api.resources.daily_prices import api as daily_prices_api
from app.api.resources.intraday_prices import api as intraday_prices_api
from app.api.resources.stocks import api as stocks_api
from app.api.resources.system import api as system_api
from app.api.resources.trading_services import api as trading_services_api
from app.api.resources.trading_transactions import api as trading_transactions_api
from app.api.resources.users import ns as users_api
from app.services.session_manager import SessionManager

# Make common imports available
__all__: list[str] = [
    "Namespace",
    "Resource",
    "SessionManager",
    "abort",
    "api_resources",
    "current_app",
    "fields",
    "register_resources",
    "request",
]

# Create an aggregated list of resources for easy importing
api_resources: list[Namespace] = [
    stocks_api,
    daily_prices_api,
    intraday_prices_api,
    trading_services_api,
    trading_transactions_api,
    system_api,
    auth_api,
    users_api,
]


def register_resources(api: Api) -> None:
    """Register all REST API resources with the provided API instance.

    Args:
        api: The Flask-RESTX API instance

    """
    for resource in api_resources:
        api.add_namespace(resource)
