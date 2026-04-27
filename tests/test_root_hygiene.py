from __future__ import annotations

import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests import conftest as shared_conftest


def test_project_temp_root_fixture_stays_under_repo_local_pytest_tree(
    project_temp_root: Path,
) -> None:
    expected_root = Path.cwd() / "build" / "pytest" / "tmp-fixtures"
    assert project_temp_root.is_relative_to(expected_root)
    assert project_temp_root.name.startswith("session_")


def test_pytest_basetemp_is_not_forced_into_repo_root(pytestconfig) -> None:
    assert pytestconfig.option.basetemp is None


def test_project_temp_dir_factory_creates_dirs_under_repo_local_pytest_tree(
    project_temp_dir,
) -> None:
    with project_temp_dir() as temp_dir:
        path = Path(temp_dir)
        assert path.is_dir()
        assert path.is_relative_to(Path.cwd() / "build" / "pytest" / "tmp-fixtures")


def test_tmp_path_factory_creates_dirs_under_repo_local_pytest_tree(tmp_path_factory) -> None:
    temp_dir = tmp_path_factory.mktemp("factory-check")
    try:
        assert temp_dir.is_dir()
        assert temp_dir.is_relative_to(Path.cwd() / "build" / "pytest" / "tmp-fixtures")
    finally:
        temp_dir.rmdir()


def test_cleanup_script_exists() -> None:
    assert Path("scripts/clean_local_artifacts.ps1").exists()


@pytest.mark.skipif(os.name != "nt", reason="PowerShell cleanup script is Windows-specific")
def test_cleanup_script_removes_repo_local_pytest_tree() -> None:
    repo_root = Path.cwd()
    temp_root = repo_root / "build" / "pytest" / "tmp-fixtures"
    marker = temp_root / "session_cleanup_check" / "marker.txt"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("cleanup", encoding="utf-8")

    subprocess.run(
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(repo_root / "scripts" / "clean_local_artifacts.ps1"),
        ],
        check=True,
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert temp_root.exists() is False
    assert (repo_root / "build" / "pytest").exists() is False


def test_should_preserve_tmp_path_returns_false_for_passing_test() -> None:
    request = SimpleNamespace(
        node=SimpleNamespace(
            rep_setup=SimpleNamespace(failed=False),
            rep_call=SimpleNamespace(failed=False),
        )
    )

    assert shared_conftest._should_preserve_tmp_path(request) is False


def test_should_preserve_tmp_path_returns_true_for_failed_setup() -> None:
    request = SimpleNamespace(
        node=SimpleNamespace(
            rep_setup=SimpleNamespace(failed=True),
            rep_call=SimpleNamespace(failed=False),
        )
    )

    assert shared_conftest._should_preserve_tmp_path(request) is True


def test_should_preserve_tmp_path_returns_true_for_failed_call() -> None:
    request = SimpleNamespace(
        node=SimpleNamespace(
            rep_setup=SimpleNamespace(failed=False),
            rep_call=SimpleNamespace(failed=True),
        )
    )

    assert shared_conftest._should_preserve_tmp_path(request) is True


def test_legacy_core_boundary_directory_removed() -> None:
    assert not Path("src/ms_preprocessing/core").exists()
