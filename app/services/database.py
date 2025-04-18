"""Database service for SQLAlchemy configuration and database operations.

This service provides database setup, session management, and schema management
functions, ensuring proper initialization and consistent database state throughout the
application.
"""

import logging
import os
import re
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.schema import CreateTable

# Import Base from the shared location
from app.models import Base

# Import EventService from the events module
from app.services.events import EventService

logger: logging.Logger = logging.getLogger(__name__)

# SQLite database path
DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "sqlite:///app/instance/daytrader.db",
)
SQL_FILE_PATH: Path = Path(__file__).parent.parent / "instance" / "database.sql"

# Create engine
engine: Engine = create_engine(DATABASE_URL)

# Create session factory
session_factory: sessionmaker = sessionmaker(bind=engine)
Session: scoped_session = scoped_session(session_factory)


def generate_sql_schema() -> str:
    """Generate SQL DDL statements from SQLAlchemy models.

    Returns:
        str: The SQL schema DDL statements as a formatted string

    """
    sql_statements: list[str] = []

    # Generate CREATE TABLE statements for all models
    for table in Base.metadata.sorted_tables:
        create_stmt: str = str(CreateTable(table).compile(engine))
        # Add IF NOT EXISTS to make it safer
        create_stmt: str = create_stmt.replace(
            "CREATE TABLE",
            "CREATE TABLE IF NOT EXISTS",
        )
        sql_statements.append(create_stmt + ";")

    # Add index creation statements
    sql_statements.append("\n-- Create indexes for better performance")
    sql_statements.append(
        "CREATE INDEX IF NOT EXISTS idx_stock_transactions_service_id ON "
        "stock_transactions(service_id);",
    )
    sql_statements.append(
        "CREATE INDEX IF NOT EXISTS idx_stock_services_symbol ON "
        "stock_services(stock_symbol);",
    )
    sql_statements.append(
        "CREATE INDEX IF NOT EXISTS idx_stock_services_state ON "
        "stock_services(service_state);",
    )

    return "\n\n".join(sql_statements)


def save_sql_schema() -> str:
    """Generate and save SQL schema to database.sql file.

    Returns:
        str: The SQL schema that was saved

    Raises:
        IOError: If file cannot be written
        Exception: For other errors during schema generation

    """
    try:
        sql_schema: str = generate_sql_schema()

        SQL_FILE_PATH.write_text(sql_schema)

        # Emit database event for tracking
        EventService.emit_database_event(
            operation="schema_save",
            status="completed",
            target=str(SQL_FILE_PATH),
            details={"size": len(sql_schema)},
        )

        logger.info("SQL schema saved to %s", SQL_FILE_PATH)
        if sql_schema:
            return sql_schema
        logger.warning("SQL schema is empty")
    except Exception as e:
        # Emit failure event
        EventService.emit_database_event(
            operation="schema_save",
            status="failed",
            target=str(SQL_FILE_PATH),
            details={"error": str(e)},
        )
        raise


def compare_sql_schema() -> bool:
    """Compare existing SQL schema file with current models.

    Returns:
        bool: True if schemas match, False if they don't or file doesn't exist

    """
    if not SQL_FILE_PATH.exists():
        logger.info("SQL file %s does not exist", SQL_FILE_PATH)
        return False

    # Read existing SQL schema
    existing_schema: str = SQL_FILE_PATH.read_text()

    # Generate current schema from models
    current_schema: str = generate_sql_schema()

    # Normalize schemas for comparison (remove whitespace, case insensitive)
    def normalize_schema(schema: str) -> str:
        # Remove comments
        schema: str = re.sub(r"--.*?\n", "\n", schema)
        # Remove extra whitespace
        schema: str = re.sub(r"\s+", " ", schema)
        # Lowercase
        schema: str = schema.lower().strip()
        return schema

    existing_norm: str = normalize_schema(existing_schema)
    current_norm: str = normalize_schema(current_schema)

    # Compare normalized schemas
    if existing_norm == current_norm:
        logger.info("SQL schema matches current models")
        return True
    logger.info("SQL schema does not match current models")
    return False


def init_db(*, reset: bool = True) -> Engine:
    """Initialize the database, optionally resetting it first.

    Args:
        reset: If True, drops all tables before creating them.

    Returns:
        Engine: SQLAlchemy engine instance

    Raises:
        Exception: If database initialization fails

    """
    try:
        # Emit database initialization event
        EventService.emit_database_event(
            operation="initialization",
            status="started",
            details={"reset": reset},
        )

        if reset:
            Base.metadata.drop_all(engine)

        # Create all tables
        Base.metadata.create_all(engine)

        # Generate and save SQL schema
        save_sql_schema()

        logger.info("Database initialized at %s", DATABASE_URL)
        if reset:
            logger.info("All existing data has been reset")

        # Emit completion event
        EventService.emit_database_event(
            operation="initialization",
            status="completed",
            details={"reset": reset, "url": DATABASE_URL},
        )

        if engine:
            return engine
    except Exception as e:
        # Emit failure event
        EventService.emit_database_event(
            operation="initialization",
            status="failed",
            details={"reset": reset, "error": str(e)},
        )
        raise


def get_session() -> SQLAlchemySession:
    """Get a new database session.

    Returns:
        SQLAlchemySession: A new SQLAlchemy session

    """
    return Session()


def check_and_update_schema() -> bool:
    """Check if SQL schema matches models and update if needed.

    Returns:
        bool: True if schema check/update succeeded

    Raises:
        Exception: If schema update fails

    """
    EventService.emit_database_event(operation="schema_check", status="started")

    if not compare_sql_schema():
        logger.info("Updating SQL schema file")
        save_sql_schema()

    # Always ensure database tables exist
    Base.metadata.create_all(engine)

    EventService.emit_database_event(operation="schema_check", status="completed")

    return True


# Function to be called in app startup
def setup_database(*, reset_on_startup: bool = True) -> Engine:
    """Set up database during application startup.

    Args:
        reset_on_startup: Whether to reset the database on startup

    Returns:
        Engine: SQLAlchemy engine instance

    Raises:
        Exception: If database setup fails

    """
    EventService.emit_database_event(
        operation="setup",
        status="started",
        details={"reset_on_startup": reset_on_startup},
    )

    try:
        if reset_on_startup:
            result: Engine = init_db(reset=True)
        else:
            result: Engine = check_and_update_schema()

        EventService.emit_database_event(
            operation="setup",
            status="completed",
            details={"reset_on_startup": reset_on_startup},
        )

        # Also emit system notification for admin awareness
        EventService.emit_system_notification(
            notification_type="database",
            message="Database setup completed successfully",
            severity="info",
            details={"reset_performed": reset_on_startup},
        )
        if result:
            return result
    except Exception as e:
        # Emit failure events
        EventService.emit_database_event(
            operation="setup",
            status="failed",
            details={"reset_on_startup": reset_on_startup, "error": str(e)},
        )

        EventService.emit_system_notification(
            notification_type="database",
            message=f"Database setup failed: {e!s}",
            severity="error",
        )

        raise
