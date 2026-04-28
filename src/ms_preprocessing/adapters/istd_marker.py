"""Adapter for the Step 2 ISTD marker processor."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd
from ms_core.preprocessing import ISTDMarker as _ISTDMarker
from ms_core.preprocessing import Settings as _CoreSettings

from ms_preprocessing.adapters import _capture_output_path, _persist_adapter_output
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult

_STEP = "istd_marker"
_XIC_REQUIRED_ERROR = (
    "Step2 now requires an XIC Extractor results workbook. "
    "Please set xic_results_file or pass --xic-results-file."
)


def _read_input(input_path: str) -> pd.DataFrame:
    suffix = input_path.lower()
    if suffix.endswith(".parquet"):
        return pd.read_parquet(input_path)
    if suffix.endswith(".csv"):
        return pd.read_csv(input_path)
    if suffix.endswith((".tsv", ".txt")):
        return pd.read_csv(input_path, sep="\t")
    return pd.read_excel(input_path)


def _save_output(df: pd.DataFrame) -> str | None:
    return _persist_adapter_output(
        df,
        step_name=_STEP,
        preferred_root=_CoreSettings.get_parquet_cache_root() / "adapters",
    )


def _coerce_optional_path(path_value: str | Path | None) -> Path | None:
    if path_value is None:
        return None
    path_text = str(path_value).strip()
    return Path(path_text) if path_text else None


def _build_metadata(raw_meta: dict[str, Any]) -> ProcessingMetadata:
    red_font_rows = set(raw_meta.get("red_font_rows") or raw_meta.get("istd_rows") or [])
    protected_rows = set(
        raw_meta.get("protected_rows") or raw_meta.get("istd_rows") or red_font_rows
    )

    return ProcessingMetadata(
        red_font_rows=red_font_rows,
        protected_rows=protected_rows,
        blue_font_cells=list(raw_meta.get("blue_font_cells", [])),
        highlight_rows=set(raw_meta.get("highlight_rows", [])),
    )


def _normalize_error(core_result: Any) -> str:
    if getattr(core_result, "message", None):
        return str(core_result.message)

    errors = getattr(core_result, "errors", None) or []
    if errors:
        return "; ".join(str(error) for error in errors)

    return "Processing failed"


def _merge_user_summary_stats(raw_stats: dict[str, Any], raw_meta: dict[str, Any]) -> dict[str, Any]:
    stats = dict(raw_stats)
    for key in (
        "xic_source_path",
        "xic_target_count",
        "xic_skipped_targets",
        "xic_targets_using_summary_rt",
        "xic_targets_using_midpoint_rt",
        "xic_istd_candidates",
        "xic_istd_chosen_rows",
    ):
        if key in raw_meta:
            stats[key] = raw_meta[key]
    return stats


def _run_processor(
    df: pd.DataFrame,
    *,
    xic_results_file: str | Path | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
) -> ProcessingResult:
    xic_path = _coerce_optional_path(xic_results_file)
    if xic_path is None:
        return ProcessingResult(
            success=False,
            step=_STEP,
            output_path=None,
            data=None,
            metadata=ProcessingMetadata(),
            error=_XIC_REQUIRED_ERROR,
        )

    try:
        processor = _ISTDMarker()
        if progress_callback is not None:
            processor.set_progress_callback(progress_callback)

        core_result = processor.process(
            df,
            xic_results_file=xic_path,
        )
    except Exception as exc:
        return ProcessingResult(
            success=False,
            step=_STEP,
            output_path=None,
            data=None,
            metadata=ProcessingMetadata(),
            error=str(exc),
        )

    output_path = None
    if core_result.success and core_result.data is not None:
        output_path = _capture_output_path(_save_output, core_result.data, step_name=_STEP)

    raw_meta = core_result.metadata if isinstance(core_result.metadata, dict) else {}
    return ProcessingResult(
        success=bool(core_result.success),
        step=_STEP,
        output_path=output_path,
        data=core_result.data,
        metadata=_build_metadata(raw_meta),
        error=None if core_result.success else _normalize_error(core_result),
        statistics=_merge_user_summary_stats(
            dict(getattr(core_result, "statistics", {}) or {}),
            raw_meta,
        ),
    )


def run(
    input_path: str,
    *,
    xic_results_file: str | Path | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
) -> ProcessingResult:
    """Read a file, run the processor, and return a typed result."""
    if not os.path.exists(input_path):
        return ProcessingResult(
            success=False,
            step=_STEP,
            output_path=None,
            data=None,
            metadata=ProcessingMetadata(),
            error=f"Input file not found: {input_path}",
        )

    df = _read_input(input_path)
    return _run_processor(
        df,
        xic_results_file=xic_results_file,
        progress_callback=progress_callback,
    )


def run_from_df(
    df: pd.DataFrame,
    *,
    xic_results_file: str | Path | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
) -> ProcessingResult:
    """Run the processor directly on an in-memory DataFrame."""
    return _run_processor(
        df,
        xic_results_file=xic_results_file,
        progress_callback=progress_callback,
    )
