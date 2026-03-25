"""Tests for the Step 4 feature filter widget."""

from __future__ import annotations

import threading
import time

import pandas as pd
import pytest

from ms_preprocessing.adapters import feature_filter as feature_filter_adapter
from ms_preprocessing.config.feature_filter_presets import get_step4_preset
from ms_preprocessing.gui.widgets.feature_filter_widget import FeatureFilterWidget
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult


def _spin_until(ctk_root, predicate, timeout: float = 1.5) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ctk_root.update()
        if predicate():
            return True
        time.sleep(0.01)
    ctk_root.update()
    return predicate()

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
    assert widget.intensity_fc_enabled_switch.get() == 1
    assert widget.diff_enabled_switch.get() == 1
    assert widget.qc_ratio_enabled_switch.get() == 1
    assert params["enable_background_threshold"] is True
    assert params["enable_intensity_fc_threshold"] is True
    assert params["enable_diff_threshold"] is True
    assert params["enable_qc_ratio_threshold"] is True
    assert params["diff_threshold"] == pytest.approx(0.25)
    assert params["qc_ratio_threshold"] == pytest.approx(0.25)


def test_feature_filter_widget_disables_matching_inputs_when_toggle_is_off(widget) -> None:
    widget.bg_enabled_switch.deselect()
    widget._sync_threshold_control_states()

    assert widget.bg_slider.cget("state") == "disabled"
    assert widget.bg_entry.cget("state") == "disabled"
    assert widget.get_parameters()["enable_background_threshold"] is False


def test_feature_filter_widget_run_processing_passes_toggle_flags(widget, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_from_df(data, **kwargs):
        captured.update(kwargs)
        return ProcessingResult(
            success=True,
            step="feature_filter",
            output_path=None,
            data=data.copy(),
            metadata=ProcessingMetadata(),
            statistics={},
        )

    monkeypatch.setattr(feature_filter_adapter, "run_from_df", fake_run_from_df)
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
        intensity_fc_threshold=2.0,
        diff_threshold=0.30,
        qc_ratio_threshold=0.25,
        enable_background_threshold=True,
        enable_intensity_fc_threshold=False,
        enable_diff_threshold=True,
        enable_qc_ratio_threshold=False,
    )

    assert result.equals(input_df)
    assert captured["enable_background_threshold"] is True
    assert captured["enable_intensity_fc_threshold"] is False
    assert captured["enable_diff_threshold"] is True
    assert captured["enable_qc_ratio_threshold"] is False


def test_feature_filter_widget_apply_parameters_updates_visible_controls(widget) -> None:
    widget.apply_parameters(get_step4_preset("strict"))

    params = widget.get_parameters()

    assert params["signal_threshold"] == pytest.approx(5000.0)
    assert params["background_threshold"] == pytest.approx(0.50)
    assert params["diff_threshold"] == pytest.approx(0.35)
    assert params["qc_ratio_threshold"] == pytest.approx(0.50)
    assert params["intensity_fc_threshold"] == pytest.approx(3.0)
    assert params["enable_background_threshold"] is True
    assert params["enable_diff_threshold"] is True
    assert params["enable_qc_ratio_threshold"] is True
    assert params["enable_intensity_fc_threshold"] is True


def test_feature_filter_widget_uses_consistent_form_alignment(widget) -> None:
    assert widget.params_frame.grid_columnconfigure(0)["minsize"] == 180
    assert widget.signal_entry.grid_info()["column"] == 1
    assert widget.bg_slider.grid_info()["column"] == 1
    assert widget.intensity_fc_slider.grid_info()["column"] == 1
    assert widget.diff_slider.grid_info()["column"] == 1
    assert widget.qc_ratio_slider.grid_info()["column"] == 1
    assert widget.signal_entry.cget("justify") == "center"
    assert widget.bg_entry.cget("justify") == "center"
    assert widget.intensity_fc_entry.cget("justify") == "center"
    assert widget.diff_entry.cget("justify") == "center"
    assert widget.qc_ratio_entry.cget("justify") == "center"
    assert hasattr(widget, "criteria_textbox")


def test_feature_filter_widget_explains_rules_in_plainer_lab_language(widget) -> None:
    criteria_text = widget.criteria_textbox.get("1.0", "end")

    assert "前 3 條是正向保留條件，採 OR 判斷" in criteria_text
    assert "QC_ratio 則是負向覆寫條件" in criteria_text
    assert "至少 2 組的 ratio 都大於等於背景比例門檻" in criteria_text
    assert "fold-change = 最大組平均強度 / 最小組平均強度" in criteria_text
    assert "只有保留下來的 feature 才會進入後續缺失值補值流程" in criteria_text
    assert "把 0 與缺失值一起視為待補值" in criteria_text
    assert "高於訊號門檻的樣本比例 < 40%" in criteria_text
    assert "最小正值的 1/5 進行保守補值" in criteria_text


def test_feature_filter_widget_runs_processing_in_background_without_duplicate_runs(
    widget,
    ctk_root,
    monkeypatch,
) -> None:
    call_started = threading.Event()
    release_worker = threading.Event()
    progress_updates: list[tuple[float, str]] = []
    completions: list[pd.DataFrame] = []
    logs: list[str] = []
    call_count = 0

    def fake_run_from_df(data, **kwargs):
        nonlocal call_count
        call_count += 1
        call_started.set()
        kwargs["progress_callback"](25, "Worker started")
        release_worker.wait(timeout=1.0)
        return ProcessingResult(
            success=True,
            step="feature_filter",
            output_path=None,
            data=data.copy(),
            metadata=ProcessingMetadata(),
            statistics={},
        )

    def on_complete(result: pd.DataFrame, metadata=None) -> None:
        _ = metadata
        completions.append(result.copy())

    monkeypatch.setattr(feature_filter_adapter, "run_from_df", fake_run_from_df)
    widget._on_progress = lambda value, status: progress_updates.append((value, status))
    widget.on_complete = on_complete
    widget.on_log = logs.append
    input_df = pd.DataFrame(
        {
            "Mz/RT": ["Sample_Type", "100.0/1.0"],
            "Tolerance": ["na", "na"],
            "Case1": ["case", 9000],
            "Control1": ["control", 9000],
            "QC1": ["qc", 9000],
        }
    )
    widget.set_data(input_df)

    started_at = time.monotonic()
    widget._on_run_clicked()
    elapsed = time.monotonic() - started_at

    assert elapsed < 0.1
    assert call_started.wait(timeout=0.2)
    assert widget.is_processing() is True

    widget._on_run_clicked()
    release_worker.set()

    assert _spin_until(ctk_root, lambda: not widget.is_processing())
    assert call_count == 1
    assert completions and completions[0].equals(input_df)
    assert any(status == "Worker started" for _, status in progress_updates)
    assert any(status == "Complete!" for _, status in progress_updates)
    assert any("already in progress" in message for message in logs)
