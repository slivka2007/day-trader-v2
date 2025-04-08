#!/usr/bin/env python

"""Script to run all integration tests for the Day Trader application.

This script runs the integration tests and generates a report.
"""

import subprocess
import sys
from pathlib import Path

# Define test modules to run
TEST_MODULES: list[str] = [
    "test_user_api.py",
    "test_stock_api.py",
    "test_daily_price_api.py",
    "test_intraday_price_api.py",
    "test_trading_service_api.py",
    "test_transaction_api.py",
    "test_yfinance_integration.py",
]

# Get the directory of this script
script_dir: Path = Path(__file__).parent

# Execute pytest with the test modules
if __name__ == "__main__":
    # Format command to run pytest
    cmd: list[str] = [
        sys.executable,
        "-m",
        "pytest",
        "-v",
    ] + [str(script_dir / module) for module in TEST_MODULES]

    # Run the tests
    result: subprocess.CompletedProcess[bytes] = subprocess.run(cmd, check=False)  # noqa: S603
    sys.exit(result.returncode)
