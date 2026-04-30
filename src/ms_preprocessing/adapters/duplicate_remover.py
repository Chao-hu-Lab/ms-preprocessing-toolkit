"""Adapter for the Step 3 duplicate remover processor."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import pandas as pd
from ms_core.preprocessing import DuplicateRemover as _DuplicateRemover
from ms_core.preprocessing import Settings as _CoreSettings

from ms_preprocessing.adapters import (
    _capture_output_path,
    capture_adapter_output,
    formatting_metadata_from_core,
    normalize_core_error,
    read_input_frame,
)
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult

_STEP = "duplicate_remover"


def _save_output(df: pd.DataFrame) -> str | None:
    return capture_adapter_output(
        df,
        step_name=_STEP,
        preferred_root=_CoreSettings.get_parquet_cache_root() / "adapters",
    )


def _build_metadata(raw_meta: dict[str, Any]) -> ProcessingMetadata:
    return formatting_metadata_from_core(raw_meta)


def _run_processor(
    df: pd.DataFrame,
    *,
    mz_tolerance_ppm: float | None = None,
    rt_tolerance: float | None = None,
    merge_mode: str | None = None,
    top_n: int | None = None,
    protected_rows: set[int] | None = None,
    enable_degeneracy_annotation: bool | None = None,
    degeneracy_ppm_tolerance: float | None = None,
    degeneracy_rt_tolerance: float | None = None,
    degeneracy_correlation_threshold: float | None = None,
    degeneracy_min_correlation_points: int | None = None,
    degeneracy_adduct_table_file: str | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
    **kwargs,
) -> ProcessingResult:
    try:
        processor = _DuplicateRemover()
        if progress_callback is not None:
            processor.set_progress_callback(progress_callback)

        core_result = processor.process(
            df,
            mz_tolerance_ppm=mz_tolerance_ppm,
            rt_tolerance=rt_tolerance,
            merge_mode=merge_mode,
            top_n=top_n,
            protected_rows=protected_rows or set(),
            enable_degeneracy_annotation=enable_degeneracy_annotation,
            degeneracy_ppm_tolerance=degeneracy_ppm_tolerance,
            degeneracy_rt_tolerance=degeneracy_rt_tolerance,
            degeneracy_correlation_threshold=degeneracy_correlation_threshold,
            degeneracy_min_correlation_points=degeneracy_min_correlation_points,
            degeneracy_adduct_table_file=degeneracy_adduct_table_file,
            **kwargs,
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
        statistics=dict(getattr(core_result, "statistics", {}) or {}),
    )


def run(
    input_path: str,
    *,
    mz_tolerance_ppm: float | None = None,
    rt_tolerance: float | None = None,
    merge_mode: str | None = None,
    top_n: int | None = None,
    protected_rows: set[int] | None = None,
    enable_degeneracy_annotation: bool | None = None,
    degeneracy_ppm_tolerance: float | None = None,
    degeneracy_rt_tolerance: float | None = None,
    degeneracy_correlation_threshold: float | None = None,
    degeneracy_min_correlation_points: int | None = None,
    degeneracy_adduct_table_file: str | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
    **kwargs,
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
        mz_tolerance_ppm=mz_tolerance_ppm,
        rt_tolerance=rt_tolerance,
        merge_mode=merge_mode,
        top_n=top_n,
        protected_rows=protected_rows,
        enable_degeneracy_annotation=enable_degeneracy_annotation,
        degeneracy_ppm_tolerance=degeneracy_ppm_tolerance,
        degeneracy_rt_tolerance=degeneracy_rt_tolerance,
        degeneracy_correlation_threshold=degeneracy_correlation_threshold,
        degeneracy_min_correlation_points=degeneracy_min_correlation_points,
        degeneracy_adduct_table_file=degeneracy_adduct_table_file,
        progress_callback=progress_callback,
        **kwargs,
    )


def run_from_df(
    df: pd.DataFrame,
    *,
    mz_tolerance_ppm: float | None = None,
    rt_tolerance: float | None = None,
    merge_mode: str | None = None,
    top_n: int | None = None,
    protected_rows: set[int] | None = None,
    enable_degeneracy_annotation: bool | None = None,
    degeneracy_ppm_tolerance: float | None = None,
    degeneracy_rt_tolerance: float | None = None,
    degeneracy_correlation_threshold: float | None = None,
    degeneracy_min_correlation_points: int | None = None,
    degeneracy_adduct_table_file: str | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
    **kwargs,
) -> ProcessingResult:
    """Run the processor directly on an in-memory DataFrame."""
    return _run_processor(
        df,
        mz_tolerance_ppm=mz_tolerance_ppm,
        rt_tolerance=rt_tolerance,
        merge_mode=merge_mode,
        top_n=top_n,
        protected_rows=protected_rows,
        enable_degeneracy_annotation=enable_degeneracy_annotation,
        degeneracy_ppm_tolerance=degeneracy_ppm_tolerance,
        degeneracy_rt_tolerance=degeneracy_rt_tolerance,
        degeneracy_correlation_threshold=degeneracy_correlation_threshold,
        degeneracy_min_correlation_points=degeneracy_min_correlation_points,
        degeneracy_adduct_table_file=degeneracy_adduct_table_file,
        progress_callback=progress_callback,
        **kwargs,
    )
