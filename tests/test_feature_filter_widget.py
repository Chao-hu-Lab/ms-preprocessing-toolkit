"""Tests for the Step 4 feature filter widget."""

from __future__ import annotations

import threading
import time

import customtkinter as ctk
import pandas as pd
import pytest

from ms_preprocessing.adapters import feature_filter as feature_filter_adapter
from ms_preprocessing.config.feature_filter_presets import get_step4_preset
from ms_preprocessing.gui.widgets.data_organizer_widget import DataOrganizerWidget
from ms_preprocessing.gui.widgets.feature_filter_widget import FeatureFilterWidget
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult


from tests.conftest import spin_until


@pytest.fixture
def widget(step_widget_factory):
    return step_widget_factory(FeatureFilterWidget, step_index=3)


def test_feature_filter_widget_defaults_keep_fc_gate_disabled(widget) -> None:
    params = widget.get_parameters()

    assert widget.bg_enabled_switch.get() == 1
    assert widget.intensity_fc_enabled_switch.get() == 0
    assert widget.qc_ratio_enabled_switch.get() == 1
    assert params["enable_background_threshold"] is True
    assert params["enable_intensity_fc_threshold"] is False
    assert params["enable_qc_ratio_threshold"] is True
    assert params["high_det_thresh"] == pytest.approx(0.8)
    assert params["low_det_thresh"] == pytest.approx(0.2)
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
        high_det_thresh=0.8,
        low_det_thresh=0.2,
        qc_ratio_threshold=0.25,
        enable_background_threshold=True,
        enable_intensity_fc_threshold=False,
        enable_qc_ratio_threshold=False,
    )

    assert result.equals(input_df)
    assert captured["enable_background_threshold"] is True
    assert captured["enable_intensity_fc_threshold"] is False
    assert captured["enable_qc_ratio_threshold"] is False


def test_feature_filter_widget_apply_parameters_updates_visible_controls(widget) -> None:
    widget.apply_parameters(get_step4_preset("strict"))

    params = widget.get_parameters()

    assert params["signal_threshold"] == pytest.approx(5000.0)
    assert params["background_threshold"] == pytest.approx(0.50)
    assert params["high_det_thresh"] == pytest.approx(0.8)
    assert params["low_det_thresh"] == pytest.approx(0.2)
    assert params["qc_ratio_threshold"] == pytest.approx(0.50)
    assert params["intensity_fc_threshold"] == pytest.approx(3.0, abs=0.01)
    assert params["enable_background_threshold"] is True
    assert params["enable_qc_ratio_threshold"] is True
    assert params["enable_intensity_fc_threshold"] is False


def test_feature_filter_widget_uses_consistent_form_alignment(widget) -> None:
    assert widget.params_frame.grid_columnconfigure(0)["minsize"] == 44
    assert widget.params_frame.grid_columnconfigure(1)["minsize"] == 180
    assert widget.signal_entry.grid_info()["column"] == 2
    assert widget.bg_enabled_switch.grid_info()["column"] == 0
    assert widget.bg_slider.grid_info()["column"] == 2
    assert widget.intensity_fc_enabled_switch.grid_info()["column"] == 0
    assert widget.intensity_fc_slider.grid_info()["column"] == 2
    assert widget.high_det_slider.grid_info()["column"] == 2
    assert widget.low_det_slider.grid_info()["column"] == 2
    assert widget.qc_ratio_enabled_switch.grid_info()["column"] == 0
    assert widget.qc_ratio_slider.grid_info()["column"] == 2
    assert widget.signal_entry.cget("justify") == "center"
    assert widget.bg_entry.cget("justify") == "center"
    assert widget.intensity_fc_entry.cget("justify") == "center"
    assert widget.high_det_entry.cget("justify") == "center"
    assert widget.low_det_entry.cget("justify") == "center"
    assert widget.qc_ratio_entry.cget("justify") == "center"
    assert widget.bg_enabled_switch.winfo_manager() == "grid"
    assert widget.qc_ratio_enabled_switch.winfo_manager() == "grid"
    assert widget.qc_ratio_slider.winfo_manager() == "grid"
    assert widget.qc_ratio_entry.winfo_manager() == "grid"
    assert hasattr(widget, "criteria_textbox")


def test_feature_filter_widget_uses_scrollable_content_panel(widget) -> None:
    assert isinstance(widget._content_frame, ctk.CTkScrollableFrame)


def test_other_steps_keep_non_scrollable_content_panel(ctk_root) -> None:
    step1_widget = DataOrganizerWidget(ctk_root, step_index=0)
    step1_widget.pack()
    ctk_root.update_idletasks()
    try:
        assert isinstance(step1_widget._content_frame, ctk.CTkFrame)
        assert not isinstance(step1_widget._content_frame, ctk.CTkScrollableFrame)
    finally:
        step1_widget.destroy()


def test_feature_filter_widget_omits_redundant_mnar_section_heading(widget) -> None:
    label_texts = [
        child.cget("text")
        for child in widget.params_frame.winfo_children()
        if isinstance(child, ctk.CTkLabel)
    ]

    assert "存在/缺失標記（MNAR 80/20）" not in label_texts


def test_feature_filter_widget_explains_rules_in_plainer_lab_language(widget) -> None:
    criteria_text = widget.criteria_textbox.get("1.0", "end")

    assert "前 3 條是正向保留條件，採 OR 判斷" in criteria_text
    assert "QC_ratio 則是負向覆寫條件" in criteria_text
    assert "至少 2 組的 ratio 都大於等於背景比例門檻" in criteria_text
    assert "fold-change = 最大組平均強度 / 最小組平均強度" in criteria_text


def test_feature_filter_widget_runs_processing_in_background_without_duplicate_runs(
    widget,
    ctk_root,
    monkeypatch,
) -> None:
    monkeypatch.setattr(widget, "_confirm_small_group_run", lambda _: True)

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

    assert spin_until(ctk_root, lambda: not widget.is_processing())
    assert call_count == 1
    assert completions and completions[0].equals(input_df)
    assert any(status == "Worker started" for _, status in progress_updates)
    assert any(status == "Complete!" for _, status in progress_updates)
    assert any("already in progress" in message for message in logs)


def test_feature_filter_widget_defaults_mnar_gate_enabled(widget) -> None:
    params = widget.get_parameters()

    assert widget.mnar_enabled_switch.get() == 1
    assert params["enable_mnar_gate"] is True
    assert params["allow_single_group_stable"] is False


def test_feature_filter_widget_mnar_switch_disables_both_sliders(widget) -> None:
    widget.mnar_enabled_switch.deselect()
    widget._sync_threshold_control_states()

    assert widget.high_det_slider.cget("state") == "disabled"
    assert widget.high_det_entry.cget("state") == "disabled"
    assert widget.low_det_slider.cget("state") == "disabled"
    assert widget.low_det_entry.cget("state") == "disabled"
    assert widget.get_parameters()["enable_mnar_gate"] is False


def test_feature_filter_widget_mnar_switch_in_column_zero(widget) -> None:
    assert widget.mnar_enabled_switch.grid_info()["column"] == 0


def test_feature_filter_widget_single_group_aborts_when_user_cancels(widget, monkeypatch) -> None:
    """When single group detected and user cancels, _on_run_clicked returns without starting."""
    monkeypatch.setattr(widget, "_confirm_single_group_run", lambda: False)

    single_group_df = pd.DataFrame(
        {
            "Mz/RT": ["Sample_Type", "100.0/1.0"],
            "Tolerance": ["na", "na"],
            "Exposure1": ["exposure", 9000],
            "Exposure2": ["exposure", 9000],
            "QC1": ["qc", 9000],
        }
    )
    widget.set_data(single_group_df)
    widget._on_run_clicked()

    assert not widget.is_processing()
    assert widget._allow_single_group_stable is False


def test_feature_filter_widget_single_group_sets_degradation_flag_when_confirmed(
    widget, ctk_root, monkeypatch
) -> None:
    """When single group detected and user confirms, allow_single_group_stable is set True."""
    monkeypatch.setattr(widget, "_confirm_single_group_run", lambda: True)
    monkeypatch.setattr(widget, "_confirm_small_group_run", lambda _: True)

    captured: dict = {}

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

    single_group_df = pd.DataFrame(
        {
            "Mz/RT": ["Sample_Type", "100.0/1.0"],
            "Tolerance": ["na", "na"],
            "Exposure1": ["exposure", 9000],
            "Exposure2": ["exposure", 9000],
            "QC1": ["qc", 9000],
        }
    )
    widget.set_data(single_group_df)
    widget._on_run_clicked()

    assert spin_until(ctk_root, lambda: not widget.is_processing())
    assert captured.get("allow_single_group_stable") is True


def test_feature_filter_widget_two_groups_skips_single_group_dialog(
    widget, ctk_root, monkeypatch
) -> None:
    """With 2+ groups, _confirm_single_group_run is never called."""
    confirm_called = []
    monkeypatch.setattr(
        widget,
        "_confirm_single_group_run",
        lambda: confirm_called.append(True) or True,
    )
    monkeypatch.setattr(widget, "_confirm_small_group_run", lambda _: True)

    def fake_run_from_df(data, **kwargs):
        return ProcessingResult(
            success=True,
            step="feature_filter",
            output_path=None,
            data=data.copy(),
            metadata=ProcessingMetadata(),
            statistics={},
        )

    monkeypatch.setattr(feature_filter_adapter, "run_from_df", fake_run_from_df)

    two_group_df = pd.DataFrame(
        {
            "Mz/RT": ["Sample_Type", "100.0/1.0"],
            "Tolerance": ["na", "na"],
            "Case1": ["case", 9000],
            "Control1": ["control", 9000],
            "QC1": ["qc", 9000],
        }
    )
    widget.set_data(two_group_df)
    widget._on_run_clicked()

    assert spin_until(ctk_root, lambda: not widget.is_processing())
    assert not confirm_called


def test_on_run_shows_small_group_dialog_when_any_group_lt10(widget, monkeypatch) -> None:
    """When any biological group N < 10, _confirm_small_group_run must be called."""
    import pandas as pd

    rows: dict = {"feature": ["Sample_Type", "f1"]}
    for i in range(5):
        rows[f"A_{i + 1}"] = ["a", 10000]
    for i in range(15):
        rows[f"B_{i + 1}"] = ["b", 10000]
    df = pd.DataFrame(rows)
    widget.set_data(df)

    called_with: list[dict] = []

    def fake_confirm(small_groups: dict) -> bool:
        called_with.append(dict(small_groups))
        return False  # user cancels

    monkeypatch.setattr(widget, "_confirm_small_group_run", fake_confirm)

    widget._on_run_clicked()

    assert len(called_with) == 1
    assert "a" in called_with[0]
    assert called_with[0]["a"] == 5


def test_on_run_skips_small_group_dialog_when_all_groups_gte10(widget, monkeypatch) -> None:
    """When all biological groups N >= 10, no small-group dialog shown."""
    import pandas as pd
    from ms_preprocessing.gui.widgets.base_widget import BaseProcessingWidget

    rows: dict = {"feature": ["Sample_Type", "f1"]}
    for i in range(10):
        rows[f"A_{i + 1}"] = ["a", 10000]
    for i in range(12):
        rows[f"B_{i + 1}"] = ["b", 10000]
    df = pd.DataFrame(rows)
    widget.set_data(df)

    confirm_called: list = []
    monkeypatch.setattr(
        widget, "_confirm_small_group_run", lambda _: confirm_called.append(True) or False
    )
    monkeypatch.setattr(BaseProcessingWidget, "_on_run_clicked", lambda self: None)

    widget._on_run_clicked()

    assert len(confirm_called) == 0


def test_adapter_get_group_summary_returns_correct_counts() -> None:
    """get_group_summary returns sample counts for biological groups and QC."""
    rows: dict = {"feature": ["Sample_Type", "f1"]}
    for i in range(3):
        rows[f"A_{i + 1}"] = ["a", 10000]
    for i in range(5):
        rows[f"B_{i + 1}"] = ["b", 10000]
    for i in range(2):
        rows[f"QC_{i + 1}"] = ["qc", 10000]
    df = pd.DataFrame(rows)

    summary = feature_filter_adapter.get_group_summary(df)

    assert summary["groups"]["a"]["sample_count"] == 3
    assert summary["groups"]["b"]["sample_count"] == 5
    assert summary["qc_count"] == 2
    assert summary["has_qc"] is True


def test_run_processing_logs_qc_small_n_note(widget, monkeypatch) -> None:
    """When QC N < 10, run_processing logs per-sample impact percentage."""
    import pandas as pd
    from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult

    def fake_run(data, **kwargs):
        return ProcessingResult(
            success=True,
            step="feature_filter",
            output_path=None,
            data=data.copy(),
            metadata=ProcessingMetadata(),
            statistics={
                "kept_count": 1,
                "deleted_count": 0,
                "qc_count": 7,
                "has_qc": True,
                "groups_detected": 1,
                "final_features": 1,
            },
        )

    monkeypatch.setattr("ms_preprocessing.adapters.feature_filter.run_from_df", fake_run)

    log_messages: list[str] = []
    widget.on_log = lambda msg: log_messages.append(msg)
    widget._data = pd.DataFrame({"f": ["Sample_Type", "f1"]})
    widget.run_processing(widget._data)

    qc_logs = [m for m in log_messages if "QC 提示" in m and "14.3" in m]
    assert len(qc_logs) == 1


def test_run_processing_no_qc_note_when_qc_n_gte10(widget, monkeypatch) -> None:
    """When QC N >= 10, no QC note is logged."""
    import pandas as pd
    from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult

    def fake_run(data, **kwargs):
        return ProcessingResult(
            success=True,
            step="feature_filter",
            output_path=None,
            data=data.copy(),
            metadata=ProcessingMetadata(),
            statistics={
                "kept_count": 1,
                "deleted_count": 0,
                "qc_count": 10,
                "has_qc": True,
                "groups_detected": 1,
                "final_features": 1,
            },
        )

    monkeypatch.setattr("ms_preprocessing.adapters.feature_filter.run_from_df", fake_run)

    log_messages: list[str] = []
    widget.on_log = lambda msg: log_messages.append(msg)
    widget._data = pd.DataFrame({"f": ["Sample_Type", "f1"]})
    widget.run_processing(widget._data)

    qc_warn = [m for m in log_messages if "QC 提示" in m]
    assert len(qc_warn) == 0
