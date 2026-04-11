"""Tests for integrated Step 1-4 pipeline profiles."""

from __future__ import annotations

import pytest

from ms_preprocessing.config.pipeline_defaults import STEP1_PARAMS, STEP2_PARAMS, STEP3_PARAMS
from ms_preprocessing.config.pipeline_profiles import get_pipeline_profile


@pytest.mark.parametrize(
    ("name", "expected_qc_ratio", "expected_bg", "expected_fc"),
    [
        ("loose", 0.00, 0.20, 1.5),
        ("default", 0.25, 0.33, 2.0),
        ("strict", 0.50, 0.50, 3.0),
    ],
)
def test_pipeline_profiles_bundle_fixed_step1_to_step3_with_named_step4(
    name: str,
    expected_qc_ratio: float,
    expected_bg: float,
    expected_fc: float,
) -> None:
    profile = get_pipeline_profile(name)

    assert profile["step1"] == STEP1_PARAMS
    assert profile["step2"] == STEP2_PARAMS
    assert profile["step3"] == STEP3_PARAMS
    assert profile["step3"]["enable_degeneracy_annotation"] is False
    assert profile["step3"]["degeneracy_ppm_tolerance"] == pytest.approx(20.0)
    assert profile["step3"]["degeneracy_rt_tolerance"] == pytest.approx(0.05)
    assert profile["step3"]["degeneracy_correlation_threshold"] == pytest.approx(0.8)
    assert profile["step3"]["degeneracy_min_correlation_points"] == 3
    assert profile["step3"]["degeneracy_adduct_table_file"] == ""
    assert profile["step4"]["qc_ratio_threshold"] == pytest.approx(expected_qc_ratio)
    assert profile["step4"]["high_det_thresh"] == pytest.approx(0.8)
    assert profile["step4"]["low_det_thresh"] == pytest.approx(0.2)
    assert profile["step4"]["background_threshold"] == pytest.approx(expected_bg)
    assert profile["step4"]["intensity_fc_threshold"] == pytest.approx(expected_fc)
    assert profile["step4"]["enable_intensity_fc_threshold"] is False


def test_pipeline_profiles_return_copies_of_mutable_step_dicts() -> None:
    profile = get_pipeline_profile("default")

    profile["step2"]["ppm_tolerance"] = 99.0

    assert STEP2_PARAMS["ppm_tolerance"] == pytest.approx(20.0)
