#!/usr/bin/env python3
"""
Main application file for the day-trader-v1 application.
"""
import os
from app.database import setup_database, check_and_update_schema
from app.models.stock_service_model import StockService
from app.models.stock_transaction_model import StockTransaction

def initialize_application():
    """Initialize the application, including database setup."""
    print("Initializing day-trader-v1 application...")
    
    # Determine if we should reset the database (in development)
    # For production, this would be set to False
    reset_db = os.environ.get('RESET_DB', 'True').lower() in ('true', '1', 't')
    
    # Setup database - this will also update the database.sql file if needed
    engine = setup_database(reset_on_startup=reset_db)
    
    print("Application initialization complete.")
    return engine

def main():
    """Main application entry point."""
    engine = initialize_application()
    
    # Start your application logic here
    # For now, just print a success message
    print("Day-trader-v1 application is ready!")
    
    # Your actual application code would go here
    # ...

if __name__ == "__main__":
    main()
