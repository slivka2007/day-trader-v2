"""Query utilities for database operations.

This module provides utility functions for common query operations like pagination and
filtering.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Query

from flask import request

from app.utils.constants import PaginationConstants


def apply_pagination(
    query: list[any],
    default_page_size: int = PaginationConstants.DEFAULT_PER_PAGE,
) -> dict | list[any]:
    """Apply pagination to a SQLAlchemy query or a Python list.

    Args:
        query: The SQLAlchemy query or Python list to paginate
        default_page_size: Default page size if not specified

    Returns:
        dict: Contains paginated results and metadata

    """
    page: int = request.args.get("page", PaginationConstants.DEFAULT_PAGE, type=int)
    page_size: int = request.args.get("page_size", default_page_size, type=int)

    # Limit page size to avoid overloading
    page_size = min(page_size, PaginationConstants.MAX_PER_PAGE)

    # Handle Python list
    if isinstance(query, list):
        # Calculate start and end indices
        start: int = (page - 1) * page_size
        end: int = start + page_size

        # Get total count for metadata
        total: int = len(query)
        total_pages: int = (total + page_size - 1) // page_size

        # Get items for current page
        items: list[any] = query[start:end]

    # Handle SQLAlchemy Query
    else:
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


def apply_filters(
    query: Query | list[any],
    model: any,
    filter_args: dict | None = None,
) -> Query | list[any]:
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
