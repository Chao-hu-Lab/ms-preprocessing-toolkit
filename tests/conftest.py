"""Pytest configuration and shared fixtures."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import shutil
import sys
import uuid

import numpy as np
import pandas as pd
import pytest
import customtkinter as ctk

# Ensure src/ is on the import path for tests
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TMP_ROOT = ROOT / ".tmp"
PROJECT_TEST_TEMP_ROOT = TMP_ROOT / "tests"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(scope="session")
def ctk_root():
    """Shared CTk root to avoid multi-root Tcl instability on Windows."""
    root = ctk.CTk()
    root.withdraw()
    try:
        yield root
    finally:
        root.destroy()


@pytest.fixture(scope="session")
def project_temp_root() -> Path:
    """Central temp root for tests that need explicit temporary directories."""
    PROJECT_TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    return PROJECT_TEST_TEMP_ROOT


@pytest.fixture
def project_temp_dir(project_temp_root: Path):
    """Factory for temporary directories kept under the repo-local temp root."""

    @contextmanager
    def _factory(prefix: str = "case-"):
        temp_dir = project_temp_root / f"{prefix}{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=False)
        try:
            yield temp_dir
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    return _factory


@pytest.fixture
def temp_dir(project_temp_dir):
    """Create a temporary directory for test files."""
    with project_temp_dir(prefix="fixture-") as tmpdir:
        yield tmpdir


@pytest.fixture
def tmp_path(project_temp_dir) -> Path:
    """Override pytest's builtin tmp_path to avoid Windows temp ACL issues."""
    with project_temp_dir(prefix="tmp-path-") as tmpdir:
        yield tmpdir


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
