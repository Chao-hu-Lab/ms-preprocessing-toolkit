"""Regression tests for GUI sidebar workflow labels."""

from __future__ import annotations

import queue
import threading
from pathlib import Path

import customtkinter as ctk
import pandas as pd

from ms_preprocessing.gui.event_handlers import MainWindowEventHandlersMixin
from ms_preprocessing.gui.layout import MainWindowLayoutMixin
from ms_preprocessing.gui.pipeline_session import PipelineSession
from ms_preprocessing.utils.file_handler import FileHandler


class _SidebarHarness(MainWindowLayoutMixin, ctk.CTkFrame):
    def __init__(self, master) -> None:
        super().__init__(master)
        self._current_step = 0
        self._completed_steps = set()
        self._step_output_paths = {}
        self._context = {}
        self._create_sidebar()

    def _switch_step(self, step_index: int) -> None:
        self._current_step = step_index

    def _export_results(self):
        return None

    def _open_output_folder(self) -> None:
        return None

    def _run_all_steps(self) -> None:
        return None

    def _export_to_dnp(self) -> None:
        return None


class _ContentAreaHarness(MainWindowLayoutMixin, ctk.CTkFrame):
    def __init__(self, master) -> None:
        super().__init__(master)
        self._current_step = 0
        self._completed_steps = set()
        self._step_output_paths = {}
        self._context = {}
        self._create_content_area()

    def _load_file_for_step(self, step_index: int) -> None:
        self._current_step = step_index

    def _on_step_complete(self, *_args, **_kwargs) -> None:
        return None

    def _log(self, _message: str) -> None:
        return None

    def _update_action_bar_progress(self, _value: float, _status: str = "") -> None:
        return None

    def _run_current_step(self) -> None:
        return None

    def _reset_current_step(self) -> None:
        return None

    def _clear_log(self) -> None:
        return None


class _MainWindowHarness(MainWindowEventHandlersMixin, MainWindowLayoutMixin, ctk.CTkFrame):
    def __init__(self, master, tmp_path: Path) -> None:
        super().__init__(master)
        self._project_root = tmp_path
        self._output_dir = tmp_path / "OUTPUT"
        self._file_handler = FileHandler()
        self._current_data = None
        self._original_data = None
        self._source_file = None
        self._current_step = 0
        self._last_completed_step = None
        self._last_run_all = False
        self._completed_steps: set[int] = set()
        self._pipeline_session = PipelineSession(output_dir=self._output_dir, source_file=None)
        self._step_output_paths = self._pipeline_session.step_output_paths
        self._context = self._pipeline_session.context
        self._source_context_snapshot = None
        self._last_materialized_export_path = None
        self._ui_thread_id = threading.get_ident()
        self._ui_queue = queue.SimpleQueue()
        self._ui_queue_after_id = None
        self._pipeline_worker_thread = None
        self._pipeline_is_processing = False

        self._create_layout()
        self._apply_pipeline_profile_to_widgets("default", log=True)


def test_main_window_sidebar_uses_expected_workflow_labels(ctk_root) -> None:
    app = _SidebarHarness(ctk_root)
    app.pack()
    ctk_root.update_idletasks()
    try:
        assert [btn.cget("text") for btn in app.step_buttons] == [
            "1. 資料整理",
            "2. ISTD 標記",
            "3. 重複訊號刪除",
            "4. 特徵篩選",
        ]
    finally:
        app.destroy()


def test_main_window_sidebar_exposes_run_all_profile_selector(ctk_root) -> None:
    app = _SidebarHarness(ctk_root)
    app.pack()
    ctk_root.update_idletasks()
    try:
        assert app.sidebar_title_label.cget("text") == "MS Preprocessing Toolkit"
        assert "\n" not in app.sidebar_title_label.cget("text")
        assert app.sidebar.cget("fg_color") == "#1E1E1E"
        assert app.pipeline_preset_label.cget("text") == "Run All Preset"
        assert app.run_all_profile_var.get() == "default"
        assert app.run_all_profile_menu.cget("values") == ["loose", "default", "strict"]
        assert not hasattr(app, "run_all_profile_preview_label")
        assert app.run_all_btn.cget("text") == "Run All"
        assert app.run_all_btn.cget("fg_color") == "#2E8B57"
        assert app.export_results_btn.cget("text") == "Export Results"
        assert app.open_output_folder_btn.cget("text") == "Open Output Folder"
        assert app.open_output_folder_btn.cget("fg_color") == "#333333"
        assert app.open_output_folder_btn.cget("border_width") == 1
        assert app.export_dnp_btn.cget("state") == "disabled"
        assert app.export_dnp_btn.cget("fg_color") == "transparent"
    finally:
        app.destroy()


def test_main_window_startup_logs_default_profile_details(ctk_root, tmp_path) -> None:
    app = _MainWindowHarness(ctk_root, tmp_path)
    app.pack(fill="both", expand=True)
    ctk_root.update_idletasks()
    try:
        log_text = app.log_text.get("1.0", "end")

        assert "Applied Run All preset: default" in log_text
        assert "Preset parameters:" in log_text
        assert "QC_ratio: 0.25" in log_text
    finally:
        app.destroy()


def test_main_window_manual_completion_switches_then_accepts_deferred_save(ctk_root, tmp_path) -> None:
    app = _MainWindowHarness(ctk_root, tmp_path)
    app.pack(fill="both", expand=True)
    ctk_root.update_idletasks()
    result_data = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.0/1.0"], "S1": ["case", 123]})
    original_input = str(tmp_path / "input.xlsx")
    deferred_path = tmp_path / "STEP1_input.parquet"
    scheduled: list[tuple[int, int | None]] = []
    app.step_widgets[0].set_input_file(original_input)
    app._schedule_step_output_save = (
        lambda step_index, _data, *, next_step_index=None: scheduled.append((step_index, next_step_index))
    )

    try:
        app._on_step_complete(result_data, metadata={})
        app.update_idletasks()

        assert app._current_step == 1
        assert app._visible_step_index == 1
        assert app.step_widgets[0].input_entry.get() == original_input
        assert app.step_widgets[1]._data is result_data
        assert app.step_widgets[1].input_entry.get() == ""
        assert scheduled == [(0, 1)]

        app._finish_deferred_step_output_save(
            step_index=0,
            next_step_index=1,
            session_token=id(app._pipeline_session),
            path=deferred_path,
            error_message=None,
        )

        assert app._step_output_paths[0] == deferred_path
        assert app.step_widgets[1].input_entry.get() == str(deferred_path)
    finally:
        app.destroy()


def test_content_area_prioritizes_step_panel_height_over_bottom_log(ctk_root) -> None:
    app = _ContentAreaHarness(ctk_root)
    app.pack(fill="both", expand=True)
    ctk_root.update_idletasks()
    try:
        assert app.content_frame.grid_rowconfigure(0)["weight"] == 0
        assert app.content_frame.grid_rowconfigure(1)["weight"] == 1
        assert app.content_frame.grid_rowconfigure(2)["weight"] == 0
        assert app.run_context_frame.grid_info()["row"] == 0
        assert app.main_frame.grid_info()["row"] == 1
        assert app.bottom_frame.grid_info()["row"] == 2
        assert app.main_frame.grid_info()["sticky"] == "nesw"
    finally:
        app.destroy()


def test_bottom_action_buttons_keep_position_when_status_text_changes(ctk_root) -> None:
    app = _ContentAreaHarness(ctk_root)
    app.pack(fill="both", expand=True)
    ctk_root.update_idletasks()
    try:
        initial_x = app.action_button_frame.winfo_rootx()
        initial_width = app.action_button_frame.winfo_width()

        app.status_label.configure(text="Step 1 complete. Step 2 ready.")
        ctk_root.update_idletasks()

        assert app.action_button_frame.winfo_rootx() == initial_x
        assert app.action_button_frame.winfo_width() == initial_width
        assert app.run_step_btn.grid_info()["in"] == app.action_button_frame
        assert app.reset_step_btn.grid_info()["in"] == app.action_button_frame
    finally:
        app.destroy()


def test_bottom_action_status_does_not_inflate_action_row_height(ctk_root) -> None:
    app = _ContentAreaHarness(ctk_root)
    app.pack(fill="both", expand=True)
    ctk_root.update_idletasks()
    try:
        app.status_label.configure(text="Step 1 complete. Step 2 ready.")
        ctk_root.update_idletasks()

        assert app.action_bar_frame.winfo_height() <= 42
        assert app.action_button_frame.winfo_y() <= 4
        assert app.status_frame.winfo_height() <= 40
        assert app.action_button_frame.winfo_height() <= 40
    finally:
        app.destroy()


def test_action_button_theme_restores_hover_after_disabled_state(ctk_root) -> None:
    app = _SidebarHarness(ctk_root)
    app.pack()
    ctk_root.update_idletasks()
    try:
        app._apply_action_button_theme(app.export_dnp_btn, "disabled")
        assert app.export_dnp_btn.cget("hover") is False

        app._apply_action_button_theme(app.export_dnp_btn, "secondary")
        assert app.export_dnp_btn.cget("hover") is True
    finally:
        app.destroy()
