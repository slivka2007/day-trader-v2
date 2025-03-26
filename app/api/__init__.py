"""
REST API package for the Day Trader application.

This package contains all the API resources, models, and schemas for the application.
"""
from flask import Blueprint, request
from flask_restx import Api
from sqlalchemy.orm import Query

# Create API blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Initialize Flask-RESTX API
api = Api(
    api_bp, 
    version='1.0',
    title='Day Trader API',
    description='REST API for the Day Trader stock trading application',
    doc='/docs',
    validate=True,
    authorizations={
        'jwt': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization',
            'description': 'Standard JWT authorization header using Bearer scheme. Example: "Bearer {token}"'
        }
    },
    security='jwt'
)

# Pagination and filtering utilities
def apply_pagination(query: Query, default_page_size: int = 20):
    """
    Apply pagination to a SQLAlchemy query.
    
    Args:
        query: The SQLAlchemy query to paginate
        default_page_size: Default page size if not specified
        
    Returns:
        dict: Contains paginated results and metadata
    """
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', default_page_size, type=int)
    
    # Limit page size to avoid overloading
    if page_size > 100:
        page_size = 100
    
    # Calculate offset
    offset = (page - 1) * page_size
    
    # Execute query with limits
    items = query.limit(page_size).offset(offset).all()
    
    # Get total count for metadata
    total = query.order_by(None).count()
    total_pages = (total + page_size - 1) // page_size
    
    # Create pagination metadata
    pagination = {
        'page': page,
        'page_size': page_size,
        'total_items': total,
        'total_pages': total_pages,
        'has_next': page < total_pages,
        'has_prev': page > 1
    }
    
    return {
        'items': items,
        'pagination': pagination
    }

def apply_filters(query: Query, model, filter_args=None):
    """
    Apply filters to a SQLAlchemy query based on request arguments.
    
    Args:
        query: The SQLAlchemy query to filter
        model: The model class being queried
        filter_args: Optional dictionary of filter arguments
        
    Returns:
        Query: Filtered SQLAlchemy query
    """
    # Use request args if no filter_args provided
    filters = filter_args or request.args
    
    # Apply filters for columns that exist in the model
    for key, value in filters.items():
        # Skip pagination and sorting parameters
        if key in ['page', 'page_size', 'sort', 'order']:
            continue
            
        # Check if the column exists in the model
        if hasattr(model, key):
            column = getattr(model, key)
            
            # Special handling for specific filters
            if key.endswith('_min'):
                base_key = key[:-4]  # Remove '_min' suffix
                if hasattr(model, base_key):
                    column = getattr(model, base_key)
                    query = query.filter(column >= value)
            elif key.endswith('_max'):
                base_key = key[:-4]  # Remove '_max' suffix
                if hasattr(model, base_key):
                    column = getattr(model, base_key)
                    query = query.filter(column <= value)
            elif key.endswith('_after'):
                base_key = key[:-6]  # Remove '_after' suffix
                if hasattr(model, base_key):
                    column = getattr(model, base_key)
                    query = query.filter(column >= value)
            elif key.endswith('_before'):
                base_key = key[:-7]  # Remove '_before' suffix
                if hasattr(model, base_key):
                    column = getattr(model, base_key)
                    query = query.filter(column <= value)
            elif key.endswith('_like'):
                base_key = key[:-5]  # Remove '_like' suffix
                if hasattr(model, base_key):
                    column = getattr(model, base_key)
                    query = query.filter(column.ilike(f'%{value}%'))
            else:
                # Default exact match
                query = query.filter(column == value)
    
    # Apply sorting if requested
    sort_column = request.args.get('sort')
    sort_order = request.args.get('order', 'asc')
    
    if sort_column and hasattr(model, sort_column):
        column = getattr(model, sort_column)
        if sort_order.lower() == 'desc':
            column = column.desc()
        query = query.order_by(column)
    
    return query

# Import and register namespaces
from app.api.resources.stocks import api as stocks_ns
from app.api.resources.stock_prices import api as prices_ns
from app.api.resources.trading_services import api as services_ns
from app.api.resources.trading_transactions import api as transactions_ns
from app.api.resources.system import api as system_ns
from app.api.auth import api as auth_ns

# Add namespaces to the API
api.add_namespace(stocks_ns)
api.add_namespace(prices_ns)
api.add_namespace(services_ns)
api.add_namespace(transactions_ns)
api.add_namespace(system_ns)
api.add_namespace(auth_ns)

__all__ = ['api_bp', 'api', 'apply_pagination', 'apply_filters'] 