from pathlib import Path

from ms_preprocessing.bootstrap_paths import find_ms_core_src


def test_find_ms_core_src_prefers_worktree_copy(tmp_path):
    """Worktree copy with bridge marker should be preferred over main src."""
    toolkit_root = tmp_path / "Desktop" / "MS Data process package" / "ms-preprocessing-toolkit"
    toolkit_root.mkdir(parents=True, exist_ok=True)

    main_src = tmp_path / "Desktop" / "MS Data process package" / "ms-core" / "src"
    worktree_src = (
        tmp_path
        / "Desktop"
        / "MS Data process package"
        / "ms-core"
        / ".worktrees"
        / "cross-project-bridge"
        / "src"
    )

    (main_src / "ms_core" / "utils").mkdir(parents=True, exist_ok=True)
    (worktree_src / "ms_core" / "utils").mkdir(parents=True, exist_ok=True)
    (worktree_src / "ms_core" / "utils" / "bridge_workspace.py").write_text(
        "# bridge marker",
        encoding="utf-8",
    )

    assert find_ms_core_src(toolkit_root) == worktree_src, (
        f"Expected worktree src at {worktree_src}, got {find_ms_core_src(toolkit_root)}"
    )


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


def test_find_ms_core_src_submodule_takes_priority_over_sibling(tmp_path):
    """Submodule (closer in dir tree) should win over sibling repo."""
    toolkit_root = tmp_path / "MS Data process package" / "ms-preprocessing-toolkit"

    # Submodule inside toolkit
    submodule_src = toolkit_root / "ms-core" / "src"
    (submodule_src / "ms_core").mkdir(parents=True, exist_ok=True)

    # Sibling repo (further up the tree)
    sibling_src = tmp_path / "MS Data process package" / "ms-core" / "src"
    (sibling_src / "ms_core").mkdir(parents=True, exist_ok=True)

    anchor = toolkit_root / "src" / "ms_preprocessing"
    anchor.mkdir(parents=True, exist_ok=True)

    result = find_ms_core_src(anchor)
    assert result == submodule_src, (
        f"Submodule should take priority over sibling; got {result}"
    )
