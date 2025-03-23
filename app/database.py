import os
import re
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.schema import CreateTable

# Import models to ensure they're registered with the Base metadata
from app.models.stock_service_model import Base, StockService
from app.models.stock_transaction_model import StockTransaction

# SQLite database path
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///daytrader.db')
SQL_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database.sql')

# Create engine
engine = create_engine(DATABASE_URL)

# Create session factory
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)

def generate_sql_schema():
    """Generate SQL DDL statements from SQLAlchemy models"""
    sql_statements = []
    
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

def save_sql_schema():
    """Generate and save SQL schema to database.sql file"""
    sql_schema = generate_sql_schema()
    
    with open(SQL_FILE_PATH, 'w') as f:
        f.write(sql_schema)
    
    print(f"SQL schema saved to {SQL_FILE_PATH}")
    return sql_schema

def compare_sql_schema():
    """Compare existing SQL schema file with current models.
    
    Returns:
        bool: True if schemas match, False if they don't or file doesn't exist
    """
    if not os.path.exists(SQL_FILE_PATH):
        print(f"SQL file {SQL_FILE_PATH} does not exist")
        return False
    
    # Read existing SQL schema
    with open(SQL_FILE_PATH, 'r') as f:
        existing_schema = f.read()
    
    # Generate current schema from models
    current_schema = generate_sql_schema()
    
    # Normalize schemas for comparison (remove whitespace, case insensitive)
    def normalize_schema(schema):
        # Remove comments
        schema = re.sub(r'--.*?\n', '\n', schema)
        # Remove extra whitespace
        schema = re.sub(r'\s+', ' ', schema)
        # Lowercase
        schema = schema.lower().strip()
        return schema
    
    existing_norm = normalize_schema(existing_schema)
    current_norm = normalize_schema(current_schema)
    
    # Compare normalized schemas
    if existing_norm == current_norm:
        print("SQL schema matches current models")
        return True
    else:
        print("SQL schema does not match current models")
        return False

def init_db(reset=True):
    """Initialize the database, optionally resetting it first.
    
    Args:
        reset (bool): If True, drops all tables before creating them.
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

def get_session():
    """Get a new database session."""
    return Session()

def check_and_update_schema():
    """Check if SQL schema matches models and update if needed"""
    if not compare_sql_schema():
        print("Updating SQL schema file")
        save_sql_schema()
        
    # Always ensure database tables exist
    Base.metadata.create_all(engine)
    return True

# Function to be called in app startup
def setup_database(reset_on_startup=True):
    """Setup database during application startup"""
    if reset_on_startup:
        init_db(reset=True)
    else:
        check_and_update_schema()
    return engine 