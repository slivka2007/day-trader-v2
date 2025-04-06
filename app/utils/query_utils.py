"""Query utilities for database operations.

This module provides utility functions for common query operations like pagination and
filtering.
"""

from __future__ import annotations

from typing import Callable, TypeVar

from flask import request
from sqlalchemy import Column, asc, desc, select

from app.utils.constants import PaginationConstants

T = TypeVar("T")


def apply_pagination(
    query: select,
    page: int = 1,
    per_page: int = PaginationConstants.DEFAULT_PER_PAGE,
) -> dict[str, any]:
    """Apply pagination to a SQLAlchemy select statement or a Python list.

    Args:
        query: The SQLAlchemy select statement or Python list to paginate
        page: Page number for pagination
        per_page: Number of items per page

    Returns:
        dict: Contains paginated results and metadata

    """
    # Limit page size to avoid overloading
    per_page = min(per_page, PaginationConstants.MAX_PER_PAGE)

    # Handle Python list
    if isinstance(query, list):
        # Calculate start and end indices
        start: int = (page - 1) * per_page
        end: int = start + per_page

        # Get total count for metadata
        total: int = len(query)
        total_pages: int = (total + per_page - 1) // per_page if total > 0 else 0

        # Get items for current page
        items: list[any] = query[start:end]
    else:
        # For SQLAlchemy select statements
        # Create a copy of the query for count
        count_query = query

        # Apply pagination to the original query
        paginated_query = query.limit(per_page).offset((page - 1) * per_page)

        # This function should be called from within a session context
        # The actual execution of these queries should happen in the service layer
        return {
            "query": paginated_query,
            "count_query": count_query,
            "page": page,
            "per_page": per_page,
        }

    # Create pagination metadata for list case
    pagination: dict[str, any] = {
        "page": page,
        "per_page": per_page,
        "total_items": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }

    return {"items": items, "pagination": pagination}


def _apply_range_filter(
    query: select,
    model_column: Column,
    value: any,
    operation: str,
) -> select:
    """Apply range-based filters (min, max, before, after)."""
    # Don't apply filter if value is None
    if value is None:
        return query

    if operation in ("min", "after"):
        return query.where(model_column >= value)
    if operation in ("max", "before"):
        return query.where(model_column <= value)
    return query


def _apply_like_filter(query: select, model_column: Column, value: str) -> select:
    """Apply LIKE filter for text search."""
    return query.where(model_column.ilike(f"%{value}%"))


def _apply_sorting(
    query: select,
    model_column: Column | None,
    sort_order: str,
) -> select:
    """Apply sorting to query."""
    if model_column:
        order_func: Callable = desc if sort_order.lower() == "desc" else asc
        return query.order_by(order_func(model_column))
    return query


def _process_special_key(
    query: select,
    model: any,
    key: str,
    value: any,
) -> select:
    """Process keys with special suffixes (_min, _max, etc.)."""
    base_key = None
    operation = None

    if key.endswith(("_min", "_max")):
        base_key: str = key[:-4]  # Remove '_min' or '_max' suffix
        operation: str = key[-3:]  # Get 'min' or 'max'
    elif key.endswith("_after"):
        base_key: str = key[:-6]  # Remove '_after' suffix
        operation = "after"
    elif key.endswith("_before"):
        base_key: str = key[:-7]  # Remove '_before' suffix
        operation: str = "before"
    elif key.endswith("_like"):
        base_key: str = key[:-5]  # Remove '_like' suffix
        operation: str = "like"

    if base_key and hasattr(model, base_key):
        column: Column = getattr(model, base_key)
        if operation in ("min", "max", "after", "before"):
            return _apply_range_filter(query, column, value, operation)
        if operation == "like":
            return _apply_like_filter(query, column, value)

    return query


def apply_filters(
    query: select,
    model: any,
    filter_args: dict[str, any] | None = None,
) -> select:
    """Apply filters to a SQLAlchemy select statement based on request arguments."""
    filters: dict[str, any] = filter_args or request.args

    for key, value in filters.items():
        # Skip pagination and sorting params
        if key in ["page", "page_size", "sort", "order"]:
            continue

        # Skip None values
        if value is None:
            continue

        if hasattr(model, key):
            # Direct column match
            column: Column = getattr(model, key)
            query = query.where(column == value)
        else:
            # Try processing as a special key
            query = _process_special_key(query, model, key, value)

    # Apply sorting if requested
    sort_column: str | None = request.args.get("sort")
    if sort_column and hasattr(model, sort_column):
        column: Column = getattr(model, sort_column)
        query = _apply_sorting(
            query,
            column,
            request.args.get("order", "asc"),
        )

    return query
