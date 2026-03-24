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
from ms_preprocessing.config.pipeline_defaults import STEP1_PARAMS, STEP2_PARAMS, STEP3_PARAMS


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

    step4_name: PresetName = name
    return {
        "step1": dict(STEP1_PARAMS),
        "step2": dict(STEP2_PARAMS),
        "step3": dict(STEP3_PARAMS),
        "step4": get_step4_preset(step4_name),
    }

