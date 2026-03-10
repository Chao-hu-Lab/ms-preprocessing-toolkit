"""Tests for the Step 4 feature filter widget."""

from __future__ import annotations

import customtkinter as ctk
import pandas as pd
import pytest

from ms_core.preprocessing.base import ProcessingResult
from ms_preprocessing.gui.widgets.feature_filter_widget import FeatureFilterWidget


@pytest.fixture(scope="module")
def ctk_root():
    root = ctk.CTk()
    root.withdraw()
    try:
        yield root
    finally:
        root.destroy()


@pytest.fixture
def widget(ctk_root):
    step4_widget = FeatureFilterWidget(ctk_root, step_index=3)
    step4_widget.pack()
    ctk_root.update_idletasks()
    try:
        yield step4_widget
    finally:
        step4_widget.destroy()


def test_feature_filter_widget_defaults_all_threshold_toggles_to_enabled(widget) -> None:
    params = widget.get_parameters()

    assert widget.bg_enabled_switch.get() == 1
    assert widget.skew_enabled_switch.get() == 1
    assert widget.diff_enabled_switch.get() == 1
    assert widget.qc_ratio_enabled_switch.get() == 1
    assert params["enable_background_threshold"] is True
    assert params["enable_skew_threshold"] is True
    assert params["enable_diff_threshold"] is True
    assert params["enable_qc_ratio_threshold"] is True


def test_feature_filter_widget_disables_matching_inputs_when_toggle_is_off(widget) -> None:
    widget.bg_enabled_switch.deselect()
    widget._sync_threshold_control_states()

    assert widget.bg_slider.cget("state") == "disabled"
    assert widget.bg_entry.cget("state") == "disabled"
    assert widget.get_parameters()["enable_background_threshold"] is False


def test_feature_filter_widget_run_processing_passes_toggle_flags(widget) -> None:
    captured: dict[str, object] = {}

    def fake_process(data, **kwargs):
        captured.update(kwargs)
        return ProcessingResult(success=True, data=data.copy(), statistics={}, metadata={})

    widget._processor.process = fake_process
    input_df = pd.DataFrame(
        {
            "Mz/RT": ["Sample_Type", "100.0/1.0"],
            "Tolerance": ["na", "na"],
            "Case1": ["case", 9000],
            "Control1": ["control", 9000],
            "QC1": ["qc", 9000],
        }
    )

    result = widget.run_processing(
        input_df,
        signal_threshold=5000,
        background_threshold=0.33,
        skew_threshold=0.66,
        diff_threshold=0.30,
        qc_ratio_threshold=0.25,
        enable_background_threshold=True,
        enable_skew_threshold=False,
        enable_diff_threshold=True,
        enable_qc_ratio_threshold=False,
    )

    assert result.equals(input_df)
    assert captured["enable_background_threshold"] is True
    assert captured["enable_skew_threshold"] is False
    assert captured["enable_diff_threshold"] is True
    assert captured["enable_qc_ratio_threshold"] is False
