"""Adapter for the Step 1 data organizer processor."""

from __future__ import annotations

import os
from typing import Any, Callable

import pandas as pd

from ms_core.preprocessing.data_organizer import DataOrganizer as _DataOrganizer
from ms_core.preprocessing.settings import Settings as _CoreSettings

from ms_preprocessing.adapters import _capture_output_path, _persist_adapter_output
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult

_STEP = "data_organizer"


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
    sample_info = raw_meta.get("sample_info")
    if not isinstance(sample_info, pd.DataFrame):
        sample_info = None

    return ProcessingMetadata(
        red_font_rows=red_font_rows,
        protected_rows=protected_rows,
        blue_font_cells=list(raw_meta.get("blue_font_cells", [])),
        highlight_rows=set(raw_meta.get("highlight_rows", [])),
        sample_info=sample_info,
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
    method_file: str | None = None,
    mz_decimals: int = 4,
    rt_decimals: int = 2,
    sample_type_mapping: dict[str, str] | None = None,
    mode: str = "normalization",
    auto_detect: bool = False,
    progress_callback: Callable[[float, str], None] | None = None,
    **kwargs,
) -> ProcessingResult:
    try:
        processor = _DataOrganizer()
        if progress_callback is not None:
            processor.set_progress_callback(progress_callback)

        resolved_mapping = sample_type_mapping
        if auto_detect and not resolved_mapping:
            resolved_mapping = processor.auto_detect_sample_types(list(df.columns[2:]))

        core_result = processor.process(
            df,
            method_file=method_file,
            mz_decimals=mz_decimals,
            rt_decimals=rt_decimals,
            sample_type_mapping=resolved_mapping,
            mode=mode,
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
    method_file: str | None = None,
    mz_decimals: int = 4,
    rt_decimals: int = 2,
    sample_type_mapping: dict[str, str] | None = None,
    mode: str = "normalization",
    auto_detect: bool = False,
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
        method_file=method_file,
        mz_decimals=mz_decimals,
        rt_decimals=rt_decimals,
        sample_type_mapping=sample_type_mapping,
        mode=mode,
        auto_detect=auto_detect,
        progress_callback=progress_callback,
        **kwargs,
    )


def run_from_df(
    df: pd.DataFrame,
    *,
    method_file: str | None = None,
    mz_decimals: int = 4,
    rt_decimals: int = 2,
    sample_type_mapping: dict[str, str] | None = None,
    mode: str = "normalization",
    auto_detect: bool = False,
    progress_callback: Callable[[float, str], None] | None = None,
    **kwargs,
) -> ProcessingResult:
    """Run the processor directly on an in-memory DataFrame."""
    return _run_processor(
        df,
        method_file=method_file,
        mz_decimals=mz_decimals,
        rt_decimals=rt_decimals,
        sample_type_mapping=sample_type_mapping,
        mode=mode,
        auto_detect=auto_detect,
        progress_callback=progress_callback,
        **kwargs,
    )
