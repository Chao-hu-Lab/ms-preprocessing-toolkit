"""Pytest configuration and shared fixtures."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import re
import shutil
import sys
import time
from typing import Iterator
import uuid

import numpy as np
import pandas as pd
import pytest
import customtkinter as ctk

# Ensure src/ is on the import path for tests
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PYTEST_ROOT = ROOT / "build" / "pytest"
PROJECT_TEST_TEMP_ROOT = PYTEST_ROOT / "tmp-fixtures"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _session_temp_root() -> Path:
    """Create a repo-local session root without using pytest temp internals."""
    PROJECT_TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    session_root = PROJECT_TEST_TEMP_ROOT / f"session_{uuid.uuid4().hex}"
    session_root.mkdir(parents=True, exist_ok=False)
    return session_root


def _normalize_temp_prefix(name: str) -> str:
    """Convert a node name into a filesystem-safe temp prefix."""
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-")
    return normalized or "tmp-path"


def _remove_tree(path: Path) -> None:
    """Best-effort recursive removal for repo-local temp directories."""
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def _prune_empty_parents(path: Path, *, stop_at: Path) -> None:
    """Remove empty parent directories up to the configured pytest root."""
    current = path
    while True:
        if current == stop_at.parent:
            break
        try:
            current.rmdir()
        except OSError:
            break
        if current == stop_at:
            break
        current = current.parent


def spin_until(ctk_root: ctk.CTk, predicate, timeout: float = 1.5) -> bool:
    """Poll the Tk event loop until predicate() returns True or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ctk_root.update()
        if predicate():
            return True
        time.sleep(0.01)
    ctk_root.update()
    return predicate()


def _should_preserve_tmp_path(request: pytest.FixtureRequest) -> bool:
    """Keep tmp_path artifacts only when setup/call failed, matching failed retention."""
    for phase in ("setup", "call"):
        report = getattr(request.node, f"rep_{phase}", None)
        if report is not None and report.failed:
            return True
    return False


class RepoTmpPathFactory:
    """Minimal tmp_path_factory replacement rooted inside the repository."""

    def __init__(self, base_root: Path) -> None:
        self._base_root = base_root

    def getbasetemp(self) -> Path:
        return self._base_root

    def mktemp(self, basename: str, numbered: bool = True) -> Path:
        prefix = _normalize_temp_prefix(basename)
        suffix = uuid.uuid4().hex if numbered else "shared"
        temp_dir = self._base_root / f"{prefix}-{suffix}"
        temp_dir.mkdir(parents=True, exist_ok=False)
        return temp_dir


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[object]):
    """Expose per-phase reports so custom tmp fixtures can honor retention policy."""
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


@pytest.fixture(scope="session")
def ctk_root():
    """Shared CTk root to avoid multi-root Tcl instability on Windows."""
    root = ctk.CTk()
    root.withdraw()
    try:
        yield root
    finally:
        root.destroy()


@pytest.fixture
def step_widget_factory(ctk_root: ctk.CTk):
    """Factory fixture: create a step widget and auto-destroy on teardown."""
    created: list = []

    def _make(widget_class, step_index: int):
        w = widget_class(ctk_root, step_index=step_index)
        w.pack()
        ctk_root.update_idletasks()
        created.append(w)
        return w

    yield _make

    for w in reversed(created):
        w.destroy()


@pytest.fixture(scope="session")
def project_temp_root() -> Iterator[Path]:
    """Central temp root for tests that need explicit temporary directories."""
    session_root = _session_temp_root()
    try:
        yield session_root
    finally:
        _prune_empty_parents(session_root, stop_at=PYTEST_ROOT)


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
            _remove_tree(temp_dir)

    return _factory


@pytest.fixture
def temp_dir(project_temp_dir):
    """Create a temporary directory for test files."""
    with project_temp_dir(prefix="fixture-") as tmpdir:
        yield tmpdir


@pytest.fixture(scope="session")
def tmp_path_factory(project_temp_root: Path) -> RepoTmpPathFactory:
    """Override pytest's builtin tmp_path_factory with a repo-local factory."""
    return RepoTmpPathFactory(project_temp_root)


@pytest.fixture
def tmp_path(
    request: pytest.FixtureRequest,
    tmp_path_factory: RepoTmpPathFactory,
) -> Iterator[Path]:
    """Override pytest's builtin tmp_path to avoid Windows temp ACL issues."""
    temp_dir = tmp_path_factory.mktemp(request.node.name)
    try:
        yield temp_dir
    finally:
        if not _should_preserve_tmp_path(request):
            _remove_tree(temp_dir)


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
