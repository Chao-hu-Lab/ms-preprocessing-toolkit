"""Adapter for the Step 3 duplicate remover processor."""

from __future__ import annotations

import os
from typing import Any, Callable

import pandas as pd

from ms_core.preprocessing import DuplicateRemover as _DuplicateRemover
from ms_core.preprocessing import Settings as _CoreSettings

from ms_preprocessing.adapters import _capture_output_path, _persist_adapter_output
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult

_STEP = "duplicate_remover"


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


def _build_metadata(raw_meta: dict[str, Any]) -> ProcessingMetadata:
    red_font_rows = set(raw_meta.get("red_font_rows", []))
    protected_rows = set(raw_meta.get("protected_rows") or raw_meta.get("red_font_rows") or [])

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
        error=None if core_result.success else _normalize_error(core_result),
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

    df = _read_input(input_path)
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
