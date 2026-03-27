"""Adapter for the Step 4 feature filter processor."""

from __future__ import annotations

import os
from typing import Any, Callable

import pandas as pd

from ms_core.preprocessing.ms_quality_filter import FeatureFilter as _FeatureFilter
from ms_core.preprocessing.settings import Settings as _CoreSettings

from ms_preprocessing.adapters import _capture_output_path, _persist_adapter_output
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult

_STEP = "feature_filter"


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


def _deleted_features_to_dataframe(raw_meta: dict[str, Any]) -> pd.DataFrame | None:
    deleted_feature_df = raw_meta.get("deleted_feature_df")
    if isinstance(deleted_feature_df, pd.DataFrame):
        return deleted_feature_df

    deleted_features = raw_meta.get("deleted_features") or []
    if not deleted_features:
        return None

    try:
        first = deleted_features[0]
        if isinstance(first, pd.Series):
            return pd.DataFrame([row.tolist() for row in deleted_features], columns=list(first.index))
        return pd.DataFrame(deleted_features)
    except Exception:
        return None


def _build_metadata(raw_meta: dict[str, Any]) -> ProcessingMetadata:
    red_font_rows = set(raw_meta.get("red_font_rows", []))
    protected_rows = set(raw_meta.get("protected_rows") or raw_meta.get("red_font_rows") or [])

    return ProcessingMetadata(
        red_font_rows=red_font_rows,
        protected_rows=protected_rows,
        highlight_rows=set(raw_meta.get("highlight_rows", [])),
        deleted_feature_df=_deleted_features_to_dataframe(raw_meta),
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
    background_threshold: float | None = None,
    intensity_fc_threshold: float | None = None,
    diff_threshold: float | None = None,
    qc_ratio_threshold: float | None = None,
    enable_background_threshold: bool = True,
    enable_intensity_fc_threshold: bool = True,
    enable_diff_threshold: bool = True,
    enable_qc_ratio_threshold: bool = True,
    signal_threshold: float | None = None,
    protected_rows: set[int] | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
    **kwargs,
) -> ProcessingResult:
    try:
        processor = _FeatureFilter()
        if progress_callback is not None:
            processor.set_progress_callback(progress_callback)
        if signal_threshold is not None:
            processor.config.signal_threshold = signal_threshold

        core_result = processor.process(
            df,
            background_threshold=background_threshold,
            intensity_fc_threshold=intensity_fc_threshold,
            diff_threshold=diff_threshold,
            qc_ratio_threshold=qc_ratio_threshold,
            enable_background_threshold=enable_background_threshold,
            enable_intensity_fc_threshold=enable_intensity_fc_threshold,
            enable_diff_threshold=enable_diff_threshold,
            enable_qc_ratio_threshold=enable_qc_ratio_threshold,
            protected_rows=protected_rows or set(),
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
    background_threshold: float | None = None,
    intensity_fc_threshold: float | None = None,
    diff_threshold: float | None = None,
    qc_ratio_threshold: float | None = None,
    enable_background_threshold: bool = True,
    enable_intensity_fc_threshold: bool = True,
    enable_diff_threshold: bool = True,
    enable_qc_ratio_threshold: bool = True,
    signal_threshold: float | None = None,
    protected_rows: set[int] | None = None,
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
        background_threshold=background_threshold,
        intensity_fc_threshold=intensity_fc_threshold,
        diff_threshold=diff_threshold,
        qc_ratio_threshold=qc_ratio_threshold,
        enable_background_threshold=enable_background_threshold,
        enable_intensity_fc_threshold=enable_intensity_fc_threshold,
        enable_diff_threshold=enable_diff_threshold,
        enable_qc_ratio_threshold=enable_qc_ratio_threshold,
        signal_threshold=signal_threshold,
        protected_rows=protected_rows,
        progress_callback=progress_callback,
        **kwargs,
    )


def run_from_df(
    df: pd.DataFrame,
    *,
    background_threshold: float | None = None,
    intensity_fc_threshold: float | None = None,
    diff_threshold: float | None = None,
    qc_ratio_threshold: float | None = None,
    enable_background_threshold: bool = True,
    enable_intensity_fc_threshold: bool = True,
    enable_diff_threshold: bool = True,
    enable_qc_ratio_threshold: bool = True,
    signal_threshold: float | None = None,
    protected_rows: set[int] | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
    **kwargs,
) -> ProcessingResult:
    """Run the processor directly on an in-memory DataFrame."""
    return _run_processor(
        df,
        background_threshold=background_threshold,
        intensity_fc_threshold=intensity_fc_threshold,
        diff_threshold=diff_threshold,
        qc_ratio_threshold=qc_ratio_threshold,
        enable_background_threshold=enable_background_threshold,
        enable_intensity_fc_threshold=enable_intensity_fc_threshold,
        enable_diff_threshold=enable_diff_threshold,
        enable_qc_ratio_threshold=enable_qc_ratio_threshold,
        signal_threshold=signal_threshold,
        protected_rows=protected_rows,
        progress_callback=progress_callback,
        **kwargs,
    )
