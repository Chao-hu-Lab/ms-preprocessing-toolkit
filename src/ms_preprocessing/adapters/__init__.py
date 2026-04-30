"""Adapter layer for app-facing access to ms_core processors.

Adapters are the only application-layer modules that should import from
``ms_core`` directly. Each adapter returns
``ms_preprocessing.utils.results.ProcessingResult``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from time import time_ns
from typing import Any

import pandas as pd

from ms_preprocessing.utils.parquet_compat import write_parquet_with_normalized_fallback
from ms_preprocessing.utils.results import ProcessingMetadata

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


def read_input_frame(input_path: str) -> pd.DataFrame:
    """Read an adapter input file into a DataFrame."""
    suffix = input_path.lower()
    if suffix.endswith(".parquet"):
        return pd.read_parquet(input_path)
    if suffix.endswith(".csv"):
        return pd.read_csv(input_path)
    if suffix.endswith((".tsv", ".txt")):
        return pd.read_csv(input_path, sep="\t")
    return pd.read_excel(input_path)


def capture_adapter_output(
    df: pd.DataFrame,
    *,
    step_name: str,
    preferred_root: Path,
) -> str | None:
    """Persist a successful adapter result to the standard handoff cache."""
    return _capture_output_path(
        lambda output_df: _persist_adapter_output(
            output_df,
            step_name=step_name,
            preferred_root=preferred_root,
        ),
        df,
        step_name=step_name,
    )


def normalize_core_error(core_result: Any) -> str:
    """Return a stable app-layer error string from an ms-core result."""
    if getattr(core_result, "message", None):
        return str(core_result.message)

    errors = getattr(core_result, "errors", None) or []
    if errors:
        return "; ".join(str(error) for error in errors)

    return "Processing failed"


def formatting_metadata_from_core(
    raw_meta: dict[str, Any],
    *,
    red_aliases: tuple[str, ...] = (),
) -> ProcessingMetadata:
    """Convert common ms-core formatting metadata into app-layer metadata."""
    red_source = raw_meta.get("red_font_rows", [])
    for alias in red_aliases:
        if raw_meta.get(alias):
            red_source = raw_meta.get(alias)
            break

    red_font_rows = set(red_source or [])
    protected_rows = set(raw_meta.get("protected_rows") or red_source or [])
    return ProcessingMetadata(
        red_font_rows=red_font_rows,
        protected_rows=protected_rows,
        blue_font_cells=list(raw_meta.get("blue_font_cells", [])),
        highlight_rows=set(raw_meta.get("highlight_rows", [])),
    )


def deleted_features_to_dataframe(raw_meta: dict[str, Any]) -> pd.DataFrame | None:
    """Normalize ms-core deleted feature metadata to a DataFrame."""
    deleted_feature_df = raw_meta.get("deleted_feature_df")
    if isinstance(deleted_feature_df, pd.DataFrame):
        return deleted_feature_df

    deleted_features = raw_meta.get("deleted_features") or []
    if not deleted_features:
        return None

    try:
        first = deleted_features[0]
        if isinstance(first, pd.Series):
            return pd.DataFrame(
                [row.tolist() for row in deleted_features],
                columns=list(first.index),
            )
        return pd.DataFrame(deleted_features)
    except Exception:
        return None
