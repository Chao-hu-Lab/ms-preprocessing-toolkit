from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import os
from pathlib import Path
import sys

MS_CORE_REPO_NAME = "ms-core"
MS_CORE_SRC_ENV = "MSPTK_MS_CORE_SRC"
MS_CORE_PROJECT_ROOT_ENV = "MSPTK_MS_CORE_ROOT"
DNP_REPO_NAME = "Data_Normalization_project_v2"
DNP_SRC_ENV = "MSPTK_DNP_SRC"
DNP_PROJECT_ROOT_ENV = "MSPTK_DNP_PROJECT_ROOT"


@dataclass(frozen=True)
class BootstrapResolution:
    """Describe how a dependency source path was resolved for runtime imports."""

    src_dir: Path | None
    source: str
    added_to_sys_path: bool = False


def _resolve_anchor(start_dir: str | Path | None) -> Path:
    anchor = Path(start_dir) if start_dir is not None else Path(__file__).resolve()
    return anchor.resolve()


def _has_package_src(src_dir: Path, package_name: str) -> bool:
    return (src_dir / package_name).exists()


def _iter_repo_dirs(anchor: Path, repo_name: str):
    seen: set[Path] = set()
    for base in (anchor, *anchor.parents):
        for repo_dir in (base / repo_name, base / "MS Data process package" / repo_name):
            repo_dir = repo_dir.resolve()
            if repo_dir in seen or not repo_dir.exists():
                continue
            seen.add(repo_dir)
            yield repo_dir


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

    for repo_dir in _iter_repo_dirs(anchor, MS_CORE_REPO_NAME):
        worktree_root = repo_dir / ".worktrees"
        if worktree_root.exists():
            preferred = sorted(
                path
                for path in worktree_root.glob("*/src")
                if (path / "ms_core" / "utils" / "bridge_workspace.py").exists()
            )
            for candidate in preferred:
                if _has_package_src(candidate, "ms_core"):
                    return BootstrapResolution(src_dir=candidate, source="worktree_src")

            for candidate in sorted(worktree_root.glob("*/src")):
                if _has_package_src(candidate, "ms_core"):
                    return BootstrapResolution(src_dir=candidate, source="worktree_src")

        src_dir = repo_dir / "src"
        if _has_package_src(src_dir, "ms_core"):
            return BootstrapResolution(src_dir=src_dir, source="repo_src")

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


def find_dnp_src(
    start_dir: str | Path | None = None,
    *,
    home_dir: str | Path | None = None,
) -> Path | None:
    seen: set[Path] = set()

    env_src = os.environ.get(DNP_SRC_ENV)
    if env_src:
        candidate = Path(env_src).expanduser().resolve()
        seen.add(candidate)
        if (candidate / "metabolomics").exists():
            return candidate

    env_root = os.environ.get(DNP_PROJECT_ROOT_ENV)
    if env_root:
        candidate = Path(env_root).expanduser().resolve() / "src"
        seen.add(candidate)
        if (candidate / "metabolomics").exists():
            return candidate

    anchor = _resolve_anchor(start_dir)
    for repo_dir in _iter_repo_dirs(anchor, DNP_REPO_NAME):
        src_dir = repo_dir / "src"
        resolved = src_dir.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if (resolved / "metabolomics").exists():
            return resolved

    desktop = Path(home_dir).expanduser().resolve() if home_dir is not None else Path.home() / "Desktop"
    desktop_src = (desktop / DNP_REPO_NAME / "src").resolve()
    if desktop_src not in seen and (desktop_src / "metabolomics").exists():
        return desktop_src

    return None


def ensure_dnp_src_on_path(
    start_dir: str | Path | None = None,
    *,
    home_dir: str | Path | None = None,
) -> Path | None:
    src_dir = find_dnp_src(start_dir, home_dir=home_dir)
    if src_dir is not None and str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    return src_dir


def find_dnp_bridge_module(
    start_dir: str | Path | None = None,
    *,
    home_dir: str | Path | None = None,
) -> Path | None:
    src_dir = find_dnp_src(start_dir, home_dir=home_dir)
    if src_dir is None:
        return None
    bridge_module = src_dir / "metabolomics" / "adapters" / "preprocessing_to_dnp.py"
    if bridge_module.exists():
        return bridge_module
    return None


def ensure_dnp_bridge_on_path(
    start_dir: str | Path | None = None,
    *,
    home_dir: str | Path | None = None,
) -> Path | None:
    bridge_module = find_dnp_bridge_module(start_dir, home_dir=home_dir)
    if bridge_module is None:
        return None
    src_dir = bridge_module.parents[2]
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    return src_dir


def find_dnp_main_module(
    start_dir: str | Path | None = None,
    *,
    home_dir: str | Path | None = None,
) -> Path | None:
    src_dir = find_dnp_src(start_dir, home_dir=home_dir)
    if src_dir is None:
        return None
    main_py = src_dir / "metabolomics" / "__main__.py"
    if main_py.exists():
        return main_py
    return None
