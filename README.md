# day-trader-v1
The application is designed to generate revenue by automatically trading stocks.

## Overview
The application is designed to generate revenue by automatically trading stocks in which the user wishes to take a long (bullish) position. It continuously cycles between buying and selling a specified stock based on signals from decision-making APIs until the user disables the service. The system leverages a simple database to track services and transactions, and it integrates with a mock trading system that simulates market behavior for testing purposes. A web dashboard allows users to monitor and control trading services in real-time.

## Project Structure

- **Backend**
  - `/app` - Main application package
    - `/api` - REST API implementation
      - `/resources` - Flask-RestX resource definitions (endpoint implementation)
      - `/schemas` - Marshmallow schemas for serialization/validation
      - `__init__.py` - API initialization, pagination, filtering
      - `sockets.py` - WebSocket handlers
      - `decorators.py` - API-related decorators
      - `auth.py` - Authentication related endpoints
    - `/models` - SQLAlchemy ORM models
      - `base.py` - Base model class and shared functionality
      - `enums.py` - Enum definitions used across models
      - Model files (`user.py`, `stock.py`, etc.) - Domain-specific model definitions
    - `/services` - Application services
      - `events.py` - Event emission service
      - `database.py` - Database connection management
      - `session_manager.py` - Session management utilities
    - `/utils` - Utility modules
      - `auth.py` - Authentication utilities
      - `errors.py` - Error handling utilities
      - `current_datetime.py` - Date/time handling utilities

- **Flow**
  - Client → API Layer (Resource) → Service Layer → Database Layer (via Database Service) → Service Layer → API Layer (Schema) → Client

- **Summary**
  - API Resources: Handle requests and call the service layer.

  - API Schemas: Validate and format data between the client and service layer.

  - Service Layer: Contains business logic and uses the Database Service to interact with database models.

  - Database Layer: Stores data, accessed only via the Database Service.

  - This separation ensures the API layer focuses on client communication, the service layer manages logic, and the database layer handles persistence.

## Database Schema
The application uses a relational database with the following core tables:

- **Base Model (Abstract)**  
  Provides common functionality for all models:
  - `id` (integer, primary key, autoincrement)
  - `created_at` (datetime, when the record was created)
  - `updated_at` (datetime, when the record was last updated)

- **User Model**  
  Stores user account information:
  - `id` (integer, primary key, unique identifier for each user)
  - `username` (string, unique username for login, max 50 characters)
  - `email` (string, unique email address, max 120 characters)
  - `password_hash` (string, securely hashed password, max 128 characters)
  - `is_active` (boolean, whether the user account is active)
  - `is_admin` (boolean, whether the user has admin privileges)
  - `last_login` (datetime, timestamp of last login)
  - `created_at` (datetime, when the record was created)
  - `updated_at` (datetime, when the record was last updated)

- **Stock Model**  
  Stores basic information about stocks:
  - `id` (integer, primary key, unique identifier for each stock)
  - `symbol` (string, unique ticker symbol, max 10 characters, index)
  - `name` (string, full company/entity name, max 200 characters)
  - `is_active` (boolean, whether the stock is actively traded)
  - `sector` (string, industry sector, max 100 characters)
  - `description` (string, brief description, max 1000 characters)
  - `created_at` (datetime, when the record was created)
  - `updated_at` (datetime, when the record was last updated)
  - Relationships to daily prices, intraday prices, services, and transactions

- **Stock Daily Price Model**  
  Stores end-of-day price data for stocks:
  - `id` (integer, primary key)
  - `stock_id` (integer, foreign key to the stock)
  - `price_date` (date, the trading date this price represents)
  - `open_price` (float, opening price for the trading day)
  - `high_price` (float, highest price during the trading day)
  - `low_price` (float, lowest price during the trading day)
  - `close_price` (float, closing price for the trading day)
  - `adj_close` (float, adjusted closing price)
  - `volume` (integer, number of shares traded)
  - `source` (string, source of the price data, e.g., "HISTORICAL", "DELAYED")
  - `created_at` (datetime, when the record was created)
  - `updated_at` (datetime, when the record was last updated)
  - Unique constraint on `(stock_id, price_date)`

- **Stock Intraday Price Model**  
  Stores intraday (e.g., minute-by-minute) price data:
  - `id` (integer, primary key)
  - `stock_id` (integer, foreign key to the stock)
  - `timestamp` (datetime, timestamp for this price point)
  - `interval` (integer, time interval in minutes, e.g., 1, 5, 15, 30, 60)
  - `open_price` (float, opening price for the interval)
  - `high_price` (float, highest price during the interval)
  - `low_price` (float, lowest price during the interval)
  - `close_price` (float, closing price for the interval)
  - `volume` (integer, number of shares traded)
  - `source` (string, source of the price data)
  - `created_at` (datetime, when the record was created)
  - `updated_at` (datetime, when the record was last updated)
  - Unique constraint on `(stock_id, timestamp, interval)`

- **Trading Service Model**  
  Stores information about each trading service instance:
  - `id` (integer, primary key, unique identifier for each service)
  - `user_id` (integer, foreign key to the user who owns this service)
  - `stock_id` (integer, foreign key to the stock being traded)
  - `name` (string, descriptive name for the service, max 100 characters)
  - `description` (text, optional detailed description)
  - `stock_symbol` (string, the stock ticker symbol, e.g., "AAPL", max 10 characters)
  - `state` (string, current state of the service, e.g., "ACTIVE", "INACTIVE", "PAUSED", "ERROR")
  - `mode` (string, current trading mode, e.g., "BUY", "SELL", "HOLD")
  - `is_active` (boolean, whether the service is enabled)
  - `initial_balance` (decimal(18,2), initial funds provided by the user)
  - `current_balance` (decimal(18,2), current funds available for trading)
  - `minimum_balance` (decimal(18,2), minimum balance to maintain)
  - `allocation_percent` (decimal(18,2), percentage of funds to allocate per trade)
  - `buy_threshold` (decimal(18,2), threshold for buy decisions)
  - `sell_threshold` (decimal(18,2), threshold for sell decisions)
  - `stop_loss_percent` (decimal(18,2), stop loss percentage)
  - `take_profit_percent` (decimal(18,2), take profit percentage)
  - `current_shares` (integer, number of shares currently held)
  - `buy_count` (integer, count of completed buy transactions)
  - `sell_count` (integer, count of completed sell transactions)
  - `total_gain_loss` (decimal(18,2), cumulative profit or loss from completed transactions)
  - `created_at` (datetime, when the record was created)
  - `updated_at` (datetime, when the record was last updated)

- **Trading Transaction Model**  
  Tracks individual buy and sell actions for each service:
  - `id` (integer, primary key, unique identifier for each transaction)
  - `service_id` (integer, foreign key to the trading service)
  - `stock_id` (integer, foreign key to the stock being traded)
  - `stock_symbol` (string, the stock ticker symbol, max 10 characters, index)
  - `shares` (decimal(18,2), number of shares bought and eventually sold)
  - `state` (string, current state of the transaction, e.g., "OPEN", "CLOSED", "CANCELLED")
  - `purchase_price` (decimal(18,2), price per share at purchase)
  - `sale_price` (decimal(18,2), price per share at sale, null until sold)
  - `gain_loss` (decimal(18,2), profit or loss, calculated as `(sale_price - purchase_price) * shares`, null until sold)
  - `purchase_date` (datetime, timestamp of purchase)
  - `sale_date` (datetime, timestamp of sale, null until sold)
  - `notes` (text, optional notes about the transaction)
  - `created_at` (datetime, when the record was created)
  - `updated_at` (datetime, when the record was last updated)

All models inherit from a common Base model that provides standard fields like `id`, `created_at`, and `updated_at` for consistent tracking of record creation and modification.

The application uses the following Enumeration types to constrain field values:

- **ServiceState**: Defines possible states for a trading service ("ACTIVE", "INACTIVE", "PAUSED", "ERROR")
- **TradingMode**: Defines possible trading modes ("BUY", "SELL", "HOLD")
- **TransactionState**: Defines possible transaction states ("OPEN", "CLOSED", "CANCELLED")
- **PriceSource**: Defines sources of price data ("REAL_TIME", "DELAYED", "SIMULATED", "HISTORICAL")
- **AnalysisTimeframe**: Defines standard timeframes for analysis ("INTRADAY", "DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "YEARLY")

## API Schema
The application's backend API follows RESTful principles with a well-structured layered architecture:

### Core API Structure
- **REST API** (`/api/v1`): Built with Flask-RESTX, providing self-documenting endpoints with Swagger UI (`/api/v1/docs`)
- **WebSockets**: Real-time notifications for data changes using Flask-SocketIO
- **Authentication**: JWT-based authentication with protected endpoints requiring valid tokens

### Resources (Endpoints)
The API organizes resources into logical namespaces:

- **Authentication** (`/api/v1/auth`): User login, token management
- **Users** (`/api/v1/users`): User account management
- **Stocks** (`/api/v1/stocks`): Stock data management
- **Stock Prices** (`/api/v1/prices`): Daily and intraday price data
- **Trading Services** (`/api/v1/services`): Trading service configuration and control
- **Trading Transactions** (`/api/v1/transactions`): Transaction tracking and management
- **System** (`/api/v1/system`): System status and operations

Each resource namespace provides standard CRUD operations and additional specialized endpoints like toggling service states or completing transactions.

### Data Validation and Serialization
- **Schemas**: Marshmallow schemas validate request data and serialize responses
- **Model Mapping**: Direct mapping between API schemas and database models
- **Validation Rules**: Comprehensive input validation for all endpoints

### API Features
- **Pagination**: Consistent pagination for list endpoints with metadata
- **Filtering**: Query parameter filtering across multiple fields
- **Sorting**: Flexible sorting on various fields
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

### Security
- JWT tokens for authentication
- Role-based access control (admin/user permissions)
- Input validation to prevent injection attacks
- Protected admin-only endpoints

## Service Layer
The service layer provides core infrastructure and cross-cutting concerns that bridge the database models and API endpoints:

### Key Services

- **Database Service**: Manages database connections and schema management
  - Provides connection pooling and session management
  - Handles database initialization and schema migrations
  - Generates SQL DDL statements from the ORM models

- **Session Manager**: Ensures proper database transaction handling
  - Context manager for automatic session handling (`with SessionManager() as session`)
  - Function decorator for wrapping database operations (`@with_session`)
  - Automatic commit on success and rollback on exceptions

- **Event Service**: Facilitates real-time WebSocket communication
  - Standardizes event emission across the application
  - Maps database model changes to WebSocket events
  - Provides room-based targeting for efficient event delivery
  - Handles stock, service, transaction, price, and user events

### Service Layer Architecture

The service layer follows these architectural principles:

1. **Separation of Concerns**: Each service focuses on a specific functionality domain
2. **Database Abstraction**: Isolates the database implementation details from the API layer
3. **Event-Driven Communication**: Enables real-time updates without polling
4. **Transaction Management**: Ensures data consistency across operations

### Integration Points

- **Database Schema Integration**: Services interact with the models defined in the Database Schema section
  - Session Manager ensures consistent transaction handling for all model operations
  - Database Service maintains the schema defined by the models

- **API Schema Integration**: Services support the API endpoints described in the API Schema section
  - Event Service emits events for WebSocket notifications described in the API Schema
  - Services provide the implementation for API resource operations

## User Input
The user provides:
- **Stock Symbol**: The ticker symbol of the stock to trade (e.g., "AAPL").
- **Fund Amount**: The initial amount of money to allocate (recorded as `starting_balance`).

## Components

### #1 Stock Trading Service (Service Layer)
Manages the trading cycle for a specific stock symbol, alternating between "BUY" and "SELL" modes based on API signals.

- **Initialization**:
  - Creates a new record in the Service Table:
    - `service_id`: Auto-generated unique ID
    - `stock_symbol`: User-provided stock symbol
    - `starting_balance`: User-provided fund amount
    - `fund_balance`: Set to `starting_balance`
    - `total_gain_loss`: 0
    - `current_number_of_shares`: 0
    - `service_state`: "ACTIVE"
    - `service_mode`: "BUY"
    - `start_date`: Current timestamp
    - `number_of_buy_transactions`: 0
    - `number_of_sell_transactions`: 0

- **Trading Cycle**:
  - Runs continuously while `service_state` is "ACTIVE":
    - **Buy Mode**:
      - Calls the **Stock Buy API (#2)** with `stock_symbol`.
      - If "YES" is returned:
        - Calls the **Stock Purchase API (#4)** with `stock_symbol` and current `fund_balance`.
        - Receives `number_of_shares`, `purchase_price`, and `date_time_of_purchase`.
        - Inserts a new row into the Transaction Table:
          - `service_id`: From the service
          - `transaction_id`: Auto-generated unique ID
          - `stock_symbol`: From the service
          - `number_of_shares`: From the Stock Purchase API
          - `purchase_price`: From the Stock Purchase API
          - `date_time_of_purchase`: From the Stock Purchase API
          - `sale_price`, `gain_loss`, `date_time_of_sale`: Null
        - Updates the Service Table:
          - `fund_balance` = `fund_balance` - (`number_of_shares` * `purchase_price`)
          - `current_number_of_shares` = `current_number_of_shares` + `number_of_shares`
          - `number_of_buy_transactions` = `number_of_buy_transactions` + 1
        - Sets `service_mode` to "SELL".
      - If "NO" is returned:
        - Waits for a configurable interval (e.g., 10 seconds for demo, 5 minutes for production) before retrying.
    - **Sell Mode**:
      - Verifies `current_number_of_shares` > 0 (to ensure there are shares to sell).
      - Calls the **Stock Sell API (#3)** with `stock_symbol` and `purchase_price` from the last open transaction.
      - If "YES" is returned:
        - Calls the **Stock Sale API (#5)** with `stock_symbol` and `current_number_of_shares`.
        - Receives `sale_price` and `date_time_of_sale`.
        - Updates the corresponding Transaction Table row (last row with null `sale_price`):
          - `sale_price`: From the Stock Sale API
          - `date_time_of_sale`: From the Stock Sale API
          - `gain_loss` = (`sale_price - purchase_price`) * `number_of_shares`
        - Updates the Service Table:
          - `fund_balance` = `fund_balance` + (`number_of_shares` * `sale_price`)
          - `total_gain_loss` = `total_gain_loss` + `gain_loss`
          - `current_number_of_shares` = `current_number_of_shares` - `number_of_shares`
          - `number_of_sell_transactions` = `number_of_sell_transactions` + 1
        - Sets `service_mode` to "BUY".
      - If "NO" is returned:
        - Waits for a configurable interval before retrying.

- **Termination**:
  - User sets `service_state` to "INACTIVE", stopping the cycle. Open positions (unsold shares) remain until further user action.

### #2 Stock Buy API (API Layer)
- **Input**: `stock_symbol` (string)
- **Output**: String ("YES" or "NO")
- **Purpose**: Provides an interface for determining whether to buy a stock based on market analysis.
- **Implementation**: Wraps the Stock Buy Logic with API-specific error handling and logging. Serves as an intermediary between the Service Layer and the Algorithm Layer.

### #3 Stock Sell API (API Layer)
- **Input**: `stock_symbol` (string), `purchase_price` (decimal)
- **Output**: String ("YES" or "NO")
- **Purpose**: Provides an interface for determining whether to sell a stock based on purchase price and current price.
- **Implementation**: Wraps the Stock Sell Logic with API-specific error handling and logging. Serves as an intermediary between the Service Layer and the Algorithm Layer.

### #4 Stock Purchase API (API Layer)
- **Input**: `stock_symbol` (string), `fund_balance` (decimal, funds available)
- **Output**: `number_of_shares` (integer), `purchase_price` (decimal), `date_time_of_purchase` (datetime)
- **Purpose**: Simulates buying shares at the current market price with available funds.
- **Implementation**: Uses mock prices and configurable price movement patterns to generate realistic purchase scenarios. Each stock has defined base prices and price volatility characteristics.

### #5 Stock Sale API (API Layer)
- **Input**: `stock_symbol` (string), `number_of_shares` (integer)
- **Output**: `sale_price` (decimal), `date_time_of_sale` (datetime)
- **Purpose**: Simulates selling the specified number of shares at the current market price.
- **Implementation**: Calculates sale price based on mock market data with appropriate price movement relative to base prices. Each stock has defined price movement ranges to simulate different volatility profiles.

### #6 Stock Buy Logic (Algorithm Layer)
- **Input**: `stock_symbol` (string)
- **Output**: String ("YES" or "NO")
- **Purpose**: Contains the core decision-making logic for determining whether to buy a stock.
- **Implementation**: Uses a sophisticated probability-based system that considers stock-specific characteristics. Different stocks have varying buy probabilities to simulate real-world market behavior. For example, growth stocks like AAPL and NVDA have higher buy probabilities, while others have more conservative probabilities.

### #7 Stock Sell Logic (Algorithm Layer)
- **Input**: `stock_symbol` (string), `purchase_price` (decimal)
- **Output**: String ("YES" or "NO")
- **Purpose**: Contains the core decision-making logic for determining whether to sell a stock.
- **Implementation**: Evaluates sell probability based on price difference percentage between purchase and current price. The algorithm applies different strategies for profit scenarios (more likely to sell as profit increases) versus loss scenarios (more likely to hold for small losses, but may cut severe losses). Stock-specific adjustments further refine the sell probability, with some stocks being more likely to be held long-term (e.g., AAPL, MSFT, NVDA) while others are more likely to be sold quickly (e.g., TSLA, META).

## Architecture

The application follows a layered architecture pattern with clear separation of concerns:

1. **Service Layer**
   - Primary interface with the main application and user interface
   - Manages the lifecycle of trading services and transaction workflows
   - Coordinates between API layer, database operations, and state management
   - Example: `StockTradingService` class that handles the trading cycle

2. **API Layer**
   - Provides standardized interfaces for stock operations
   - Handles API-specific concerns like error wrapping and logging
   - Acts as an intermediary between service and algorithm layers
   - Examples: `should_buy_stock()`, `should_sell_stock()`, `purchase_stock()`, and `sell_stock()` functions

3. **Algorithm Layer**
   - Contains core decision-making logic and business rules
   - Implements the specific algorithms for buy/sell decisions
   - Isolated from API concerns to focus purely on decision logic
   - Examples: `should_buy()` and `should_sell()` functions with their pricing models and probability calculations

This layered design provides several benefits:
- **Separation of Concerns**: Each layer has specific responsibilities
- **Maintainability**: Logic can be modified in one layer without affecting others
- **Testability**: Layers can be tested in isolation
- **Flexibility**: Implementation can be changed without altering interfaces

The typical data flow follows this pattern:
1. Service Layer calls API Layer functions
2. API Layer validates inputs and delegates to the Algorithm Layer
3. Algorithm Layer performs calculations and returns decisions
4. API Layer wraps results or errors and returns to Service Layer
5. Service Layer acts on the results (database updates, state changes, etc.)

## Web Dashboard
The application provides a web-based dashboard that allows users to:
- Create new trading services with specified stock symbol and starting balance
- Monitor active services with real-time updates on balances, gains/losses, and share positions
- View transaction history with purchase and sale details
- Start and stop services with immediate visual feedback
- Observe state transitions with clear visual indicators

## Additional Considerations
- **Centralized Constants**: Application-wide constants are centralized for consistency across components.
- **Error Handling**: Comprehensive error handling with specific exception types for different error scenarios.
- **Session Management**: Database session management with proper context handling to prevent leaks.
- **Real-time Updates**: Automatic AJAX updates every 10 seconds to keep the dashboard current without page refreshes.
- **Concurrency**: The system supports multiple stock services running simultaneously in separate threads.
- **Responsive UI**: User-friendly interface with loading states and clear visual feedback on actions.
- **Testing Framework**: Mock implementation of trading APIs allows for testing without connecting to real trading platforms.

## Implementation Priorities

1. **Model First** - Essential data models with proper schema design ✅
2. **Service Development** - Main stock service with trading cycle logic ✅
3. **API Development** - Mock implementations for buying and selling stocks ✅
4. **Algorithm Development** - Sophisticated decision-making algorithms ✅
5. **Frontend Implementation** - Web dashboard with real-time updates ✅
6. **Refinement** - Enhanced UX and error handling ✅
