"""Adapter layer for app-facing access to ms_core processors.

Adapters are the only application-layer modules that should import from
``ms_core`` directly. Each adapter returns
``ms_preprocessing.utils.results.ProcessingResult``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from time import time_ns
from typing import Callable

import pandas as pd

from ms_preprocessing.utils.parquet_compat import write_parquet_with_normalized_fallback

logger = logging.getLogger(__name__)


def _prepare_cache_root(preferred_root: Path) -> Path:
    """Create the preferred cache root, falling back to a repo-local temp dir."""
    try:
        preferred_root.mkdir(parents=True, exist_ok=True)
        return preferred_root
    except OSError:
        fallback_root = _fallback_cache_root()
        fallback_root.mkdir(parents=True, exist_ok=True)
        return fallback_root


def _write_parquet_output(df: pd.DataFrame, output_path: Path) -> None:
    """Persist a dataframe to parquet, normalizing mixed object columns if needed."""
    write_parquet_with_normalized_fallback(df, output_path, index=False)


def _fallback_cache_root() -> Path:
    return Path.cwd() / ".tmp" / "adapters-cache"


def _build_handoff_path(cache_root: Path, step_name: str) -> Path:
    return cache_root / f"{step_name}_{time_ns()}.parquet"


def _persist_adapter_output(
    df: pd.DataFrame,
    *,
    step_name: str,
    preferred_root: Path,
) -> str | None:
    """Persist adapter handoff output, retrying in the repo-local fallback cache."""
    primary_root = _prepare_cache_root(preferred_root)
    primary_path = _build_handoff_path(primary_root, step_name)

    try:
        _write_parquet_output(df, primary_path)
        return str(primary_path)
    except Exception as primary_exc:
        fallback_root = _prepare_cache_root(_fallback_cache_root())
        fallback_path = _build_handoff_path(fallback_root, step_name)

        if fallback_path != primary_path:
            try:
                _write_parquet_output(df, fallback_path)
                logger.warning(
                    "Adapter handoff for %s fell back to %s after primary cache write failed: %s",
                    step_name,
                    fallback_path,
                    primary_exc,
                )
                return str(fallback_path)
            except Exception as fallback_exc:
                logger.warning(
                    "Adapter handoff for %s failed in both primary and fallback caches: %s; %s",
                    step_name,
                    primary_exc,
                    fallback_exc,
                )
                return None

        logger.warning(
            "Adapter handoff for %s could not be persisted in fallback cache: %s",
            step_name,
            primary_exc,
        )
        return None


def _capture_output_path(
    save_output: Callable[[pd.DataFrame], str | None],
    df: pd.DataFrame,
    *,
    step_name: str,
) -> str | None:
    """Keep adapter success semantics stable even when handoff persistence fails."""
    try:
        return save_output(df)
    except Exception as exc:
        logger.warning("Adapter handoff for %s raised unexpectedly: %s", step_name, exc)
        return None
