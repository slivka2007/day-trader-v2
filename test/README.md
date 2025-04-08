# Day Trader API Integration Tests

This directory contains integration tests for the Day Trader API. The tests verify that the API endpoints work correctly and integrate properly with the service and model layers.

## Test Structure

The tests are organized by API resource:

- `test_stock_api.py`: Tests for the Stock API endpoints
- `test_daily_price_api.py`: Tests for the Daily Price API endpoints
- `test_intraday_price_api.py`: Tests for the Intraday Price API endpoints

## Setup Files

- `conftest.py`: Contains pytest fixtures for setting up the test environment
- `utils.py`: Contains utility functions for authentication and test data creation
- `run_integration_tests.py`: Script to run all the integration tests

## Running the Tests

To run all integration tests:

```bash
python test/run_integration_tests.py
```

To run tests for a specific API resource:

```bash
python -m pytest test/test_stock_api.py -v
python -m pytest test/test_daily_price_api.py -v
python -m pytest test/test_intraday_price_api.py -v
python -m pytest test/test_user_api.py -v
python -m pytest test/test_trading_service_api.py -v
python -m pytest test/test_transaction_api.py -v
```

## Test Data

The tests create the following test data:

- Test users:

  - Regular user: `testuser` / `TestPassword123!`
  - Admin user: `testadmin` / `TestPassword123!`

- Test stock:

  - Symbol: `AAPL`
  - Name: `Apple Inc.`
  - Sector: `Technology`

- Test price data for the stock (created during test execution)

## Testing Strategy

The integration tests follow these principles:

1. **Isolation**: Each test class creates its own test data
2. **Independence**: Tests can run in any order
3. **Authentication**: Tests verify both authenticated and unauthenticated access
4. **Coverage**: Tests cover all CRUD operations for each resource
5. **Robustness**: Tests handle cases where data may already exist

## Notes for Contributors

When adding new API resources, please create corresponding integration tests following the patterns in the existing test files. Each API resource should have tests for:

- List operations (with filtering and pagination)
- Individual resource retrieval
- Resource creation (with and without authentication)
- Resource updates
- Resource deletion
- Any special operations specific to the resource
