"""Resolve user-visible config locations for profiles and references."""

from __future__ import annotations

import os
import sys
from pathlib import Path

CONFIG_DIR_ENV = "MSPTK_CONFIG_DIR"


def _source_checkout_config_dir() -> Path | None:
    """Return the source checkout config directory when running from a repo."""

    current_file = Path(__file__).resolve()
    for parent in current_file.parents:
        config_dir = parent / "config"
        package_dir = parent / "src" / "ms_preprocessing"
        if config_dir.exists() and package_dir.exists():
            return config_dir
    return None


def user_config_dir() -> Path:
    """Return the directory for local user configuration files.

    The open-source checkout keeps examples under ``config/``. Installed and
    frozen users should be able to use the same directory shape from the
    process working directory, or point to an explicit config root.
    """
    override = os.getenv(CONFIG_DIR_ENV)
    if override:
        return Path(override).expanduser()

    cwd_config = Path.cwd() / "config"
    if cwd_config.exists():
        return cwd_config

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "config"

    source_config = _source_checkout_config_dir()
    if source_config is not None:
        return source_config

    return cwd_config
