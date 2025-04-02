"""Datetime utility functions for consistent timezone handling.

This module provides standardized datetime functions to ensure all datetime
operations use a consistent timezone throughout the application.
"""

import datetime

import pytz

# Define the EST timezone
TIMEZONE: pytz.timezone = pytz.timezone("America/New_York")


def get_current_datetime() -> datetime.datetime:
    """Get the current datetime in the application's timezone.

    Returns:
        datetime: Current datetime object with timezone information

    """
    return datetime.datetime.now(TIMEZONE)


def get_current_date() -> datetime.date:
    """Get the current date in the application's timezone.

    Returns:
        date: Current date object

    """
    return get_current_datetime().date()


def get_current_time() -> datetime.time:
    """Get the current time in the application's timezone.

    Returns:
        time: Current time object

    """
    return get_current_datetime().time()
