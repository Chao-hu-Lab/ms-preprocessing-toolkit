"""Smoke guardrail tests for entrypoints and syntax integrity."""

from __future__ import annotations

import py_compile
import re
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


def test_runtime_version_matches_pyproject() -> None:
    from ms_preprocessing import __version__

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', pyproject, re.MULTILINE)

    assert match is not None
    assert __version__ == match.group(1)


def test_parquet_cache_default_enabled() -> None:
    assert Settings.SAVE_PARQUET_CACHE is True


def test_pyinstaller_spec_bundles_builtin_yaml_profiles() -> None:
    spec = (ROOT / "ms-preprocessing.spec").read_text(encoding="utf-8")

    assert "src/ms_preprocessing/resources/builtin_profiles" in spec
    assert "ms_preprocessing/resources/builtin_profiles" in spec


def test_docs_reference_unified_parquet_pipeline_and_zero_missing_behavior() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8", errors="replace")
    design = (
        ROOT / "docs" / "plans" / "2026-03-04-step4-zero-impute-and-performance-design.md"
    ).read_text(encoding="utf-8", errors="replace")
    rollout = (
        ROOT / "docs" / "plans" / "2026-03-05-unified-parquet-v2-rollout-checklist.md"
    )

    assert rollout.exists(), "Rollout checklist must exist"

    assert "Unified Parquet V2" in readme
    assert "Step1-4 intermediate format = parquet" in readme
    assert "final export = xlsx; downstream handoff is manual" in readme
    assert "Step4 zero-as-missing default behavior" in readme

    assert "Unified Parquet V2 Addendum" in design
    assert "rollback checklist" in design.lower()
    assert "troubleshooting checklist" in design.lower()


def test_readme_documents_dependency_override_policy() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8", errors="replace")

    assert "MSPTK_MS_CORE_SRC" in readme
    assert "MSPTK_MS_CORE_ROOT" in readme
    assert "MSPTK_CONFIG_DIR" in readme
    assert "development-only override" in readme
    assert "does not import, launch, or configure downstream normalization projects" in readme


def test_docs_include_conservative_io_go_no_go_and_rollback_criteria() -> None:
    rollout = (
        ROOT / "docs" / "plans" / "2026-03-05-unified-parquet-v2-rollout-checklist.md"
    ).read_text(encoding="utf-8", errors="replace")
    notes_path = (
        ROOT / "docs" / "plans" / "2026-03-05-conservative-io-write-optimization-notes.md"
    )

    assert notes_path.exists(), "Conservative optimization notes must exist"
    notes = notes_path.read_text(encoding="utf-8", errors="replace")

    assert "1497.067" in rollout
    assert "go/no-go" in rollout.lower()
    assert "rollback" in rollout.lower()

    assert "Gate A" in notes
    assert "Gate B" in notes
    assert "keep previous behavior" in notes.lower()
