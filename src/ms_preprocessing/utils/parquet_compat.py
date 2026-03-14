"""Shared parquet compatibility helpers for dataframe persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def has_duplicate_columns(df: pd.DataFrame) -> bool:
    """Return whether a dataframe contains duplicate column labels."""
    return bool(df.columns.duplicated().any())


def write_parquet_with_normalized_fallback(
    df: pd.DataFrame,
    output_path: str | Path,
    *,
    index: bool = False,
) -> None:
    """Write parquet, retrying with normalized object columns if needed."""
    try:
        df.to_parquet(output_path, index=index)
    except Exception:
        normalize_dataframe_for_parquet(df).to_parquet(output_path, index=index)


def normalize_dataframe_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize object columns into parquet-friendly scalar values."""
    normalized = df.copy()
    object_positions = [idx for idx, dtype in enumerate(normalized.dtypes) if dtype == "object"]

    for col_idx in object_positions:
        # Use positional indexing so duplicate column labels stay addressable.
        series = normalized.iloc[:, col_idx]
        non_null = series[series.notna()]
        if non_null.empty:
            continue

        if non_null.map(lambda value: isinstance(value, str)).all():
            continue

        if non_null.map(lambda value: isinstance(value, (bytes, bytearray))).all():
            normalized.iloc[:, col_idx] = series.map(_decode_bytes_value).to_numpy()
            continue

        if non_null.map(lambda value: isinstance(value, (int, float, bool, np.number, np.bool_))).all():
            normalized.iloc[:, col_idx] = pd.to_numeric(series, errors="coerce").to_numpy()
            continue

        normalized.iloc[:, col_idx] = series.map(_stringify_mixed_value).to_numpy()

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
