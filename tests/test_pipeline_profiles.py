"""Tests for integrated Step 1-4 pipeline profiles."""

from __future__ import annotations

import importlib
import json

import pytest

from ms_preprocessing.config.pipeline_profiles import (
    format_pipeline_profile_preview,
    get_pipeline_profile,
)


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
    import ms_preprocessing.config.pipeline_defaults as defaults

    profile = get_pipeline_profile(name)

    assert profile["step1"] == defaults.STEP1_PARAMS
    assert profile["step2"] == defaults.STEP2_PARAMS
    assert profile["step3"] == defaults.STEP3_PARAMS
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
    import ms_preprocessing.config.pipeline_defaults as defaults

    profile = get_pipeline_profile("default")

    profile["step2"]["xic_results_file"] = "mutated.xlsx"

    assert defaults.STEP2_PARAMS["xic_results_file"] != "mutated.xlsx"


def test_pipeline_profiles_follow_reloaded_local_reference_config(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "local_reference_paths.json"
    config_path.write_text(
        json.dumps(
            {
                "method_file": "profile-method.docx",
                "xic_results_file": "profile-xic.xlsx",
            }
        ),
        encoding="utf-8",
    )
    import ms_preprocessing.config.pipeline_defaults as defaults
    import ms_preprocessing.config.pipeline_profiles as profiles

    try:
        with monkeypatch.context() as isolated_env:
            isolated_env.setenv("MSPTK_LOCAL_REFERENCE_CONFIG", str(config_path))
            importlib.reload(defaults)

            profile = profiles.get_pipeline_profile("loose")

            assert profile["step1"]["method_file"] == "profile-method.docx"
            assert profile["step2"]["xic_results_file"] == "profile-xic.xlsx"
    finally:
        importlib.reload(defaults)


def test_pipeline_profile_preview_uses_actual_profile_values() -> None:
    preview = format_pipeline_profile_preview("default")

    assert "Step 1-3: fixed defaults" in preview
    assert "訊號: 5000" in preview
    assert "穩定檢出: 0.33" in preview
    assert "MNAR 出現/缺失: 0.80 / 0.20" in preview
    assert "QC檢出: 0.25" in preview
    assert "強度倍率: off" in preview
