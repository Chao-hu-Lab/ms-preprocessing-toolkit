"""Tests for the compact Run Context / Latest Result GUI summary."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import customtkinter as ctk
import pandas as pd

import ms_preprocessing.gui.path_display as path_display_module
from ms_preprocessing.gui.event_handlers import MainWindowEventHandlersMixin
from ms_preprocessing.gui.layout import MainWindowLayoutMixin
from ms_preprocessing.gui.pipeline_session import PipelineSession
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult


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


class _SummaryHarness(MainWindowEventHandlersMixin, ctk.CTkFrame):
    def __init__(self, master, tmp_path: Path) -> None:
        super().__init__(master)
        self._output_dir = tmp_path / "OUTPUT"
        self._source_file = tmp_path / "input.xlsx"
        self._current_step = 1
        self._completed_steps = {0}
        self._last_completed_step = None
        self._last_run_all = False
        self._last_materialized_export_path = tmp_path / "ALL_input.xlsx"
        self._pipeline_session = PipelineSession(
            output_dir=self._output_dir,
            source_file=self._source_file,
        )
        self._context = self._pipeline_session.context
        self._pipeline_session.record_step_parameters(
            0,
            {"method_file": str(tmp_path / "method.docx")},
        )
        self._pipeline_session.record_step_parameters(
            1,
            {"xic_results_file": str(tmp_path / "xic_results.xlsx")},
        )
        self._step_output_paths = {}
        self.step_widgets = [_Step1Widget()]
        self.run_context_label = ctk.CTkLabel(self, text="")
        self.latest_result_label = ctk.CTkLabel(self, text="")


class _Step1Widget:
    def get_combined_preprocessor_paths(self) -> dict[str, str]:
        return {"combined_tsv": r"C:\data\raw_combined.tsv", "method_file": ""}


def test_run_context_panel_exists(ctk_root) -> None:
    app = _ContentAreaHarness(ctk_root)
    app.pack(fill="both", expand=True)
    ctk_root.update_idletasks()
    try:
        assert hasattr(app, "run_context_frame")
        assert hasattr(app, "run_context_label")
        assert hasattr(app, "latest_result_label")
    finally:
        app.destroy()


def test_show_step_stacks_all_steps_and_raises_target(ctk_root) -> None:
    app = _ContentAreaHarness(ctk_root)
    app.pack(fill="both", expand=True)
    ctk_root.update_idletasks()
    try:
        app._show_step(1)
        ctk_root.update_idletasks()

        assert app.step_widgets[1].winfo_manager() == "grid"
        assert app.step_widgets[0].winfo_manager() == "grid"
        assert app._visible_step_index == 1
    finally:
        app.destroy()


def test_content_area_keeps_summary_main_and_bottom_rows_stable(ctk_root) -> None:
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
    finally:
        app.destroy()


def test_run_context_summary_includes_source_method_istd_and_latest_output(ctk_root, tmp_path) -> None:
    app = _SummaryHarness(ctk_root, tmp_path)
    app.pack()
    ctk_root.update_idletasks()
    try:
        app._update_run_context_summary()
        text = app.run_context_label.cget("text")

        assert "Source: input.xlsx" in text
        assert "Step: 2" in text
        assert "Completed: 1" in text
        assert "Method: method.docx" in text
        assert "XIC: xic_results.xlsx" in text
        assert "Combined TSV: selected" in text
        assert "Latest output: ALL_input.xlsx" in text
        assert "\nFiles:" in text
        assert "\nOutput:" in text
    finally:
        app.destroy()


def test_display_name_shortens_windows_paths_when_running_on_posix(
    ctk_root,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(path_display_module, "PurePath", PurePosixPath)
    app = _SummaryHarness(ctk_root, tmp_path)
    app.pack()
    ctk_root.update_idletasks()
    try:
        assert app._display_name(r"C:\data\method.docx") == "method.docx"
    finally:
        app.destroy()


def test_latest_result_summary_updates_label(ctk_root, tmp_path) -> None:
    app = _SummaryHarness(ctk_root, tmp_path)
    app.pack()
    ctk_root.update_idletasks()
    try:
        app._update_latest_result_summary(["Kept: 80", "Deleted: 20"])

        assert app.latest_result_label.cget("text") == "Latest Result: Kept: 80 | Deleted: 20"
    finally:
        app.destroy()


def test_step_completion_updates_latest_result_summary(ctk_root, tmp_path) -> None:
    class _Widget:
        def get_last_parameters(self) -> dict:
            return {}

        def get_processing_result(self) -> ProcessingResult:
            return ProcessingResult(
                success=True,
                step="feature_filter",
                output_path=None,
                data=pd.DataFrame({"S1": [1]}),
                metadata=ProcessingMetadata(),
                statistics={"kept_features": 1, "deleted_features": 0},
            )

        def get_metadata(self) -> dict:
            return {"statistics": {"kept_features": 1, "deleted_features": 0}}

        def show_stats(self, _stats: dict) -> None:
            return None

        def set_input_file(self, _path: str) -> None:
            return None

    app = _SummaryHarness(ctk_root, tmp_path)
    app.step_widgets = [_Widget()]
    app._current_step = 0
    app._save_step_output = lambda *_args, **_kwargs: None
    app._auto_export_final_results = lambda: None
    app.pack()
    ctk_root.update_idletasks()
    try:
        app._on_step_complete(pd.DataFrame({"S1": [1]}), metadata={})

        assert "Kept: 1" in app.latest_result_label.cget("text")
        assert "Deleted: 0" in app.latest_result_label.cget("text")
    finally:
        app.destroy()
