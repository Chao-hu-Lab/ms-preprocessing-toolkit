"""Adapter for the Step 2 ISTD marker processor."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from ms_core.preprocessing import ISTDMarker as _ISTDMarker
from ms_core.preprocessing import Settings as _CoreSettings

from ms_preprocessing.adapters import _capture_output_path, _persist_adapter_output
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult

_STEP = "istd_marker"
_DEFAULT_ISTD_MZ: tuple[float, ...] | None = None


def get_default_istd_mz() -> tuple[float, ...]:
    """Expose default ISTD targets without leaking core imports into widgets."""
    global _DEFAULT_ISTD_MZ
    if _DEFAULT_ISTD_MZ is None:
        _DEFAULT_ISTD_MZ = tuple(_ISTDMarker().config.default_istd_mz)
    return _DEFAULT_ISTD_MZ


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


def _run_processor(
    df: pd.DataFrame,
    *,
    istd_features: set[str] | None = None,
    custom_tolerances: dict[str, tuple[float, float]] | None = None,
    istd_mz_list: list[float] | None = None,
    istd_record_file: str | Path | None = None,
    istd_record_date: str | None = None,
    keep_istd_rows: bool = True,
    ppm_tolerance: float | None = None,
    rt_tolerance: float | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
    **kwargs,
) -> ProcessingResult:
    try:
        processor = _ISTDMarker()
        if progress_callback is not None:
            processor.set_progress_callback(progress_callback)
        if ppm_tolerance is not None:
            processor.config.default_ppm_tolerance = ppm_tolerance
        if rt_tolerance is not None:
            processor.config.default_rt_tolerance = rt_tolerance

        core_result = processor.process(
            df,
            istd_features=istd_features,
            custom_tolerances=custom_tolerances,
            istd_mz_list=istd_mz_list,
            istd_record_file=Path(istd_record_file) if istd_record_file else None,
            istd_record_date=istd_record_date,
            keep_istd_rows=keep_istd_rows,
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
    istd_features: set[str] | None = None,
    custom_tolerances: dict[str, tuple[float, float]] | None = None,
    istd_mz_list: list[float] | None = None,
    istd_record_file: str | Path | None = None,
    istd_record_date: str | None = None,
    keep_istd_rows: bool = True,
    ppm_tolerance: float | None = None,
    rt_tolerance: float | None = None,
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
        istd_features=istd_features,
        custom_tolerances=custom_tolerances,
        istd_mz_list=istd_mz_list,
        istd_record_file=istd_record_file,
        istd_record_date=istd_record_date,
        keep_istd_rows=keep_istd_rows,
        ppm_tolerance=ppm_tolerance,
        rt_tolerance=rt_tolerance,
        progress_callback=progress_callback,
        **kwargs,
    )


def run_from_df(
    df: pd.DataFrame,
    *,
    istd_features: set[str] | None = None,
    custom_tolerances: dict[str, tuple[float, float]] | None = None,
    istd_mz_list: list[float] | None = None,
    istd_record_file: str | Path | None = None,
    istd_record_date: str | None = None,
    keep_istd_rows: bool = True,
    ppm_tolerance: float | None = None,
    rt_tolerance: float | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
    **kwargs,
) -> ProcessingResult:
    """Run the processor directly on an in-memory DataFrame."""
    return _run_processor(
        df,
        istd_features=istd_features,
        custom_tolerances=custom_tolerances,
        istd_mz_list=istd_mz_list,
        istd_record_file=istd_record_file,
        istd_record_date=istd_record_date,
        keep_istd_rows=keep_istd_rows,
        ppm_tolerance=ppm_tolerance,
        rt_tolerance=rt_tolerance,
        progress_callback=progress_callback,
        **kwargs,
    )
