"""Tests for Step 4 preset definitions."""

from __future__ import annotations

import pytest

from ms_preprocessing.config.feature_filter_presets import get_step4_preset


@pytest.mark.parametrize(
    ("name", "expected_qc_ratio"),
    [
        ("loose", 0.00),
        ("default", 0.25),
        ("strict", 0.50),
    ],
)
def test_step4_presets_use_expected_qc_ratio_thresholds(name: str, expected_qc_ratio: float) -> None:
    params = get_step4_preset(name)

    assert params["qc_ratio_threshold"] == pytest.approx(expected_qc_ratio)


@pytest.mark.parametrize(
    ("name", "expected_high", "expected_low"),
    [
        ("loose", 0.3, 0.1),
        ("default", 0.8, 0.2),
        ("strict", 0.8, 0.2),
    ],
)
def test_step4_presets_have_mnar_thresholds(
    name: str, expected_high: float, expected_low: float
) -> None:
    """All presets must expose high_det_thresh and low_det_thresh for the MNAR gate."""
    params = get_step4_preset(name)

    assert params["high_det_thresh"] == pytest.approx(expected_high)
    assert params["low_det_thresh"] == pytest.approx(expected_low)
    assert params["high_det_thresh"] > params["low_det_thresh"]


@pytest.mark.parametrize("name", ["loose", "default", "strict"])
def test_step4_presets_disable_intensity_fc_by_default(name: str) -> None:
    params = get_step4_preset(name)

    assert params["enable_intensity_fc_threshold"] is False


@pytest.mark.parametrize("name", ["loose", "default", "strict"])
def test_step4_presets_do_not_contain_diff_threshold(name: str) -> None:
    """diff_threshold was removed; presets must not expose it."""
    params = get_step4_preset(name)

    assert "diff_threshold" not in params
    assert "enable_diff_threshold" not in params


@pytest.mark.parametrize(
    ("name", "expected_ratio_rescue"),
    [
        ("loose", 2.0),
        ("default", 3.0),
        ("strict", 3.0),
    ],
)
def test_step4_presets_expose_ratio_rescue_threshold(
    name: str, expected_ratio_rescue: float
) -> None:
    params = get_step4_preset(name)

    assert params["ratio_rescue_threshold"] == pytest.approx(expected_ratio_rescue)


@pytest.mark.parametrize("name", ["loose", "default", "strict"])
def test_step4_presets_enable_ratio_rescue_by_default(name: str) -> None:
    params = get_step4_preset(name)

    assert params["enable_ratio_rescue"] is True
