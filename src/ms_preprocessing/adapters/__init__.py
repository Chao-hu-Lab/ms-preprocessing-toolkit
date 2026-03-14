"""Adapter layer for app-facing access to ms_core processors.

Adapters are the only application-layer modules that should import from
``ms_core`` directly. Each adapter returns
``ms_preprocessing.utils.results.ProcessingResult``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


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
    try:
        df.to_parquet(output_path, index=False)
    except Exception:
        _normalize_for_parquet(df).to_parquet(output_path, index=False)


def _normalize_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    object_positions = [
        idx for idx, dtype in enumerate(normalized.dtypes)
        if dtype == "object"
    ]

    for col_idx in object_positions:
        series = normalized.iloc[:, col_idx]
        non_null = series[series.notna()]
        if non_null.empty:
            continue

        if non_null.map(lambda value: isinstance(value, str)).all():
            continue

        if non_null.map(lambda value: isinstance(value, (bytes, bytearray))).all():
            converted = series.map(_decode_bytes_value)
            normalized.iloc[:, col_idx] = converted.to_numpy()
            continue

        if non_null.map(lambda value: isinstance(value, (int, float, bool, np.number, np.bool_))).all():
            converted = pd.to_numeric(series, errors="coerce")
            normalized.iloc[:, col_idx] = converted.to_numpy()
            continue

        converted = series.map(_stringify_mixed_value)
        normalized.iloc[:, col_idx] = converted.to_numpy()

    return normalized


def _decode_bytes_value(value: Any) -> Any:
    if value is None:
        return np.nan
    try:
        if pd.isna(value):
            return np.nan
    except Exception:
        pass
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", errors="replace")
    return value


def _stringify_mixed_value(value: Any) -> Any:
    if value is None:
        return np.nan
    try:
        if pd.isna(value):
            return np.nan
    except Exception:
        pass
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", errors="replace")
    return str(value)
