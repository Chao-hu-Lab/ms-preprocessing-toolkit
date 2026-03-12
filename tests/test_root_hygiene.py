from __future__ import annotations

from pathlib import Path


def test_project_temp_root_fixture_stays_under_dot_tmp(project_temp_root: Path) -> None:
    assert project_temp_root.parts[-2:] == (".tmp", "tests")


def test_pytest_basetemp_is_not_forced_into_repo_root(pytestconfig) -> None:
    assert pytestconfig.option.basetemp is None


def test_project_temp_dir_factory_creates_dirs_under_dot_tmp(project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        path = Path(temp_dir)
        assert path.is_dir()
        assert path.parts[-3] == ".tmp"


def test_cleanup_script_exists() -> None:
    assert Path("scripts/clean_local_artifacts.ps1").exists()
