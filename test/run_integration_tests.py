#!/usr/bin/env python

"""Script to run integration tests for the Day Trader API.

This script runs pytest with the necessary configuration to test the API.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

if __name__ == "__main__":
    # Add the parent directory to the path so we can import the app
    sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

    # Run pytest with the following arguments:
    # -v: verbose output
    # --tb=short: short traceback
    # -xvs: exit on first failure, verbose, don't capture output
    exit_code: int | pytest.ExitCode = pytest.main(["-v", "--tb=short", "-xvs", "test"])

    sys.exit(exit_code)
