from __future__ import annotations

import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path

MS_CORE_REPO_NAME = "ms-core"
MS_CORE_SRC_ENV = "MSPTK_MS_CORE_SRC"
MS_CORE_PROJECT_ROOT_ENV = "MSPTK_MS_CORE_ROOT"


@dataclass(frozen=True)
class BootstrapResolution:
    """Describe how a dependency source path was resolved for runtime imports."""

    src_dir: Path | None
    source: str
    added_to_sys_path: bool = False


def _resolve_anchor(start_dir: str | Path | None) -> Path:
    anchor = Path(start_dir) if start_dir is not None else Path(__file__).resolve()
    return anchor.resolve()


def _iter_ancestor_dirs(anchor: Path):
    current = anchor if anchor.is_dir() else anchor.parent
    yield current
    yield from current.parents


def _has_package_src(src_dir: Path, package_name: str) -> bool:
    return (src_dir / package_name).exists()


def _find_toolkit_root(anchor: Path) -> Path | None:
    for base in _iter_ancestor_dirs(anchor):
        if (base / "src" / "ms_preprocessing").exists():
            return base
    return None


def resolve_ms_core_src(start_dir: str | Path | None = None) -> BootstrapResolution:
    env_src = os.environ.get(MS_CORE_SRC_ENV)
    if env_src:
        candidate = Path(env_src).expanduser().resolve()
        if _has_package_src(candidate, "ms_core"):
            return BootstrapResolution(src_dir=candidate, source="env_src")

    env_root = os.environ.get(MS_CORE_PROJECT_ROOT_ENV)
    if env_root:
        candidate = Path(env_root).expanduser().resolve() / "src"
        if _has_package_src(candidate, "ms_core"):
            return BootstrapResolution(src_dir=candidate, source="env_root")

    anchor = _resolve_anchor(start_dir)
    toolkit_root = _find_toolkit_root(anchor)
    if toolkit_root is not None:
        repo_dir = toolkit_root / MS_CORE_REPO_NAME
        if repo_dir.exists():
            worktree_root = repo_dir / ".worktrees"
            if worktree_root.exists():
                preferred = sorted(
                    path
                    for path in worktree_root.glob("*/src")
                    if (path / "ms_core" / "utils" / "bridge_workspace.py").exists()
                )
                for candidate in preferred:
                    if _has_package_src(candidate, "ms_core"):
                        return BootstrapResolution(src_dir=candidate, source="toolkit_worktree_src")

                for candidate in sorted(worktree_root.glob("*/src")):
                    if _has_package_src(candidate, "ms_core"):
                        return BootstrapResolution(src_dir=candidate, source="toolkit_worktree_src")

            src_dir = repo_dir / "src"
            if _has_package_src(src_dir, "ms_core"):
                return BootstrapResolution(src_dir=src_dir, source="toolkit_submodule_src")

    return BootstrapResolution(src_dir=None, source="not_found")


def find_ms_core_src(start_dir: str | Path | None = None) -> Path | None:
    return resolve_ms_core_src(start_dir).src_dir


def bootstrap_ms_core(start_dir: str | Path | None = None) -> BootstrapResolution:
    resolution = resolve_ms_core_src(start_dir)
    src_dir = resolution.src_dir
    if src_dir is not None and str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
        return BootstrapResolution(src_dir=src_dir, source=resolution.source, added_to_sys_path=True)
    return resolution


def _ms_core_bootstrap_error_message() -> str:
    return (
        "Could not locate ms-core for toolkit imports. "
        "Clone this repository with '--recurse-submodules', run "
        "'git submodule update --init --recursive', or set "
        f"{MS_CORE_SRC_ENV} / {MS_CORE_PROJECT_ROOT_ENV} to a valid ms-core checkout."
    )


def ensure_ms_core_src_on_path(start_dir: str | Path | None = None) -> Path | None:
    resolution = bootstrap_ms_core(start_dir)
    if resolution.src_dir is None and importlib.util.find_spec("ms_core") is None:
        raise ModuleNotFoundError(_ms_core_bootstrap_error_message())
    return resolution.src_dir
