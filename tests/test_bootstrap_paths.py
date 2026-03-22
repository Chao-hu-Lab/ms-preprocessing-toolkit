import sys

import pytest

from pathlib import Path

from ms_preprocessing.bootstrap_paths import (
    BootstrapResolution,
    bootstrap_ms_core,
    DNP_PROJECT_ROOT_ENV,
    DNP_SRC_ENV,
    ensure_ms_core_src_on_path,
    find_dnp_bridge_module,
    MS_CORE_PROJECT_ROOT_ENV,
    MS_CORE_SRC_ENV,
    resolve_ms_core_src,
    find_dnp_main_module,
    find_dnp_src,
    find_ms_core_src,
)


def test_find_ms_core_src_prefers_toolkit_submodule_worktree_copy(tmp_path):
    """Toolkit-local ms-core worktree should be preferred over the submodule src."""
    toolkit_root = tmp_path / "Desktop" / "MS Data process package" / "ms-preprocessing-toolkit"
    toolkit_root.mkdir(parents=True, exist_ok=True)
    anchor = toolkit_root / "src" / "ms_preprocessing"
    anchor.mkdir(parents=True, exist_ok=True)

    main_src = toolkit_root / "ms-core" / "src"
    worktree_src = toolkit_root / "ms-core" / ".worktrees" / "cross-project-bridge" / "src"

    (main_src / "ms_core" / "utils").mkdir(parents=True, exist_ok=True)
    (worktree_src / "ms_core" / "utils").mkdir(parents=True, exist_ok=True)
    (worktree_src / "ms_core" / "utils" / "bridge_workspace.py").write_text(
        "# bridge marker",
        encoding="utf-8",
    )

    assert find_ms_core_src(anchor) == worktree_src, (
        f"Expected worktree src at {worktree_src}, got {find_ms_core_src(anchor)}"
    )


def test_find_ms_core_src_supports_env_override(monkeypatch, tmp_path):
    ms_core_src = tmp_path / "custom-ms-core" / "src"
    (ms_core_src / "ms_core").mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv(MS_CORE_SRC_ENV, str(ms_core_src))
    monkeypatch.delenv(MS_CORE_PROJECT_ROOT_ENV, raising=False)

    assert find_ms_core_src(tmp_path) == ms_core_src


def test_resolve_ms_core_src_reports_env_override_source(monkeypatch, tmp_path):
    ms_core_src = tmp_path / "custom-ms-core" / "src"
    (ms_core_src / "ms_core").mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv(MS_CORE_SRC_ENV, str(ms_core_src))
    monkeypatch.delenv(MS_CORE_PROJECT_ROOT_ENV, raising=False)

    resolution = resolve_ms_core_src(tmp_path)

    assert resolution.src_dir == ms_core_src
    assert resolution.source == "env_src"
    assert resolution.added_to_sys_path is False


def test_bootstrap_ms_core_reports_when_it_adds_sys_path(monkeypatch, tmp_path):
    ms_core_src = tmp_path / "custom-ms-core" / "src"
    (ms_core_src / "ms_core").mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv(MS_CORE_SRC_ENV, str(ms_core_src))
    monkeypatch.delenv(MS_CORE_PROJECT_ROOT_ENV, raising=False)
    monkeypatch.setattr(sys, "path", list(sys.path))

    resolution = bootstrap_ms_core(tmp_path)

    assert resolution.src_dir == ms_core_src
    assert resolution.source == "env_src"
    assert resolution.added_to_sys_path is True
    assert sys.path[0] == str(ms_core_src)


def test_bootstrap_ms_core_does_not_duplicate_existing_sys_path(monkeypatch, tmp_path):
    ms_core_src = tmp_path / "custom-ms-core" / "src"
    (ms_core_src / "ms_core").mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv(MS_CORE_SRC_ENV, str(ms_core_src))
    monkeypatch.delenv(MS_CORE_PROJECT_ROOT_ENV, raising=False)
    monkeypatch.setattr(sys, "path", [str(ms_core_src), *sys.path])

    resolution = bootstrap_ms_core(tmp_path)

    assert resolution.src_dir == ms_core_src
    assert resolution.added_to_sys_path is False
    assert sys.path.count(str(ms_core_src)) == 1


def test_find_ms_core_src_uses_project_root_override(monkeypatch, tmp_path):
    ms_core_root = tmp_path / "external-ms-core"
    ms_core_src = ms_core_root / "src"
    (ms_core_src / "ms_core").mkdir(parents=True, exist_ok=True)

    monkeypatch.delenv(MS_CORE_SRC_ENV, raising=False)
    monkeypatch.setenv(MS_CORE_PROJECT_ROOT_ENV, str(ms_core_root))

    assert find_ms_core_src(tmp_path) == ms_core_src


def test_find_ms_core_src_finds_submodule_at_toolkit_root(tmp_path):
    """When ms-core is a git submodule inside the toolkit, bootstrap should find it."""
    # Simulate: ms-preprocessing-toolkit/
    #               ms-core/src/ms_core/   ← submodule layout
    #               src/ms_preprocessing/  ← toolkit source
    toolkit_root = tmp_path / "ms-preprocessing-toolkit"
    submodule_src = toolkit_root / "ms-core" / "src"
    (submodule_src / "ms_core").mkdir(parents=True, exist_ok=True)

    # anchor = toolkit_root/src/ms_preprocessing (simulates __init__.py location)
    anchor = toolkit_root / "src" / "ms_preprocessing"
    anchor.mkdir(parents=True, exist_ok=True)

    result = find_ms_core_src(anchor)
    assert result == submodule_src, f"Expected submodule src at {submodule_src}, got {result}"


def test_find_ms_core_src_ignores_sibling_repo_without_override(tmp_path):
    """Sibling ms-core checkout is dev-only and should not be auto-discovered."""
    toolkit_root = tmp_path / "MS Data process package" / "ms-preprocessing-toolkit"

    sibling_src = tmp_path / "MS Data process package" / "ms-core" / "src"
    (sibling_src / "ms_core").mkdir(parents=True, exist_ok=True)

    anchor = toolkit_root / "src" / "ms_preprocessing"
    anchor.mkdir(parents=True, exist_ok=True)

    result = find_ms_core_src(anchor)
    assert result is None


def test_ensure_ms_core_src_on_path_raises_clear_error_when_missing(monkeypatch, tmp_path):
    monkeypatch.delenv(MS_CORE_SRC_ENV, raising=False)
    monkeypatch.delenv(MS_CORE_PROJECT_ROOT_ENV, raising=False)
    monkeypatch.setattr(
        "ms_preprocessing.bootstrap_paths.resolve_ms_core_src",
        lambda *_a, **_k: BootstrapResolution(src_dir=None, source="not_found"),
    )
    monkeypatch.setattr("ms_preprocessing.bootstrap_paths.importlib.util.find_spec", lambda _name: None)

    with pytest.raises(ModuleNotFoundError) as exc:
        ensure_ms_core_src_on_path(tmp_path)

    message = str(exc.value)
    assert "--recurse-submodules" in message
    assert MS_CORE_SRC_ENV in message
    assert MS_CORE_PROJECT_ROOT_ENV in message


def test_ensure_ms_core_src_on_path_allows_preinstalled_module(monkeypatch, tmp_path):
    monkeypatch.delenv(MS_CORE_SRC_ENV, raising=False)
    monkeypatch.delenv(MS_CORE_PROJECT_ROOT_ENV, raising=False)
    monkeypatch.setattr(
        "ms_preprocessing.bootstrap_paths.resolve_ms_core_src",
        lambda *_a, **_k: BootstrapResolution(src_dir=None, source="not_found"),
    )
    monkeypatch.setattr("ms_preprocessing.bootstrap_paths.importlib.util.find_spec", lambda _name: object())

    assert ensure_ms_core_src_on_path(tmp_path) is None


def test_find_dnp_src_supports_env_override(monkeypatch, tmp_path):
    dnp_src = tmp_path / "custom-dnp" / "src"
    (dnp_src / "metabolomics").mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv(DNP_SRC_ENV, str(dnp_src))
    monkeypatch.delenv(DNP_PROJECT_ROOT_ENV, raising=False)

    assert find_dnp_src(tmp_path) == dnp_src


def test_find_dnp_src_finds_sibling_repo_from_toolkit_root(monkeypatch, tmp_path):
    monkeypatch.delenv(DNP_SRC_ENV, raising=False)
    monkeypatch.delenv(DNP_PROJECT_ROOT_ENV, raising=False)

    toolkit_root = tmp_path / "MS Data process package" / "ms-preprocessing-toolkit"
    anchor = toolkit_root / "src" / "ms_preprocessing"
    anchor.mkdir(parents=True, exist_ok=True)

    dnp_src = tmp_path / "MS Data process package" / "Data_Normalization_project_v2" / "src"
    (dnp_src / "metabolomics").mkdir(parents=True, exist_ok=True)

    assert find_dnp_src(anchor) == dnp_src


def test_find_dnp_main_module_uses_project_root_override(monkeypatch, tmp_path):
    dnp_root = tmp_path / "external-dnp"
    main_py = dnp_root / "src" / "metabolomics" / "__main__.py"
    main_py.parent.mkdir(parents=True, exist_ok=True)
    main_py.write_text("print('ok')", encoding="utf-8")

    monkeypatch.delenv(DNP_SRC_ENV, raising=False)
    monkeypatch.setenv(DNP_PROJECT_ROOT_ENV, str(dnp_root))

    assert find_dnp_main_module(tmp_path) == main_py


def test_find_dnp_bridge_module_uses_src_override(monkeypatch, tmp_path):
    dnp_src = tmp_path / "custom-dnp" / "src"
    bridge_module = dnp_src / "metabolomics" / "adapters" / "preprocessing_to_dnp.py"
    bridge_module.parent.mkdir(parents=True, exist_ok=True)
    bridge_module.write_text("def convert_preprocessing_to_dnp(source, target):\n    return target\n", encoding="utf-8")

    monkeypatch.setenv(DNP_SRC_ENV, str(dnp_src))
    monkeypatch.delenv(DNP_PROJECT_ROOT_ENV, raising=False)

    assert find_dnp_bridge_module(tmp_path) == bridge_module
