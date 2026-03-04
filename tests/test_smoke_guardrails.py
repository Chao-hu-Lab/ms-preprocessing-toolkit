"""Smoke guardrail tests for entrypoints and syntax integrity."""

from __future__ import annotations

import py_compile
import subprocess
import sys
from pathlib import Path

from ms_core.preprocessing.settings import Settings


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def test_all_source_files_compile() -> None:
    """All Python sources should be syntactically valid."""
    files = [ROOT / "main.py", *sorted(SRC.rglob("*.py"))]
    for file_path in files:
        py_compile.compile(str(file_path), doraise=True)


def test_cli_version_smoke() -> None:
    """CLI entrypoint should start and return version info."""
    result = subprocess.run(
        [sys.executable, "main.py", "--version"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "MS Preprocessing Toolkit v" in result.stdout


def test_parquet_cache_default_enabled() -> None:
    assert Settings.SAVE_PARQUET_CACHE is True
