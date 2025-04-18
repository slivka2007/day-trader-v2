# day-trader-v1

## Overview

DayTrader is a comprehensive algorithmic trading platform that automates stock trading based on configurable strategies and technical analysis. Built on a three-layer architecture (Model, Service, API), the system features a Flask-based RESTful API backend with WebSocket support for real-time updates, an extensive service layer for business logic, and a robust relational database model for persistent storage.

The platform allows users to create and manage multiple trading services, each dedicated to a specific stock symbol. These services continuously analyze price data and execute buy/sell decisions based on technical indicators and configurable thresholds. The system tracks all transactions, calculates performance metrics, and provides real-time notifications of market activities.

Key features include user authentication with role-based access control, real-time WebSocket event notifications, comprehensive error handling, session-based database transactions, and a simulated trading environment for testing strategies. The modular design enables easy extension of trading strategies and integration with external data sources and trading platforms.

## Backend Project Structure

- `/app` - Main application package
  - `/api` - REST API implementation
    - `/resources` - Flask-RestX resource definitions (endpoint implementation)
      - `__init__.py` - Resource registration and namespace initialization
      - `auth.py` - Authentication and authorization endpoints
      - `stocks.py` - Stock data management endpoints
      - `daily_prices.py` - Daily price data management endpoints
      - `intraday_prices.py` - Intraday price data management endpoints
      - `system.py` - System status and operations endpoints
      - `trading_services.py` - Trading service management endpoints
      - `trading_transactions.py` - Transaction tracking endpoints
      - `users.py` - User account management endpoints
    - `/schemas` - Marshmallow schemas for serialization/validation
      - `__init__.py` - Schema registration and common schema utilities
      - `stock.py` - Stock data serialization schemas
      - `daily_price.py` - Daily price serialization schemas
      - `intraday_price.py` - Intraday price serialization schemas
      - `trading_service.py` - Trading service serialization schemas
      - `trading_transaction.py` - Transaction serialization schemas
      - `user.py` - User data serialization schemas
    - `__init__.py` - API initialization, pagination, filtering
    - `error_handlers.py` - API error handling and responses
    - `sockets.py` - WebSocket handlers and event definitions
  - `/models` - SQLAlchemy ORM models
    - `__init__.py` - Model registration and imports
    - `base.py` - Base model class and shared functionality
    - `enums.py` - Enum definitions used across models
    - `stock.py` - Stock data model
    - `stock_daily_price.py` - Daily stock price model
    - `stock_intraday_price.py` - Intraday stock price model
    - `trading_service.py` - Trading service model
    - `trading_transaction.py` - Transaction model
    - `user.py` - User account model
  - `/services` - Application services
    - `/data_providers` - External data source integrations
      - `__init__.py` - Provider registration and imports
      - `yfinance_provider.py` - Yahoo Finance data provider
    - `__init__.py` - Service registration and imports
    - `backtest_service.py` - Strategy backtesting capabilities
    - `daily_price_service.py` - Daily price data operations
    - `intraday_price_service.py` - Intraday price data operations
    - `technical_analysis_service.py` - Market analysis algorithms
    - `trading_strategy_service.py` - Trading strategy implementations
    - `database.py` - Database connection management
    - `events.py` - Event emission service
    - `session_manager.py` - Database session management
    - `stock_service.py` - Stock data business logic
    - `trading_service.py` - Trading service business logic
    - `transaction_service.py` - Transaction business logic
    - `user_service.py` - User account business logic
  - `/utils` - Utility modules
    - `__init__.py` - Utility registration and imports
    - `auth.py` - Authentication utilities
    - `constants.py` - Application-wide constants
    - `current_datetime.py` - Date/time handling utilities
    - `errors.py` - Error handling utilities
    - `query_utils.py` - Database query utilities
    - `validators.py` - Input validation utilities
  - `/instance` - Instance-specific data
    - `database.sql` - Database schema SQL
    - `daytrader.db` - SQLite database file

## Model Layer

The application uses a relational database with the following core tables:

- **Base Model (Abstract)**  
  Provides common functionality for all models:

  - `id` (Integer, primary key, autoincrement)
  - `created_at` (DateTime, when the record was created)
  - `updated_at` (DateTime, when the record was last updated)
  - Methods:
    - `to_dict()`: Converts model to dictionary representation
    - `to_json()`: Converts model to JSON string
    - `update_from_dict()`: Updates model from dictionary data
    - `from_dict()`: Creates model instance from dictionary data

- **User Model**  
  Stores user account information:

  - `id` (Integer, primary key)
  - `username` (String(50), unique, nullable=False)
  - `email` (String(120), unique, nullable=False)
  - `password_hash` (String(128), nullable=False)
  - `is_active` (Boolean, default=True)
  - `is_admin` (Boolean, default=False)
  - `last_login` (DateTime)
  - `created_at` (DateTime, default=get_current_datetime)
  - `updated_at` (DateTime, default=get_current_datetime, onupdate=get_current_datetime)
  - Relationships:
    - `services` (One-to-Many relationship to TradingService, cascade="all, delete-orphan")
  - Properties:
    - `password` (setter only, raises error when getting)
    - `has_active_services` (Boolean, whether user has active trading services)
  - Validation methods:
    - `validate_username()`: Validates username length and format
    - `validate_email()`: Validates email format
  - Methods:
    - `verify_password()`: Verifies password against stored hash
    - `update_last_login()`: Updates last login timestamp

- **Stock Model**  
  Stores basic information about stocks:

  - `id` (Integer, primary key, inherited from Base)
  - `symbol` (String(10), unique, nullable=False, indexed)
  - `name` (String(200), nullable=True)
  - `is_active` (Boolean, default=True, nullable=False)
  - `sector` (String(100), nullable=True)
  - `description` (String(1000), nullable=True)
  - `created_at` (DateTime, inherited from Base)
  - `updated_at` (DateTime, inherited from Base)
  - Relationships:
    - `daily_prices` (One-to-Many relationship to StockDailyPrice, cascade="all, delete-orphan")
    - `intraday_prices` (One-to-Many relationship to StockIntradayPrice, cascade="all, delete-orphan")
    - `services` (One-to-Many relationship to TradingService)
    - `transactions` (One-to-Many relationship to TradingTransaction)
  - Properties:
    - `has_dependencies` (Boolean, whether stock has services or transactions)
    - `has_prices` (Boolean, whether stock has any price data)
  - Validation methods:
    - `validate_symbol()`: Validates stock symbol format and length
    - `validate_name()`: Validates stock name length
    - `validate_sector()`: Validates sector length
    - `validate_description()`: Validates description length

- **Stock Daily Price Model**  
  Stores end-of-day price data for stocks:

  - `id` (Integer, primary key, inherited from Base)
  - `stock_id` (Integer, ForeignKey to the stock, nullable=False)
  - `price_date` (Date, nullable=False)
  - `open_price` (Float, nullable=True)
  - `high_price` (Float, nullable=True)
  - `low_price` (Float, nullable=True)
  - `close_price` (Float, nullable=True)
  - `adj_close` (Float, nullable=True)
  - `volume` (Integer, nullable=True)
  - `source` (String(20), default=PriceSource.HISTORICAL.value, nullable=False)
  - `created_at` (DateTime, inherited from Base)
  - `updated_at` (DateTime, inherited from Base)
  - Relationships:
    - `stock` (Many-to-One relationship to Stock)
  - Constraints:
    - Unique constraint on `(stock_id, price_date)`
  - Properties:
    - `change` (Float, price change from open to close)
    - `change_percent` (Float, percentage price change)
    - `is_real_data` (Boolean, whether price data is from a real source)
    - `trading_range` (Float, high_price - low_price)
    - `trading_range_percent` (Float, trading range as percentage of low price)
  - Validation methods:
    - `validate_source()`: Validates source enum value
    - `validate_price_date()`: Ensures date is not in the future
    - `validate_prices()`: Ensures prices are non-negative and maintains logical price relationships

- **Stock Intraday Price Model**  
  Stores intraday (e.g., minute-by-minute) price data:

  - `id` (Integer, primary key, inherited from Base)
  - `stock_id` (Integer, ForeignKey to the stock, nullable=False)
  - `timestamp` (DateTime, nullable=False)
  - `interval` (Integer, default=1, nullable=False) - Time interval in minutes (1, 5, 15, 30, 60)
  - `open_price` (Float, nullable=True)
  - `high_price` (Float, nullable=True)
  - `low_price` (Float, nullable=True)
  - `close_price` (Float, nullable=True)
  - `volume` (Integer, nullable=True)
  - `source` (String(20), default=PriceSource.DELAYED.value, nullable=False)
  - `created_at` (DateTime, inherited from Base)
  - `updated_at` (DateTime, inherited from Base)
  - Relationships:
    - `stock` (Many-to-One relationship to Stock)
  - Constraints:
    - Unique constraint on `(stock_id, timestamp, interval)`
  - Properties:
    - `change` (Float, price change from open to close)
    - `change_percent` (Float, percentage price change)
    - `is_real_data` (Boolean, whether price data is from a real source)
    - `is_delayed` (Boolean, whether price data is delayed)
    - `is_simulated` (Boolean, whether price data is simulated)
    - `is_historical` (Boolean, whether price data is historical)
    - `is_real_time` (Boolean, whether price data is real-time)
    - `is_valid` (Boolean, whether price data is valid)
  - Validation methods:
    - `validate_source()`: Validates source enum value
    - `validate_timestamp()`: Ensures timestamp is not in the future
    - `validate_interval()`: Validates interval is a supported value
    - `validate_prices()`: Ensures prices are non-negative and maintains logical price relationships

- **Trading Service Model**  
  Stores information about each trading service instance:

  - `id` (Integer, primary key)
  - `user_id` (Integer, ForeignKey to User, nullable=False)
  - `stock_id` (Integer, ForeignKey to Stock, nullable=True)
  - `active_transaction_id` (Integer, ForeignKey to TradingTransaction, nullable=True)
  - `name` (String(100), nullable=False)
  - `description` (Text, nullable=True)
  - `stock_symbol` (String(10), nullable=False)
  - `state` (String(20), default=ServiceState.INACTIVE.value, nullable=False)
  - `mode` (String(20), default=TradingMode.BUY.value, nullable=False)
  - `is_active` (Boolean, default=True, nullable=False)
  - `initial_balance` (Numeric(18,2), nullable=False)
  - `current_balance` (Numeric(18,2), nullable=False)
  - `minimum_balance` (Numeric(18,2), default=0, nullable=False)
  - `allocation_percent` (Numeric(18,2), default=0.5, nullable=False)
  - `buy_threshold` (Numeric(18,2), default=3.0, nullable=False)
  - `sell_threshold` (Numeric(18,2), default=2.0, nullable=False)
  - `stop_loss_percent` (Numeric(18,2), default=5.0, nullable=False)
  - `take_profit_percent` (Numeric(18,2), default=10.0, nullable=False)
  - `current_shares` (Integer, default=0, nullable=False)
  - `buy_count` (Integer, default=0, nullable=False)
  - `sell_count` (Integer, default=0, nullable=False)
  - `total_gain_loss` (Numeric(18,2), default=0, nullable=False)
  - `created_at` (DateTime, inherited from Base)
  - `updated_at` (DateTime, inherited from Base)
  - Relationships:
    - `user` (Many-to-One relationship to User)
    - `stock` (Many-to-One relationship to Stock, optional)
    - `transactions` (One-to-Many relationship to TradingTransaction, cascade="all, delete-orphan")
    - `active_transaction` (Many-to-One relationship to TradingTransaction, optional)
  - Properties:
    - `can_buy` (Boolean, whether service can buy stocks)
    - `can_sell` (Boolean, whether service can sell stocks)
    - `is_profitable` (Boolean, whether service has positive gain/loss)
    - `has_dependencies` (Boolean, whether service has associated transactions)
    - `has_active_transaction` (Boolean, whether service has an active transaction)
  - Validation methods:
    - `validate_stock_symbol()`: Validates stock symbol format
    - `validate_state()`: Validates service state enum value
    - `validate_mode()`: Validates trading mode enum value
    - `validate_initial_balance()`: Ensures positive initial balance
    - `validate_current_balance()`: Ensures positive current balance
    - `validate_minimum_balance()`: Ensures non-negative minimum balance
    - `validate_allocation_percent()`: Validates allocation is within allowed range

- **Trading Transaction Model**  
  Tracks individual buy and sell actions for each service:
  - `id` (Integer, primary key)
  - `service_id` (Integer, ForeignKey to TradingService, nullable=False)
  - `stock_id` (Integer, ForeignKey to Stock, nullable=True)
  - `stock_symbol` (String(10), nullable=False, indexed)
  - `shares` (Numeric(18,2), nullable=False)
  - `state` (String(20), default=TransactionState.OPEN.value, nullable=False)
  - `purchase_price` (Numeric(18,2), nullable=False)
  - `sale_price` (Numeric(18,2), nullable=True)
  - `gain_loss` (Numeric(18,2), nullable=True)
  - `purchase_date` (DateTime, default=get_current_datetime, nullable=False)
  - `sale_date` (DateTime, nullable=True)
  - `notes` (Text, nullable=True)
  - `created_at` (DateTime, inherited from Base)
  - `updated_at` (DateTime, inherited from Base)
  - Relationships:
    - `service` (Many-to-One relationship to TradingService)
    - `stock` (Many-to-One relationship to Stock, optional)
  - Properties:
    - `is_complete` (Boolean, whether transaction is completed)
    - `is_open` (Boolean, whether transaction is open/active)
    - `is_profitable` (Boolean, whether transaction resulted in profit)
    - `can_be_cancelled` (Boolean, whether transaction can be cancelled)
    - `calculated_gain_loss` (Float, calculated gain/loss from prices)
  - Validation methods:
    - `validate_stock_symbol()`: Validates stock symbol format
    - `validate_state()`: Validates transaction state enum value
    - `validate_shares()`: Ensures shares amount is positive
    - `validate_purchase_price()`: Validates purchase price is positive

The application uses the following Enumeration types to constrain field values:

- **ServiceState**: Defines possible states for a trading service

  - `ACTIVE`: Service is running and can process transactions
  - `INACTIVE`: Service is not running (either never started or explicitly stopped)
  - `PAUSED`: Service is temporarily suspended but can be resumed
  - `ERROR`: Service encountered an error and needs attention

- **ServiceAction**: Defines actions that can be taken on a service

  - `CHECK_BUY`: Check for a buy opportunity
  - `CHECK_SELL`: Check for a sell opportunity

- **TradingMode**: Defines possible trading modes

  - `BUY`: Service is looking for opportunities to buy
  - `SELL`: Service is looking for opportunities to sell
  - `HOLD`: Service is holding current positions without buying or selling

- **TransactionState**: Defines possible transaction states

  - `OPEN`: Purchase executed, not yet sold
  - `CLOSED`: Fully executed (purchased and sold)
  - `CANCELLED`: Transaction cancelled before completion

- **PriceSource**: Defines sources of price data

  - `REAL_TIME`: Live price data from exchanges
  - `DELAYED`: Delayed price data (typically 15-20 minutes)
  - `SIMULATED`: Simulated or generated price data for testing
  - `HISTORICAL`: Historical price data from past periods
  - `TEST`: Test data for development and testing purposes

- **IntradayInterval**: Valid intervals for intraday price data

  - `ONE_MINUTE`: 1-minute interval
  - `FIVE_MINUTES`: 5-minute interval
  - `FIFTEEN_MINUTES`: 15-minute interval
  - `THIRTY_MINUTES`: 30-minute interval
  - `ONE_HOUR`: 60-minute (1-hour) interval

- **AnalysisTimeframe**: Defines standard timeframes for analysis
  - `INTRADAY`: Within a single trading day
  - `DAILY`: Day-to-day analysis
  - `WEEKLY`: Week-to-week analysis
  - `MONTHLY`: Month-to-month analysis
  - `QUARTERLY`: Quarter-to-quarter analysis
  - `YEARLY`: Year-to-year analysis

## Service Layer

The service layer provides core infrastructure and cross-cutting concerns that bridge the database models and API endpoints:

### Key Services

- **Database Service**: Manages database connections and schema management

  - Provides connection pooling and session management
  - Handles database initialization and schema migrations
  - Generates SQL DDL statements from the ORM models
  - Includes schema comparison and validation functionality
  - Emits database events for schema changes and operations

- **Session Manager**: Ensures proper database transaction handling

  - Context manager for automatic session handling (`with SessionManager() as session`)
  - Function decorator for wrapping database operations (`@with_session`)
  - Automatic commit on success and rollback on exceptions

- **Event Service**: Facilitates real-time WebSocket communication

  - Standardizes event emission across the application
  - Maps database model changes to WebSocket events
  - Provides room-based targeting for efficient event delivery
  - Handles stock, service, transaction, price, user, system, metrics, and database events
  - Supports filtering sensitive data from user events

- **User Service**: Manages user account operations

  - User authentication and authorization
  - Account creation, updates, and management
  - Password handling and security
  - Admin privilege management
  - User search and filtering capabilities

- **Stock Service**: Handles stock data operations

  - Stock creation, updates, and retrieval
  - Symbol-based lookups and validation
  - Stock status management and toggling
  - Stock search functionality
  - Tracks stock dependencies (services and transactions)

- **Daily Price Service**: Manages daily stock price data

  - Daily price record management (CRUD operations)
  - Historical price data retrieval with date-range filtering
  - Data import from external providers
  - Price trend analysis and basic forecasting
  - Integration with Yahoo Finance for historical data

- **Intraday Price Service**: Manages intraday stock price data

  - Minute-by-minute price data management
  - Real-time and delayed price updates
  - Support for multiple time intervals (1m, 5m, 15m, 30m, 60m)
  - Integration with Yahoo Finance for intraday data

- **Technical Analysis Service**: Performs market data analysis

  - Calculation of technical indicators (RSI, Bollinger Bands)
  - Moving average calculations (short/medium/long-term)
  - Market trend identification and pattern recognition
  - Signal generation for trading decisions
  - Support for custom analysis timeframes

- **Trading Service**: Core service for trading operations

  - Trading service lifecycle management
  - Service state management (active, inactive, paused, error)
  - Performance tracking and metrics calculation
  - Account balance and allocation management
  - Integration with stock and transaction services

- **Trading Strategy Service**: Implements trading decision logic

  - Configurable buy/sell condition evaluation
  - Technical indicator-based decision making
  - Strategy execution and trade signal generation
  - Integration with technical analysis service
  - Support for custom decision parameters (thresholds, allocation)

- **Transaction Service**: Tracks trading transactions

  - Buy/sell transaction creation and management
  - Transaction completion and cancellation handling
  - Profit/loss calculation and reporting
  - Transaction search and filtering
  - Historical transaction analysis

- **Backtest Service**: Enables trading strategy evaluation

  - Historical strategy performance simulation
  - Performance metrics calculation (returns, drawdowns)
  - Parameter optimization capabilities
  - Trade simulation without affecting real balances
  - Comparative strategy analysis

- **Data Providers**: Integration with external market data sources
  - Yahoo Finance integration for real-time and historical data
  - Configurable data fetching parameters
  - Error handling and retry logic
  - Data transformation to internal model formats
  - Support for multiple data granularities

### Service Layer Architecture

The service layer follows these architectural principles:

1. **Separation of Concerns**: Each service focuses on a specific functionality domain
2. **Database Abstraction**: Isolates the database implementation details from the API layer
3. **Event-Driven Communication**: Enables real-time updates without polling
4. **Transaction Management**: Ensures data consistency across operations
5. **Stateless Operations**: Services do not maintain internal state between calls
6. **Session-Based Data Access**: All database operations use managed sessions

## API Layer

The application's backend API follows RESTful principles with a well-structured layered architecture:

### Core API Structure

- **REST API** (`/api/v1`): Built with Flask-RESTX, providing self-documenting endpoints with Swagger UI (`/api/v1/docs`)
- **WebSockets**: Real-time notifications for data changes using Flask-SocketIO
- **Authentication**: JWT-based authentication with protected endpoints requiring valid tokens
- **Error Handling**: Standardized error handling and responses via error_handlers.py

### Resources (Endpoints)

The API organizes resources into logical namespaces:

- **Authentication** (`/api/v1/auth`):

  - `POST /register`: Register a new user account
  - `POST /login`: Authenticate and receive access tokens
  - `POST /refresh`: Refresh an existing access token

- **Users** (`/api/v1/users`):

  - Standard CRUD operations for user accounts
  - Password management
  - Administrative user controls

- **Stocks** (`/api/v1/stocks`):

  - Standard CRUD operations for stock data
  - Stock search and filtering capabilities
  - Stock status management

- **Daily Prices** (`/api/v1/daily_prices`):

  - End-of-day price data management
  - Historical daily price retrieval and filtering
  - Bulk import for daily price data
  - Price trend and analysis

- **Intraday Prices** (`/api/v1/intraday_prices`):

  - Minute-by-minute price data management
  - Real-time and delayed price updates
  - Multi-interval price data (1m, 5m, 15m, 30m, 60m)
  - Intraday price history and filtering

- **Trading Services** (`/api/v1/services`):

  - Service configuration and control
  - Service state management (activate, pause, stop)
  - Performance metrics and statistics

- **Trading Transactions** (`/api/v1/transactions`):

  - Transaction record management
  - Transaction completion and cancellation
  - Transaction filtering and reporting

- **System** (`/api/v1/system`):
  - System status information
  - Database management utilities
  - Configuration and operational controls

### Data Validation and Serialization

- **Schemas**: Marshmallow schemas validate request data and serialize responses
  - Model-specific schemas for each resource type
  - Custom field validation and transformation
  - Standardized error reporting
- **Model Mapping**: Direct mapping between API schemas and database models
- **Validation Rules**: Comprehensive input validation for all endpoints

### API Features

- **Pagination**: Consistent pagination for list endpoints with metadata
  - Page number and page size parameters
  - Total items and total pages information
  - Previous/next page indicators
- **Filtering**: Query parameter filtering across multiple fields
  - Simple equality filters (e.g., `?status=active`)
  - Range filters with suffix notation (e.g., `?price_min=10&price_max=20`)
  - Text search filters with suffix notation (e.g., `?name_like=trading`)
- **Sorting**: Flexible sorting on various fields
  - Sort column selection (e.g., `?sort=created_at`)
  - Sort direction control (e.g., `?order=desc`)
- **Error Handling**: Standardized error responses with descriptive messages
- **WebSocket Events**: Real-time updates for database changes

### WebSocket Notifications

The API emits events for model changes through rooms:

- `services`: All trading service updates
- `service_{id}`: Updates for a specific service
- `stocks`: All stock updates
- `stock_{symbol}`: Updates for a specific stock
- `transactions`: All transaction updates
- `price_updates`: Real-time price changes
- `users`: User account updates
- `user_{id}`: Updates for a specific user
- `metrics`: Analytics dashboard updates
- `system`: System-wide notifications
- `system_{severity}`: Filtered system notifications by severity
- `errors`: Error events
- `data_feeds`: Consolidated data feeds
- `database_admin`: Database operation events

### WebSocket Events

- **Connection Management**:
  - `connect`: Initial connection event
  - `disconnect`: Connection termination event
  - `join`: Join a specific notification room
  - `leave`: Leave a notification room
- **Convenience Events**:
  - `service_watch`: Watch a specific trading service
  - `stock_watch`: Watch a specific stock
  - `user_watch`: Watch a specific user
  - `join_services`: Watch all service events
  - `join_price_updates`: Watch all price updates
  - `join_transactions`: Watch all transaction events
  - `join_system`: Watch system events (optionally filtered by severity)
  - `join_users`: Watch user account events (admin only)
- **Data Events**:
  - `service:update`: Trading service update
  - `service:state_change`: Service state change
  - `transaction:new`: New transaction created
  - `transaction:update`: Transaction updated
  - `transaction:complete`: Transaction completed
  - `price:update`: Price data update
  - `stock:update`: Stock data update
  - `user:update`: User data update (restricted fields)
  - `system:notification`: System-wide notification
  - `error`: Error event with standardized format
