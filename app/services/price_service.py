"""
Price service for managing StockDailyPrice and StockIntradayPrice model operations.

This service encapsulates all database interactions for the price models,
providing a clean API for stock price data management operations.
"""
import logging
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.models.stock_daily_price import StockDailyPrice
from app.models.stock_intraday_price import StockIntradayPrice
from app.models.stock import Stock
from app.models.enums import PriceSource
from app.utils.errors import ValidationError, ResourceNotFoundError, BusinessLogicError
from app.utils.current_datetime import get_current_datetime, get_current_date
from app.api.schemas.stock_price import (
    daily_price_schema, 
    daily_prices_schema,
    intraday_price_schema,
    intraday_prices_schema
)

# Set up logging
logger = logging.getLogger(__name__)

class PriceService:
    """Service for stock price model operations."""
    
    #
    # Daily Price Operations
    #
    
    # Read operations
    @staticmethod
    def get_daily_price_by_id(session: Session, price_id: int) -> Optional[StockDailyPrice]:
        """
        Get a daily price record by ID.
        
        Args:
            session: Database session
            price_id: Price record ID to retrieve
            
        Returns:
            StockDailyPrice instance if found, None otherwise
        """
        return StockDailyPrice.get_by_id(session, price_id)
    
    @staticmethod
    def get_daily_price_or_404(session: Session, price_id: int) -> StockDailyPrice:
        """
        Get a daily price record by ID or raise ResourceNotFoundError.
        
        Args:
            session: Database session
            price_id: Price record ID to retrieve
            
        Returns:
            StockDailyPrice instance
            
        Raises:
            ResourceNotFoundError: If price record not found
        """
        price = PriceService.get_daily_price_by_id(session, price_id)
        if not price:
            raise ResourceNotFoundError(f"Daily price record with ID {price_id} not found")
        return price
    
    @staticmethod
    def get_daily_price_by_date(session: Session, stock_id: int, price_date: date) -> Optional[StockDailyPrice]:
        """
        Get a daily price record by stock ID and date.
        
        Args:
            session: Database session
            stock_id: Stock ID
            price_date: Date of the price record
            
        Returns:
            StockDailyPrice instance if found, None otherwise
        """
        return StockDailyPrice.get_by_date(session, stock_id, price_date)
    
    @staticmethod
    def get_daily_prices_by_date_range(session: Session, stock_id: int, 
                             start_date: date, end_date: date = None) -> List[StockDailyPrice]:
        """
        Get daily price records for a date range.
        
        Args:
            session: Database session
            stock_id: Stock ID
            start_date: Start date (inclusive)
            end_date: End date (inclusive), defaults to today
            
        Returns:
            List of StockDailyPrice instances
        """
        return StockDailyPrice.get_by_date_range(session, stock_id, start_date, end_date)
    
    @staticmethod
    def get_latest_daily_prices(session: Session, stock_id: int, days: int = 30) -> List[StockDailyPrice]:
        """
        Get the latest daily price records for a stock.
        
        Args:
            session: Database session
            stock_id: Stock ID
            days: Number of days to look back
            
        Returns:
            List of StockDailyPrice instances, most recent first
        """
        return StockDailyPrice.get_latest_prices(session, stock_id, days)
    
    # Write operations
    @staticmethod
    def create_daily_price(session: Session, stock_id: int, price_date: date, data: Dict[str, Any]) -> StockDailyPrice:
        """
        Create a new daily price record.
        
        Args:
            session: Database session
            stock_id: Stock ID
            price_date: Date of the price record
            data: Price data
            
        Returns:
            Created StockDailyPrice instance
            
        Raises:
            ValidationError: If required data is missing or invalid
            ResourceNotFoundError: If stock not found
            BusinessLogicError: For other business logic errors
        """
        from app.services.events import EventService
        
        try:
            # Verify stock exists
            stock = Stock.get_by_id(session, stock_id)
            if not stock:
                raise ResourceNotFoundError(f"Stock with ID {stock_id} not found")
                
            # Check if price already exists for this date
            existing = PriceService.get_daily_price_by_date(session, stock_id, price_date)
            if existing:
                raise ValidationError(f"Price record already exists for stock ID {stock_id} on {price_date}")
            
            # Create the daily price record using the model's method
            price_record = StockDailyPrice.create_price(
                session=session,
                stock_id=stock_id,
                price_date=price_date,
                data=data
            )
            
            # Prepare response data
            price_data = daily_price_schema.dump(price_record)
            
            # Emit WebSocket event
            EventService.emit_price_update(
                action='created',
                price_data=price_data,
                stock_symbol=stock.symbol
            )
            
            return price_record
            
        except ValueError as e:
            # Convert ValueError from model to ValidationError for API consistency
            logger.error(f"Validation error creating daily price: {str(e)}")
            session.rollback()
            raise ValidationError(str(e))
        except ResourceNotFoundError:
            session.rollback()
            raise
        except Exception as e:
            logger.error(f"Error creating daily price: {str(e)}")
            session.rollback()
            raise BusinessLogicError(f"Could not create daily price record: {str(e)}")
    
    @staticmethod
    def update_daily_price(session: Session, price_id: int, data: Dict[str, Any]) -> StockDailyPrice:
        """
        Update a daily price record.
        
        Args:
            session: Database session
            price_id: Price record ID to update
            data: Updated price data
            
        Returns:
            Updated StockDailyPrice instance
            
        Raises:
            ResourceNotFoundError: If price record not found
            ValidationError: If invalid data is provided
            BusinessLogicError: For other business logic errors
        """
        from app.services.events import EventService
        
        try:
            # Get the price record
            price_record = PriceService.get_daily_price_or_404(session, price_id)
            
            # Update the price record using the model's method
            updated_record = price_record.update(session, data)
            
            # No need to emit event here as the model's update method already does it
            
            return updated_record
            
        except ValueError as e:
            # Convert ValueError from model to ValidationError for API consistency
            logger.error(f"Validation error updating daily price: {str(e)}")
            session.rollback()
            raise ValidationError(str(e))
        except ResourceNotFoundError:
            session.rollback()
            raise
        except Exception as e:
            logger.error(f"Error updating daily price: {str(e)}")
            session.rollback()
            raise BusinessLogicError(f"Could not update daily price record: {str(e)}")
    
    @staticmethod
    def delete_daily_price(session: Session, price_id: int) -> bool:
        """
        Delete a daily price record.
        
        Args:
            session: Database session
            price_id: Price record ID to delete
            
        Returns:
            True if successful
            
        Raises:
            ResourceNotFoundError: If price record not found
            BusinessLogicError: If price record cannot be deleted
        """
        from app.services.events import EventService
        
        try:
            # Get the price record
            price_record = PriceService.get_daily_price_or_404(session, price_id)
            
            # Get stock symbol for event
            stock_symbol = price_record.stock.symbol if price_record.stock else "unknown"
            
            # Check if this is recent data (within last 30 days)
            thirty_days_ago = get_current_date() - timedelta(days=30)
            if price_record.price_date >= thirty_days_ago:
                raise BusinessLogicError("Cannot delete recent price data (less than 30 days old). This data may be in use for active analyses.")
            
            # Delete the record
            session.delete(price_record)
            session.commit()
            
            # Emit WebSocket event
            EventService.emit_price_update(
                action='deleted',
                price_data={'id': price_id},
                stock_symbol=stock_symbol
            )
            
            return True
            
        except ResourceNotFoundError:
            session.rollback()
            raise
        except Exception as e:
            logger.error(f"Error deleting daily price: {str(e)}")
            session.rollback()
            raise BusinessLogicError(f"Could not delete daily price record: {str(e)}")
    
    #
    # Intraday Price Operations
    #
    
    # Read operations
    @staticmethod
    def get_intraday_price_by_id(session: Session, price_id: int) -> Optional[StockIntradayPrice]:
        """
        Get an intraday price record by ID.
        
        Args:
            session: Database session
            price_id: Price record ID to retrieve
            
        Returns:
            StockIntradayPrice instance if found, None otherwise
        """
        return StockIntradayPrice.get_by_id(session, price_id)
    
    @staticmethod
    def get_intraday_price_or_404(session: Session, price_id: int) -> StockIntradayPrice:
        """
        Get an intraday price record by ID or raise ResourceNotFoundError.
        
        Args:
            session: Database session
            price_id: Price record ID to retrieve
            
        Returns:
            StockIntradayPrice instance
            
        Raises:
            ResourceNotFoundError: If price record not found
        """
        price = PriceService.get_intraday_price_by_id(session, price_id)
        if not price:
            raise ResourceNotFoundError(f"Intraday price record with ID {price_id} not found")
        return price
    
    @staticmethod
    def get_intraday_price_by_timestamp(session: Session, stock_id: int, 
                               timestamp: datetime, interval: int = 1) -> Optional[StockIntradayPrice]:
        """
        Get an intraday price record by stock ID, timestamp, and interval.
        
        Args:
            session: Database session
            stock_id: Stock ID
            timestamp: Timestamp of the price record
            interval: Time interval in minutes (default: 1)
            
        Returns:
            StockIntradayPrice instance if found, None otherwise
        """
        return StockIntradayPrice.get_by_timestamp(session, stock_id, timestamp, interval)
    
    @staticmethod
    def get_intraday_prices_by_time_range(session: Session, stock_id: int, 
                           start_time: datetime, end_time: datetime = None, 
                           interval: int = 1) -> List[StockIntradayPrice]:
        """
        Get intraday price records for a time range.
        
        Args:
            session: Database session
            stock_id: Stock ID
            start_time: Start timestamp (inclusive)
            end_time: End timestamp (inclusive), defaults to current time
            interval: Time interval in minutes (default: 1)
            
        Returns:
            List of StockIntradayPrice instances
        """
        return StockIntradayPrice.get_by_time_range(session, stock_id, start_time, end_time, interval)
    
    @staticmethod
    def get_latest_intraday_prices(session: Session, stock_id: int, hours: int = 8, 
                          interval: int = 1) -> List[StockIntradayPrice]:
        """
        Get the latest intraday price records for a stock.
        
        Args:
            session: Database session
            stock_id: Stock ID
            hours: Number of hours to look back
            interval: Time interval in minutes
            
        Returns:
            List of StockIntradayPrice instances, most recent first
        """
        return StockIntradayPrice.get_latest_prices(session, stock_id, hours, interval)
    
    # Write operations
    @staticmethod
    def create_intraday_price(session: Session, stock_id: int, timestamp: datetime, 
                              interval: int, data: Dict[str, Any]) -> StockIntradayPrice:
        """
        Create a new intraday price record.
        
        Args:
            session: Database session
            stock_id: Stock ID
            timestamp: Timestamp of the price record
            interval: Time interval in minutes (1, 5, 15, 30, 60)
            data: Price data
            
        Returns:
            Created StockIntradayPrice instance
            
        Raises:
            ValidationError: If required data is missing or invalid
            ResourceNotFoundError: If stock not found
            BusinessLogicError: For other business logic errors
        """
        from app.services.events import EventService
        
        try:
            # Verify stock exists
            stock = Stock.get_by_id(session, stock_id)
            if not stock:
                raise ResourceNotFoundError(f"Stock with ID {stock_id} not found")
                
            # Check if price already exists for this timestamp and interval
            existing = PriceService.get_intraday_price_by_timestamp(session, stock_id, timestamp, interval)
            if existing:
                raise ValidationError(f"Price record already exists for stock ID {stock_id} at {timestamp} with interval {interval}")
            
            # Create the intraday price record using the model's method
            price_record = StockIntradayPrice.create_price(
                session=session,
                stock_id=stock_id,
                timestamp=timestamp,
                interval=interval,
                data=data
            )
            
            # Prepare response data
            price_data = intraday_price_schema.dump(price_record)
            
            # Emit WebSocket event
            EventService.emit_price_update(
                action='created',
                price_data=price_data,
                stock_symbol=stock.symbol
            )
            
            return price_record
            
        except ValueError as e:
            # Convert ValueError from model to ValidationError for API consistency
            logger.error(f"Validation error creating intraday price: {str(e)}")
            session.rollback()
            raise ValidationError(str(e))
        except ResourceNotFoundError:
            session.rollback()
            raise
        except Exception as e:
            logger.error(f"Error creating intraday price: {str(e)}")
            session.rollback()
            raise BusinessLogicError(f"Could not create intraday price record: {str(e)}")
    
    @staticmethod
    def update_intraday_price(session: Session, price_id: int, data: Dict[str, Any]) -> StockIntradayPrice:
        """
        Update an intraday price record.
        
        Args:
            session: Database session
            price_id: Price record ID to update
            data: Updated price data
            
        Returns:
            Updated StockIntradayPrice instance
            
        Raises:
            ResourceNotFoundError: If price record not found
            ValidationError: If invalid data is provided
            BusinessLogicError: For other business logic errors
        """
        from app.services.events import EventService
        
        try:
            # Get the price record
            price_record = PriceService.get_intraday_price_or_404(session, price_id)
            
            # Update the price record using the model's method
            updated_record = price_record.update(session, data)
            
            # No need to emit event here as the model's update method already does it
            
            return updated_record
            
        except ValueError as e:
            # Convert ValueError from model to ValidationError for API consistency
            logger.error(f"Validation error updating intraday price: {str(e)}")
            session.rollback()
            raise ValidationError(str(e))
        except ResourceNotFoundError:
            session.rollback()
            raise
        except Exception as e:
            logger.error(f"Error updating intraday price: {str(e)}")
            session.rollback()
            raise BusinessLogicError(f"Could not update intraday price record: {str(e)}")
    
    @staticmethod
    def delete_intraday_price(session: Session, price_id: int) -> bool:
        """
        Delete an intraday price record.
        
        Args:
            session: Database session
            price_id: Price record ID to delete
            
        Returns:
            True if successful
            
        Raises:
            ResourceNotFoundError: If price record not found
            BusinessLogicError: If price record cannot be deleted
        """
        from app.services.events import EventService
        
        try:
            # Get the price record
            price_record = PriceService.get_intraday_price_or_404(session, price_id)
            
            # Get stock symbol for event
            stock_symbol = price_record.stock.symbol if price_record.stock else "unknown"
            
            # Check if this is recent data (within last 7 days)
            seven_days_ago = get_current_date() - timedelta(days=7)
            if price_record.timestamp.date() >= seven_days_ago:
                raise BusinessLogicError("Cannot delete recent price data (less than 7 days old). This data may be in use for active analyses.")
            
            # Delete the record
            session.delete(price_record)
            session.commit()
            
            # Emit WebSocket event
            EventService.emit_price_update(
                action='deleted',
                price_data={'id': price_id},
                stock_symbol=stock_symbol
            )
            
            return True
            
        except ResourceNotFoundError:
            session.rollback()
            raise
        except Exception as e:
            logger.error(f"Error deleting intraday price: {str(e)}")
            session.rollback()
            raise BusinessLogicError(f"Could not delete intraday price record: {str(e)}")
    
    #
    # Bulk Operations
    #
    
    @staticmethod
    def bulk_import_daily_prices(session: Session, stock_id: int, price_data: List[Dict[str, Any]]) -> List[StockDailyPrice]:
        """
        Import multiple daily price records for a stock.
        
        Args:
            session: Database session
            stock_id: Stock ID
            price_data: List of price data dictionaries, each containing a 'price_date' field
            
        Returns:
            List of created StockDailyPrice instances
            
        Raises:
            ResourceNotFoundError: If stock not found
            ValidationError: If invalid data is provided
            BusinessLogicError: For other business logic errors
        """
        from app.services.events import EventService
        
        try:
            # Verify stock exists
            stock = Stock.get_by_id(session, stock_id)
            if not stock:
                raise ResourceNotFoundError(f"Stock with ID {stock_id} not found")
            
            created_records = []
            
            # Group commit to improve performance
            for data in price_data:
                # Extract and validate price date
                if 'price_date' not in data:
                    raise ValidationError("Missing 'price_date' in price data")
                
                price_date = data['price_date']
                if isinstance(price_date, str):
                    try:
                        price_date = datetime.strptime(price_date, '%Y-%m-%d').date()
                    except ValueError:
                        raise ValidationError(f"Invalid price_date format: {price_date}. Use YYYY-MM-DD")
                
                # Check if price already exists
                existing = PriceService.get_daily_price_by_date(session, stock_id, price_date)
                if existing:
                    logger.warning(f"Skipping existing price record for {stock.symbol} on {price_date}")
                    continue
                
                # Create price record
                try:
                    price_record = StockDailyPrice.create_price(
                        session=session,
                        stock_id=stock_id,
                        price_date=price_date,
                        data=data
                    )
                    created_records.append(price_record)
                except Exception as e:
                    logger.warning(f"Error creating price record for {stock.symbol} on {price_date}: {str(e)}")
                    # Continue processing other records instead of failing the entire batch
            
            # Commit all changes
            session.commit()
            
            # Emit batch update event
            if created_records:
                EventService.emit_price_update(
                    action='bulk_imported',
                    price_data={
                        'count': len(created_records),
                        'stock_id': stock_id,
                        'stock_symbol': stock.symbol
                    },
                    stock_symbol=stock.symbol
                )
            
            return created_records
            
        except Exception as e:
            logger.error(f"Error bulk importing daily prices: {str(e)}")
            session.rollback()
            if isinstance(e, (ResourceNotFoundError, ValidationError)):
                raise
            raise BusinessLogicError(f"Could not import daily price records: {str(e)}")
    
    @staticmethod
    def bulk_import_intraday_prices(session: Session, stock_id: int, price_data: List[Dict[str, Any]]) -> List[StockIntradayPrice]:
        """
        Import multiple intraday price records for a stock.
        
        Args:
            session: Database session
            stock_id: Stock ID
            price_data: List of price data dictionaries, each containing 'timestamp' and 'interval' fields
            
        Returns:
            List of created StockIntradayPrice instances
            
        Raises:
            ResourceNotFoundError: If stock not found
            ValidationError: If invalid data is provided
            BusinessLogicError: For other business logic errors
        """
        from app.services.events import EventService
        
        try:
            # Verify stock exists
            stock = Stock.get_by_id(session, stock_id)
            if not stock:
                raise ResourceNotFoundError(f"Stock with ID {stock_id} not found")
            
            created_records = []
            
            # Group commit to improve performance
            for data in price_data:
                # Extract and validate timestamp
                if 'timestamp' not in data:
                    raise ValidationError("Missing 'timestamp' in price data")
                
                timestamp = data['timestamp']
                if isinstance(timestamp, str):
                    try:
                        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    except ValueError:
                        raise ValidationError(f"Invalid timestamp format: {timestamp}. Use ISO format")
                
                # Extract and validate interval
                interval = data.get('interval', 1)
                if interval not in [1, 5, 15, 30, 60]:
                    raise ValidationError(f"Invalid interval: {interval}. Must be one of: 1, 5, 15, 30, 60")
                
                # Check if price already exists
                existing = PriceService.get_intraday_price_by_timestamp(session, stock_id, timestamp, interval)
                if existing:
                    logger.warning(f"Skipping existing price record for {stock.symbol} at {timestamp} (interval: {interval})")
                    continue
                
                # Create price record
                try:
                    price_record = StockIntradayPrice.create_price(
                        session=session,
                        stock_id=stock_id,
                        timestamp=timestamp,
                        interval=interval,
                        data=data
                    )
                    created_records.append(price_record)
                except Exception as e:
                    logger.warning(f"Error creating price record for {stock.symbol} at {timestamp}: {str(e)}")
                    # Continue processing other records instead of failing the entire batch
            
            # Commit all changes
            session.commit()
            
            # Emit batch update event
            if created_records:
                EventService.emit_price_update(
                    action='bulk_imported',
                    price_data={
                        'count': len(created_records),
                        'stock_id': stock_id,
                        'stock_symbol': stock.symbol
                    },
                    stock_symbol=stock.symbol
                )
            
            return created_records
            
        except Exception as e:
            logger.error(f"Error bulk importing intraday prices: {str(e)}")
            session.rollback()
            if isinstance(e, (ResourceNotFoundError, ValidationError)):
                raise
            raise BusinessLogicError(f"Could not import intraday price records: {str(e)}")
