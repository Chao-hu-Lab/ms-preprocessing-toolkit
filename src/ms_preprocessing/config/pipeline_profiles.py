"""
Integrated Step 1-4 pipeline profiles.

These profiles bundle the fixed Step 1-3 parameters with the existing
Step 4 loose/default/strict presets so callers can select one named
configuration for an entire preprocessing run.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from ms_preprocessing.config.feature_filter_presets import (
    PresetName,
    Step4Params,
    get_step4_preset,
)


class PipelineProfile(TypedDict):
    """Complete parameter bundle for a Step 1-4 preprocessing run."""

    step1: dict
    step2: dict
    step3: dict
    step4: Step4Params


PipelineProfileName = Literal["loose", "default", "strict"]


def get_pipeline_profile(name: PipelineProfileName = "default") -> PipelineProfile:
    """
    Return a complete Step 1-4 parameter bundle for the named profile.

    Notes:
        - The input data file is intentionally not part of the profile because it
          varies per run.
        - Step 1-3 reuse the fixed pipeline defaults.
        - Step 4 is selected from the existing loose/default/strict presets.
    """

    from ms_preprocessing.config.pipeline_defaults import STEP1_PARAMS, STEP2_PARAMS, STEP3_PARAMS

    step4_name: PresetName = name
    return {
        "step1": dict(STEP1_PARAMS),
        "step2": dict(STEP2_PARAMS),
        "step3": dict(STEP3_PARAMS),
        "step4": get_step4_preset(step4_name),
    }


def _format_number(value: float) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.2f}"


def format_pipeline_profile_preview(name: PipelineProfileName = "default") -> str:
    """Return the compact sidebar preview for a Run All pipeline profile."""

    profile = get_pipeline_profile(name)
    step4 = profile["step4"]
    intensity_fc = (
        f"{_format_number(step4['intensity_fc_threshold'])}x"
        if step4.get("enable_intensity_fc_threshold")
        else "off"
    )
    return "\n".join(
        [
            "Step 1-3: fixed defaults",
            (
                f"訊號: {_format_number(step4['signal_threshold'])} | "
                f"穩定檢出: {_format_number(step4['background_threshold'])}"
            ),
            (
                f"MNAR 出現/缺失: {float(step4['high_det_thresh']):.2f} / "
                f"{float(step4['low_det_thresh']):.2f} | "
                f"QC檢出: {float(step4['qc_ratio_threshold']):.2f}"
            ),
            f"強度倍率: {intensity_fc}",
        ]
    )

