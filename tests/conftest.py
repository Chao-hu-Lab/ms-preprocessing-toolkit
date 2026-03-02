"""Pytest configuration and shared fixtures."""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile
import sys

# Ensure src/ is on the import path for tests
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_excel_file(temp_dir):
    """Create a sample Excel file for testing."""
    data = {
        "Mz/RT": ["Sample_Type", "100.123/1.5", "200.456/2.5"],
        "Tolerance": ["na", "20/0.5", "20/0.5"],
        "Sample1": ["case", 5000, 6000],
        "Sample2": ["case", 5500, 6500],
        "QC1": ["qc", 5200, 6200],
    }
    df = pd.DataFrame(data)

    filepath = temp_dir / "test_data.xlsx"
    df.to_excel(filepath, index=False)

    return filepath


@pytest.fixture
def sample_csv_file(temp_dir):
    """Create a sample CSV file for testing."""
    data = {
        "Mz/RT": ["Sample_Type", "100.123/1.5", "200.456/2.5"],
        "Tolerance": ["na", "20/0.5", "20/0.5"],
        "Sample1": ["case", 5000, 6000],
        "Sample2": ["case", 5500, 6500],
    }
    df = pd.DataFrame(data)

    filepath = temp_dir / "test_data.csv"
    df.to_csv(filepath, index=False)

    return filepath
