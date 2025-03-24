import os
import re
from pathlib import Path
from typing import List, Optional, Tuple, Union, Dict, Any
from sqlalchemy import create_engine, inspect, Engine
from sqlalchemy.orm import sessionmaker, scoped_session, Session as SQLAlchemySession
from sqlalchemy.schema import CreateTable

# Import Base from the shared location
from database.models import Base

# Import models to ensure they're registered with the Base metadata
from database.models.stock_model import Stock
from database.models.daily_price_model import DailyPrice
from database.models.intraday_price_model import IntradayPrice
from database.models.stock_service_model import StockService
from database.models.stock_transaction_model import StockTransaction

# SQLite database path
DATABASE_URL: str = os.environ.get('DATABASE_URL', 'sqlite:///database/daytrader.db')
SQL_FILE_PATH: Path = Path(__file__).parent.parent / 'database.sql'

# Create engine
engine: Engine = create_engine(DATABASE_URL)

# Create session factory
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)

def generate_sql_schema() -> str:
    """Generate SQL DDL statements from SQLAlchemy models
    
    Returns:
        str: The SQL schema DDL statements
    """
    sql_statements: List[str] = []
    
    # Generate CREATE TABLE statements for all models
    for table in Base.metadata.sorted_tables:
        create_stmt = str(CreateTable(table).compile(engine))
        # Add IF NOT EXISTS to make it safer
        create_stmt = create_stmt.replace('CREATE TABLE', 'CREATE TABLE IF NOT EXISTS')
        sql_statements.append(create_stmt + ';')
    
    # Add index creation statements
    sql_statements.append('\n-- Create indexes for better performance')
    sql_statements.append('CREATE INDEX IF NOT EXISTS idx_stock_transactions_service_id ON stock_transactions(service_id);')
    sql_statements.append('CREATE INDEX IF NOT EXISTS idx_stock_services_symbol ON stock_services(stock_symbol);')
    sql_statements.append('CREATE INDEX IF NOT EXISTS idx_stock_services_state ON stock_services(service_state);')
    
    return '\n\n'.join(sql_statements)

def save_sql_schema() -> str:
    """Generate and save SQL schema to database.sql file
    
    Returns:
        str: The SQL schema that was saved
    """
    sql_schema: str = generate_sql_schema()
    
    SQL_FILE_PATH.write_text(sql_schema)
    
    print(f"SQL schema saved to {SQL_FILE_PATH}")
    return sql_schema

def compare_sql_schema() -> bool:
    """Compare existing SQL schema file with current models.
    
    Returns:
        bool: True if schemas match, False if they don't or file doesn't exist
    """
    if not SQL_FILE_PATH.exists():
        print(f"SQL file {SQL_FILE_PATH} does not exist")
        return False
    
    # Read existing SQL schema
    existing_schema: str = SQL_FILE_PATH.read_text()
    
    # Generate current schema from models
    current_schema: str = generate_sql_schema()
    
    # Normalize schemas for comparison (remove whitespace, case insensitive)
    def normalize_schema(schema: str) -> str:
        # Remove comments
        schema = re.sub(r'--.*?\n', '\n', schema)
        # Remove extra whitespace
        schema = re.sub(r'\s+', ' ', schema)
        # Lowercase
        schema = schema.lower().strip()
        return schema
    
    existing_norm: str = normalize_schema(existing_schema)
    current_norm: str = normalize_schema(current_schema)
    
    # Compare normalized schemas
    if existing_norm == current_norm:
        print("SQL schema matches current models")
        return True
    else:
        print("SQL schema does not match current models")
        return False

def init_db(reset: bool = True) -> Engine:
    """Initialize the database, optionally resetting it first.
    
    Args:
        reset: If True, drops all tables before creating them.
        
    Returns:
        Engine: SQLAlchemy engine instance
    """
    if reset:
        Base.metadata.drop_all(engine)
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    # Generate and save SQL schema
    save_sql_schema()
    
    print(f"Database initialized at {DATABASE_URL}")
    if reset:
        print("All existing data has been reset.")
    
    return engine

def get_session() -> SQLAlchemySession:
    """Get a new database session.
    
    Returns:
        SQLAlchemySession: A new SQLAlchemy session
    """
    return Session()

def check_and_update_schema() -> bool:
    """Check if SQL schema matches models and update if needed
    
    Returns:
        bool: True if schema check/update succeeded
    """
    if not compare_sql_schema():
        print("Updating SQL schema file")
        save_sql_schema()
        
    # Always ensure database tables exist
    Base.metadata.create_all(engine)
    return True

# Function to be called in app startup
def setup_database(reset_on_startup: bool = True) -> Engine:
    """Setup database during application startup
    
    Args:
        reset_on_startup: Whether to reset the database on startup
        
    Returns:
        Engine: SQLAlchemy engine instance
    """
    if reset_on_startup:
        init_db(reset=True)
    else:
        check_and_update_schema()
    return engine 