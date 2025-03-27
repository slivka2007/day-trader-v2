"""
Services package for the Day Trader application.

This package contains service modules that provide application-wide functionality
that is not tied to a specific model or resource.
"""
from app.services.events import EventService

__all__ = ['EventService'] 