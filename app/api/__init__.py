"""REST API package for the Day Trader application.

This package contains all the API resources, models, and schemas for the application.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Query

from flask import Blueprint, Flask, request
from flask_restx import Api
from flask_restx.errors import ValidationError
from flask_socketio import SocketIO

from app.api.resources import register_resources

# Create API blueprint
api_bp: Blueprint = Blueprint("api", __name__, url_prefix="/api/v1")

# Initialize Flask-RESTX API
api: Api = Api(
    api_bp,
    version="1.0",
    title="Day Trader API",
    description="RESTful API for the Day Trader application",
    doc="/docs",
    validate=True,
    authorizations={
        "Bearer Auth": {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": "Add a JWT with ** Bearer &lt;JWT&gt; ** to authorize",
        },
    },
    security="Bearer Auth",
)


# Pagination and filtering utilities
def apply_pagination(query: Query, default_page_size: int = 20) -> dict:
    """Apply pagination to a SQLAlchemy query.

    Args:
        query: The SQLAlchemy query to paginate
        default_page_size: Default page size if not specified

    Returns:
        dict: Contains paginated results and metadata

    """
    page: int = request.args.get("page", 1, type=int)
    page_size: int = request.args.get("page_size", default_page_size, type=int)

    # Limit page size to avoid overloading
    page_size = min(page_size, 100)

    # Calculate offset
    offset: int = (page - 1) * page_size

    # Execute query with limits
    items: list[any] = query.limit(page_size).offset(offset).all()

    # Get total count for metadata
    total: int = query.order_by(None).count()
    total_pages: int = (total + page_size - 1) // page_size

    # Create pagination metadata
    pagination: dict[str, any] = {
        "page": page,
        "page_size": page_size,
        "total_items": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }

    return {"items": items, "pagination": pagination}


def _apply_range_filter(
    query: Query,
    model: any,
    key: str,
    value: any,
    suffix: str,
) -> Query:
    """Apply range-based filters (min, max, before, after)."""
    base_key: str = key[: -len(suffix)]
    if hasattr(model, base_key):
        column: any = getattr(model, base_key)
        if suffix in ("_min", "_after"):
            return query.filter(column >= value)
        if suffix in ("_max", "_before"):
            return query.filter(column <= value)
    return query


def _apply_like_filter(query: Query, model: any, key: str, value: any) -> Query:
    """Apply LIKE filter for text search."""
    base_key: str = key[:-5]  # Remove '_like' suffix
    if hasattr(model, base_key):
        column: any = getattr(model, base_key)
        return query.filter(column.ilike(f"%{value}%"))
    return query


def _apply_sorting(
    query: Query,
    model: any,
    sort_column: str | None,
    sort_order: str,
) -> Query:
    """Apply sorting to query."""
    if sort_column and hasattr(model, sort_column):
        column: any = getattr(model, sort_column)
        if sort_order.lower() == "desc":
            column = column.desc()
        return query.order_by(column)
    return query


def apply_filters(query: Query, model: any, filter_args: dict | None = None) -> Query:
    """Apply filters to a SQLAlchemy query based on request arguments."""
    filters: dict[str, any] = filter_args or request.args

    for key, value in filters.items():
        if key in ["page", "page_size", "sort", "order"]:
            continue

        if not hasattr(model, key):
            continue

        if key.endswith(("_min", "_max", "_after", "_before")):
            query = _apply_range_filter(
                query,
                model,
                key,
                value,
                key[-4:]
                if key.endswith(("_min", "_max"))
                else key[-6:]
                if key.endswith("_after")
                else key[-7:],
            )
        elif key.endswith("_like"):
            query = _apply_like_filter(query, model, key, value)
        else:
            column = getattr(model, key)
            query = query.filter(column == value)

    return _apply_sorting(
        query,
        model,
        request.args.get("sort"),
        request.args.get("order", "asc"),
    )


register_resources(api)


# Register error handlers
@api_bp.errorhandler(ValidationError)
def handle_validation_error(error: ValidationError) -> tuple[dict[str, str], int]:
    """Handle Schema validation errors."""
    return {"message": str(error)}, 400


@api_bp.errorhandler(404)
def handle_not_found(error: any) -> tuple[dict[str, str], int]:
    """Handle 404 errors."""
    return {"message": error.description}, 404


@api_bp.errorhandler(401)
def handle_unauthorized(error: any) -> tuple[dict[str, str], int]:
    """Handle 401 errors."""
    return {"message": error.description}, 401


# Initialize WebSockets for real-time updates
socketio: SocketIO = SocketIO(cors_allowed_origins="*")


def init_websockets(app: Flask) -> SocketIO:
    """Initialize WebSocket handlers."""
    from app.api.sockets import register_handlers

    socketio.init_app(app)
    register_handlers(socketio)
    app.socketio = socketio  # Store reference in app for easy access
    return socketio


__all__: list[str] = [
    "api",
    "api_bp",
    "apply_filters",
    "apply_pagination",
    "init_websockets",
    "socketio",
]
