# day-trader-v1
The application is designed to generate revenue by automatically trading stocks.

## Overview
The application is designed to generate revenue by automatically trading stocks inputted by the user. It continuously cycles between buying and selling a specified stock based on signals from decision-making services until the user disables the service. The system leverages a simple database to track services and transactions, and it integrates with a mock trading system that simulates market behavior for testing purposes. A web dashboard allows users to monitor and control trading services in real-time.

## User Input
The user provides:
- **Stock Symbol**: The ticker symbol of the stock to trade (e.g., "AAPL").
- **Fund Amount**: The initial amount of money to allocate (recorded as `initial_balance`).

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