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
