"""
Stock service for managing Stock model operations.

This service encapsulates all database interactions for the Stock model,
providing a clean API for stock management operations.
"""
import logging
from typing import Optional, List, Dict, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.stock import Stock
from app.utils.errors import ValidationError, ResourceNotFoundError, BusinessLogicError
from app.utils.current_datetime import get_current_datetime
from app.api.schemas.stock import stock_schema, stocks_schema

# Set up logging
logger = logging.getLogger(__name__)

class StockService:
    """Service for Stock model operations."""
    
    # Read operations
    @staticmethod
    def find_by_symbol(session: Session, symbol: str) -> Optional[Stock]:
        """
        Find a stock by symbol.
        
        Args:
            session: Database session
            symbol: Stock symbol to search for (case-insensitive)
            
        Returns:
            Stock instance if found, None otherwise
        """
        if not symbol:
            return None
            
        return Stock.get_by_symbol(session, symbol)
    
    @staticmethod
    def find_by_symbol_or_404(session: Session, symbol: str) -> Stock:
        """
        Find a stock by symbol or raise ResourceNotFoundError.
        
        Args:
            session: Database session
            symbol: Stock symbol to search for (case-insensitive)
            
        Returns:
            Stock instance
            
        Raises:
            ResourceNotFoundError: If stock not found
        """
        stock = StockService.find_by_symbol(session, symbol)
        if not stock:
            raise ResourceNotFoundError('Stock', f"symbol '{symbol.upper()}'")
        return stock
    
    @staticmethod
    def get_by_id(session: Session, stock_id: int) -> Optional[Stock]:
        """
        Get a stock by ID.
        
        Args:
            session: Database session
            stock_id: Stock ID to retrieve
            
        Returns:
            Stock instance if found, None otherwise
        """
        return Stock.get_by_id(session, stock_id)
    
    @staticmethod
    def get_or_404(session: Session, stock_id: int) -> Stock:
        """
        Get a stock by ID or raise ResourceNotFoundError.
        
        Args:
            session: Database session
            stock_id: Stock ID to retrieve
            
        Returns:
            Stock instance
            
        Raises:
            ResourceNotFoundError: If stock not found
        """
        stock = StockService.get_by_id(session, stock_id)
        if not stock:
            raise ResourceNotFoundError(f"Stock with ID {stock_id} not found")
        return stock
    
    @staticmethod
    def get_all(session: Session) -> List[Stock]:
        """
        Get all stocks.
        
        Args:
            session: Database session
            
        Returns:
            List of Stock instances
        """
        return Stock.get_all(session)
    
    # Write operations
    @staticmethod
    def create_stock(session: Session, data: Dict[str, Any]) -> Stock:
        """
        Create a new stock.
        
        Args:
            session: Database session
            data: Stock data dictionary
            
        Returns:
            Created stock instance
            
        Raises:
            ValidationError: If required fields are missing or invalid
        """
        from app.services.events import EventService
        
        try:
            # Validate required fields
            if 'symbol' not in data or not data['symbol']:
                raise ValidationError("Stock symbol is required")
                
            # Check if symbol already exists
            existing = StockService.find_by_symbol(session, data['symbol'])
            if existing:
                raise ValidationError(f"Stock with symbol '{data['symbol'].upper()}' already exists")
            
            # Ensure symbol is uppercase
            if 'symbol' in data:
                data['symbol'] = data['symbol'].upper()
            
            # Create stock instance
            stock = Stock.from_dict(data)
            session.add(stock)
            session.commit()
            
            # Prepare response data
            stock_data = stock_schema.dump(stock)
            
            # Emit WebSocket event
            EventService.emit_stock_update(
                action='created',
                stock_data=stock_data,
                stock_symbol=stock.symbol
            )
            
            return stock
        except Exception as e:
            logger.error(f"Error creating stock: {str(e)}")
            session.rollback()
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Could not create stock: {str(e)}")
    
    @staticmethod
    def update_stock(session: Session, stock: Stock, data: Dict[str, Any]) -> Stock:
        """
        Update stock attributes.
        
        Args:
            session: Database session
            stock: Stock instance to update
            data: Dictionary of attributes to update
            
        Returns:
            Updated stock instance
            
        Raises:
            ValidationError: If invalid data is provided
        """
        from app.services.events import EventService
        
        try:
            # Define which fields can be updated
            allowed_fields = {
                'name', 'is_active', 'sector', 'description'
            }
            
            # Don't allow symbol to be updated
            if 'symbol' in data:
                del data['symbol']
            
            # Use the model's update_from_data method
            updated = stock.update_from_data(data, allowed_fields)
            
            # Only emit event if something was updated
            if updated:
                stock.updated_at = get_current_datetime()
                session.commit()
                
                # Prepare response data
                stock_data = stock_schema.dump(stock)
                
                # Emit WebSocket event
                EventService.emit_stock_update(
                    action='updated',
                    stock_data=stock_data,
                    stock_symbol=stock.symbol
                )
            
            return stock
        except Exception as e:
            logger.error(f"Error updating stock: {str(e)}")
            session.rollback()
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Could not update stock: {str(e)}")
    
    @staticmethod
    def change_active_status(session: Session, stock: Stock, is_active: bool) -> Stock:
        """
        Change the active status of the stock.
        
        Args:
            session: Database session
            stock: Stock instance
            is_active: New active status
            
        Returns:
            Updated stock instance
        """
        from app.services.events import EventService
        
        try:
            # Only update if status is changing
            if stock.is_active != is_active:
                stock.is_active = is_active
                stock.updated_at = get_current_datetime()
                session.commit()
                
                # Prepare response data
                stock_data = stock_schema.dump(stock)
                
                # Emit WebSocket event
                EventService.emit_stock_update(
                    action='status_changed',
                    stock_data=stock_data,
                    stock_symbol=stock.symbol
                )
            
            return stock
        except Exception as e:
            logger.error(f"Error changing stock active status: {str(e)}")
            session.rollback()
            raise ValidationError(f"Could not change stock active status: {str(e)}")
    
    @staticmethod
    def toggle_active(session: Session, stock: Stock) -> Stock:
        """
        Toggle stock active status.
        
        Args:
            session: Database session
            stock: Stock instance
            
        Returns:
            Updated stock instance
        """
        return StockService.change_active_status(session, stock, not stock.is_active)
    
    @staticmethod
    def delete_stock(session: Session, stock: Stock) -> bool:
        """
        Delete a stock.
        
        Args:
            session: Database session
            stock: Stock to delete
            
        Returns:
            True if successful
            
        Raises:
            BusinessLogicError: If stock cannot be deleted due to dependencies
        """
        from app.services.events import EventService
        
        try:
            # Check dependencies using the model's method
            if stock.has_dependencies():
                if stock.services and len(stock.services) > 0:
                    raise BusinessLogicError(f"Cannot delete stock '{stock.symbol}' because it is used by trading services")
                
                if stock.transactions and len(stock.transactions) > 0:
                    raise BusinessLogicError(f"Cannot delete stock '{stock.symbol}' because it has associated transactions")
            
            symbol = stock.symbol
            stock_id = stock.id
            session.delete(stock)
            session.commit()
            
            # Emit WebSocket event
            EventService.emit_stock_update(
                action='deleted',
                stock_data={'id': stock_id, 'symbol': symbol},
                stock_symbol=symbol
            )
            
            return True
        except Exception as e:
            logger.error(f"Error deleting stock: {str(e)}")
            session.rollback()
            if isinstance(e, BusinessLogicError):
                raise
            raise BusinessLogicError(f"Could not delete stock: {str(e)}")
    
    @staticmethod
    def get_latest_price(stock: Stock) -> Optional[float]:
        """
        Get the latest price for a stock.
        
        Args:
            stock: Stock instance
            
        Returns:
            Latest closing price if available, None otherwise
        """
        return stock.get_latest_price()
        
    @staticmethod
    def search_stocks(session: Session, query: str, limit: int = 10) -> List[Stock]:
        """
        Search stocks by symbol or name.
        
        Args:
            session: Database session
            query: Search query string
            limit: Maximum number of results to return
            
        Returns:
            List of matching Stock instances
        """
        return Stock.search_stocks(session, query, limit)
