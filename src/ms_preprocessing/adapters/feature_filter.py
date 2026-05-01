"""Adapter for the Step 4 feature filter processor."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import pandas as pd
from ms_core.preprocessing import FeatureFilter as _FeatureFilter
from ms_core.preprocessing import Settings as _CoreSettings

from ms_preprocessing.adapters import (
    _capture_output_path,
    capture_adapter_output,
    deleted_features_to_dataframe,
    formatting_metadata_from_core,
    normalize_core_error,
    read_input_frame,
)
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult

_STEP = "feature_filter"


def _save_output(df: pd.DataFrame) -> str | None:
    return capture_adapter_output(
        df,
        step_name=_STEP,
        preferred_root=_CoreSettings.get_parquet_cache_root() / "adapters",
    )


def _build_metadata(raw_meta: dict[str, Any]) -> ProcessingMetadata:
    metadata = formatting_metadata_from_core(raw_meta)
    metadata.deleted_feature_df = deleted_features_to_dataframe(raw_meta)
    return metadata


def _run_processor(
    df: pd.DataFrame,
    *,
    background_threshold: float | None = None,
    intensity_fc_threshold: float | None = None,
    ratio_rescue_threshold: float | None = None,
    high_det_thresh: float | None = None,
    low_det_thresh: float | None = None,
    qc_ratio_threshold: float | None = None,
    enable_background_threshold: bool = True,
    enable_intensity_fc_threshold: bool = False,
    enable_qc_ratio_threshold: bool = True,
    enable_mnar_gate: bool = True,
    enable_ratio_rescue: bool = True,
    allow_single_group_stable: bool = False,
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
            ratio_rescue_threshold=ratio_rescue_threshold,
            high_det_thresh=high_det_thresh,
            low_det_thresh=low_det_thresh,
            qc_ratio_threshold=qc_ratio_threshold,
            enable_background_threshold=enable_background_threshold,
            enable_intensity_fc_threshold=enable_intensity_fc_threshold,
            enable_qc_ratio_threshold=enable_qc_ratio_threshold,
            enable_mnar_gate=enable_mnar_gate,
            enable_ratio_rescue=enable_ratio_rescue,
            allow_single_group_stable=allow_single_group_stable,
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
        error=None if core_result.success else normalize_core_error(core_result),
        statistics=dict(getattr(core_result, "statistics", {}) or {}),
    )


def run(
    input_path: str,
    *,
    background_threshold: float | None = None,
    intensity_fc_threshold: float | None = None,
    ratio_rescue_threshold: float | None = None,
    high_det_thresh: float | None = None,
    low_det_thresh: float | None = None,
    qc_ratio_threshold: float | None = None,
    enable_background_threshold: bool = True,
    enable_intensity_fc_threshold: bool = False,
    enable_qc_ratio_threshold: bool = True,
    enable_mnar_gate: bool = True,
    enable_ratio_rescue: bool = True,
    allow_single_group_stable: bool = False,
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

    df = read_input_frame(input_path)
    return _run_processor(
        df,
        background_threshold=background_threshold,
        intensity_fc_threshold=intensity_fc_threshold,
        ratio_rescue_threshold=ratio_rescue_threshold,
        high_det_thresh=high_det_thresh,
        low_det_thresh=low_det_thresh,
        qc_ratio_threshold=qc_ratio_threshold,
        enable_background_threshold=enable_background_threshold,
        enable_intensity_fc_threshold=enable_intensity_fc_threshold,
        enable_qc_ratio_threshold=enable_qc_ratio_threshold,
        enable_mnar_gate=enable_mnar_gate,
        enable_ratio_rescue=enable_ratio_rescue,
        allow_single_group_stable=allow_single_group_stable,
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
    ratio_rescue_threshold: float | None = None,
    high_det_thresh: float | None = None,
    low_det_thresh: float | None = None,
    qc_ratio_threshold: float | None = None,
    enable_background_threshold: bool = True,
    enable_intensity_fc_threshold: bool = False,
    enable_qc_ratio_threshold: bool = True,
    enable_mnar_gate: bool = True,
    enable_ratio_rescue: bool = True,
    allow_single_group_stable: bool = False,
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
        ratio_rescue_threshold=ratio_rescue_threshold,
        high_det_thresh=high_det_thresh,
        low_det_thresh=low_det_thresh,
        qc_ratio_threshold=qc_ratio_threshold,
        enable_background_threshold=enable_background_threshold,
        enable_intensity_fc_threshold=enable_intensity_fc_threshold,
        enable_qc_ratio_threshold=enable_qc_ratio_threshold,
        enable_mnar_gate=enable_mnar_gate,
        enable_ratio_rescue=enable_ratio_rescue,
        allow_single_group_stable=allow_single_group_stable,
        signal_threshold=signal_threshold,
        protected_rows=protected_rows,
        progress_callback=progress_callback,
        **kwargs,
    )


def count_analysis_groups(df: pd.DataFrame) -> int:
    """Return the number of non-QC analysis groups in df.

    Wraps FeatureFilter.count_analysis_groups() so GUI code
    never needs to import ms_core directly.
    """
    return _FeatureFilter().count_analysis_groups(df)


def get_group_summary(df: pd.DataFrame) -> dict[str, Any]:
    """Return group summary including sample counts and QC count.

    Wraps FeatureFilter.get_group_summary() so GUI code
    never needs to import ms_core directly.
    """
    raw = _FeatureFilter().get_group_summary(df)
    return {
        "groups": raw.get("groups", {}),
        "qc_count": raw.get("qc_count", 0),
        "has_qc": raw.get("has_qc", False),
    }
