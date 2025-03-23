# day-trader-v1
The application is designed to generate revenue by automatically trading stocks.

## Overview
The application is designed to generate revenue by automatically trading stocks in which the user wishes to take a long (bullish) position. It continuously cycles between buying and selling a specified stock based on signals from decision-making APIs until the user disables the service. The system leverages a simple database to track services and transactions, and it integrates with external APIs for trade execution.

## Database Schema
The application uses a relational database with two tables:

- **Stock Service Model**  
  Stores information about each trading service instance:
  - `service_id` (integer, primary key, unique identifier for each service)
  - `stock_symbol` (string, the stock ticker symbol, e.g., "AAPL")
  - `starting_balance` (decimal, initial funds provided by the user)
  - `fund_balance` (decimal, current funds available for trading)
  - `total_gain_loss` (decimal, cumulative profit or loss from completed transactions)
  - `current_number_of_shares` (integer, number of shares currently held)
  - `service_state` (string, "active" or "inactive", indicating if the service is running)
  - `service_mode` (string, "buy" or "sell", current operational mode)
  - `start_date` (datetime, timestamp when the service was initiated)
  - `number_of_buy_transactions` (integer, count of completed buy transactions)
  - `number_of_sell_transactions` (integer, count of completed sell transactions)

- **Stock Transaction Model**  
  Tracks individual buy and sell actions for each service:
  - `service_id` (integer, foreign key referencing Stock Service Model)
  - `transaction_id` (integer, primary key, unique identifier for each transaction)
  - `stock_symbol` (string, the stock ticker symbol)
  - `number_of_shares` (integer, number of shares bought and eventually sold)
  - `purchase_price` (decimal, price per share at purchase)
  - `sale_price` (decimal, price per share at sale, null until sold)
  - `gain_loss` (decimal, profit or loss, calculated as `(sale_price - purchase_price) * number_of_shares`, null until sold)
  - `date_time_of_purchase` (datetime, timestamp of purchase)
  - `date_time_of_sale` (datetime, timestamp of sale, null until sold)

## User Input
The user provides:
- **Stock Symbol**: The ticker symbol of the stock to trade (e.g., "AAPL").
- **Fund Amount**: The initial amount of money to allocate (recorded as `starting_balance`).

## Components

### #1 Stock Service (Build Now)
Manages the trading cycle for a specific stock symbol, alternating between "buy" and "sell" modes based on API signals.

- **Initialization**:
  - Creates a new record in the Service Table:
    - `service_id`: Auto-generated unique ID
    - `stock_symbol`: User-provided stock symbol
    - `starting_balance`: User-provided fund amount
    - `fund_balance`: Set to `starting_balance`
    - `total_gain_loss`: 0
    - `current_number_of_shares`: 0
    - `service_state`: "active"
    - `service_mode`: "buy"
    - `start_date`: Current timestamp
    - `number_of_buy_transactions`: 0
    - `number_of_sell_transactions`: 0

- **Trading Cycle**:
  - Runs continuously while `service_state` is "active":
    - **Buy Mode**:
      - Calls the **Buy API (#2)** with `stock_symbol`.
      - If "yes" is returned:
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
        - Sets `service_mode` to "sell".
      - If "no" is returned:
        - Waits for a configurable interval (e.g., 5 minutes) before retrying.
    - **Sell Mode**:
      - Verifies `current_number_of_shares` > 0 (to ensure there are shares to sell).
      - Calls the **Sell API (#3)** with `stock_symbol` and `purchase_price` from the last open transaction.
      - If "yes" is returned:
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
        - Sets `service_mode` to "buy".
      - If "no" is returned:
        - Waits for a configurable interval (e.g., 5 minutes) before retrying.

- **Termination**:
  - User sets `service_state` to "inactive", stopping the cycle. Open positions (unsold shares) remain until further user action.

### #2 Stock Buy API (Build Later)
- **Input**: `stock_symbol` (string)
- **Output**: Boolean ("yes" or "no")
- **Purpose**: Determines whether to buy the stock based on historical market data, real-time market data, and news sentiment.

### #3 Stock Sell API (Build Later)
- **Input**: `stock_symbol` (string), `purchase_price` (decimal)
- **Output**: Boolean ("yes" or "no")
- **Purpose**: Determines whether to sell the stock based on the purchase price, historical market data, real-time market data, and news sentiment.

### #4 Stock Purchase API (Build Now)
- **Input**: `stock_symbol` (string), `fund_balance` (decimal, funds available)
- **Output**: `number_of_shares` (integer), `purchase_price` (decimal), `date_time_of_purchase` (datetime)
- **Purpose**: Uses Alpaca APIs to buy as many shares as possible at the current market price with the provided funds. Waits until the order is executed before returning.

### #5 Stock Sale API (Build Now)
- **Input**: `stock_symbol` (string), `number_of_shares` (integer)
- **Output**: `sale_price` (decimal), `date_time_of_sale` (datetime)
- **Purpose**: Uses Alpaca APIs to sell the specified number of shares at the current market price. Waits until the order is executed before returning.

## Additional Considerations
- **Concurrency**: The system should support multiple stock services running simultaneously, with atomic database updates to prevent race conditions.
- **Error Handling**: Handle API timeouts, insufficient funds, and Alpaca API constraints (e.g., rate limits, market hours).
- **Polling Interval**: Configurable delay between API calls (e.g., 5 minutes) to balance responsiveness and resource usage.
- **Monitoring**: The main application should provide a way to view service status and transaction history (future enhancement).

## Implementation Priorities

1. **Model First** - Start with essential data models
2. **Service Development** - Build the main stock service
3. **API Development** - Build APIs that facilitate the purchasing and selling of stock via Alpaca API endpoints, and, build the APIs that call the stock buying and stock selling algorithms
4. **Frontend Implementation** - Create UI for essential flows
5. **Refinement** - Enhance UX and add additional features
6. **Algorithm Development** Build the stock buying and selling logic 
