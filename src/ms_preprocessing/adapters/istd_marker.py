"""Adapter for the Step 2 ISTD marker processor."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd
from ms_core.preprocessing import ISTDMarker as _ISTDMarker
from ms_core.preprocessing import Settings as _CoreSettings

from ms_preprocessing.adapters import (
    _capture_output_path,
    capture_adapter_output,
    formatting_metadata_from_core,
    normalize_core_error,
    read_input_frame,
)
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult

_STEP = "istd_marker"
_XIC_REQUIRED_ERROR = (
    "Step2 now requires an XIC Extractor results workbook. "
    "Please set xic_results_file or pass --xic-results-file."
)


def _save_output(df: pd.DataFrame) -> str | None:
    return capture_adapter_output(
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
    return formatting_metadata_from_core(
        raw_meta,
        red_aliases=("istd_rows",),
    )


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
        error=None if core_result.success else normalize_core_error(core_result),
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

    df = read_input_frame(input_path)
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
