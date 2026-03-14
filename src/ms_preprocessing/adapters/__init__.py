"""Adapter layer for app-facing access to ms_core processors.

Adapters are the only application-layer modules that should import from
``ms_core`` directly. Each adapter returns
``ms_preprocessing.utils.results.ProcessingResult``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ms_preprocessing.utils.parquet_compat import write_parquet_with_normalized_fallback


def _prepare_cache_root(preferred_root: Path) -> Path:
    """Create the preferred cache root, falling back to a repo-local temp dir."""
    try:
        preferred_root.mkdir(parents=True, exist_ok=True)
        return preferred_root
    except OSError:
        fallback_root = Path.cwd() / ".tmp" / "adapters-cache"
        fallback_root.mkdir(parents=True, exist_ok=True)
        return fallback_root


def _write_parquet_output(df: pd.DataFrame, output_path: Path) -> None:
    """Persist a dataframe to parquet, normalizing mixed object columns if needed."""
    write_parquet_with_normalized_fallback(df, output_path, index=False)
