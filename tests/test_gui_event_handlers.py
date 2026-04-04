"""Focused tests for main-window event handler guardrails."""

from __future__ import annotations

import threading
import time
from unittest.mock import Mock

import customtkinter as ctk
import pandas as pd

from ms_preprocessing.config.pipeline_profiles import get_pipeline_profile
from ms_preprocessing.gui.event_handlers import MainWindowEventHandlersMixin
from ms_preprocessing.gui.main_window import MainWindow
from ms_preprocessing.gui.pipeline_session import PipelineSession
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult


from tests.conftest import spin_until


def test_run_all_steps_checks_pipeline_prerequisites_before_processing() -> None:
    window = MainWindow.__new__(MainWindow)
    data = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.0/1.0"], "S1": ["case", 123]})
    widget = Mock()
    widget.get_parameters.return_value = {}

    window._current_data = data
    window._original_data = data.copy()
    window._current_step = 0
    window._context = {}
    window._completed_steps = set()
    window._last_completed_step = None
    window._last_run_all = False
    window._step_output_paths = {}
    window.step_widgets = [widget]
    window._pipeline_session = Mock()
    window._pipeline_session.can_run_step.return_value = False
    window._pipeline_session.record_step_parameters.return_value = None

    logs: list[str] = []
    switch_calls: list[int] = []
    window._log = logs.append
    window._save_step_output = lambda *_args, **_kwargs: None
    window._update_export_dnp_btn = lambda: None
    window.update_idletasks = lambda: None
    window._switch_step = switch_calls.append

    window._run_all_steps()

    assert any("prerequisites are complete" in message for message in logs)
    assert widget.run_processing.called is False
    assert switch_calls == [0]


def test_run_all_steps_rebuilds_clean_pipeline_session_from_loaded_source(tmp_path) -> None:
    class _Widget:
        def __init__(self, result: ProcessingResult) -> None:
            self._template_result = result
            self._processing_result = result
            self.contexts: list[dict[str, object]] = []

        def set_data(self, data: pd.DataFrame) -> None:
            self._data = data.copy()

        def set_context(self, context: dict[str, object]) -> None:
            self.contexts.append(
                {
                    "red_font_rows": set(context.get("red_font_rows") or []),
                    "highlight_rows": set(context.get("highlight_rows") or []),
                }
            )

        def set_input_file(self, path: str) -> None:
            _ = path

        def get_parameters(self) -> dict:
            return {}

        def run_processing(self, data: pd.DataFrame, **params) -> pd.DataFrame:
            _ = params
            self._processing_result = self._template_result
            return data.copy()

        def get_processing_result(self) -> ProcessingResult:
            return self._processing_result

    data = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.0/1.0"], "S1": ["case", 123]})
    window = MainWindow.__new__(MainWindow)
    window._output_dir = tmp_path / "OUTPUT"
    window._source_file = tmp_path / "input.xlsx"
    window._current_data = data
    window._original_data = data.copy()
    window._current_step = 0
    window._last_completed_step = 2
    window._last_run_all = False
    window._last_materialized_export_path = None
    window._completed_steps = {0, 1, 2}
    window._pipeline_session = PipelineSession(
        output_dir=window._output_dir, source_file=window._source_file
    )
    window._pipeline_session.update_context_from_metadata(
        {"red_font_rows": [99], "protected_rows": [99], "highlight_rows": [77]}
    )
    window._step_output_paths = {0: tmp_path / "stale.parquet"}
    window._context = window._pipeline_session.context
    window._source_context_snapshot = {
        "red_font_rows": set(),
        "protected_rows": set(),
        "blue_font_cells": [],
        "highlight_rows": set(),
    }
    window._log = lambda *_args, **_kwargs: None
    window._save_step_output = lambda *_args, **_kwargs: None
    window._update_export_dnp_btn = lambda: None
    window.update_idletasks = lambda: None
    window._switch_step = lambda *_args, **_kwargs: None

    window.step_widgets = [
        _Widget(
            ProcessingResult(
                success=True,
                step="data_organizer",
                output_path=None,
                data=data.copy(),
                metadata=ProcessingMetadata(red_font_rows={7}, protected_rows={7}),
            )
        ),
        _Widget(
            ProcessingResult(
                success=True,
                step="istd_marker",
                output_path=None,
                data=data.copy(),
                metadata=ProcessingMetadata(red_font_rows={7}, protected_rows={7}),
            )
        ),
        _Widget(
            ProcessingResult(
                success=True,
                step="duplicate_remover",
                output_path=None,
                data=data.copy(),
                metadata=ProcessingMetadata(red_font_rows={7}, protected_rows={7}),
            )
        ),
        _Widget(
            ProcessingResult(
                success=True,
                step="feature_filter",
                output_path=None,
                data=data.copy(),
                metadata=ProcessingMetadata(
                    red_font_rows={7},
                    protected_rows={7},
                    highlight_rows={8},
                ),
            )
        ),
    ]

    window._run_all_steps()

    assert window._pipeline_session.metadata.red_font_rows == {7}
    assert window._pipeline_session.metadata.highlight_rows == {8}
    assert 99 not in window._pipeline_session.metadata.red_font_rows
    assert 77 not in window._pipeline_session.metadata.highlight_rows
    assert window.step_widgets[0].contexts[0]["red_font_rows"] == set()
    assert window.step_widgets[0].contexts[0]["highlight_rows"] == set()


def test_switch_step_is_blocked_while_processing_is_active() -> None:
    window = MainWindow.__new__(MainWindow)
    busy_widget = Mock()
    busy_widget._is_processing = True
    idle_widget = Mock()
    idle_widget._is_processing = False

    logs: list[str] = []
    window.step_widgets = [busy_widget, idle_widget]
    window._current_step = 0
    window._context = {}
    window._completed_steps = set()
    window._step_output_paths = {}
    window._log = logs.append
    window._show_step = Mock()
    window.step_buttons = []
    window._step_status_labels = []

    window._switch_step(1)

    assert window._current_step == 0
    assert window._show_step.called is False
    assert any("cannot switch steps while processing" in message for message in logs)


def test_step_4_completion_auto_exports_final_results(tmp_path) -> None:
    window = MainWindow.__new__(MainWindow)
    data = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.0/1.0"], "S1": ["case", 123]})
    current_widget = Mock()
    current_widget.get_last_parameters.return_value = {}
    current_widget.get_processing_result.return_value = Mock()
    current_widget.get_metadata.return_value = {"statistics": {}}

    window.step_widgets = [Mock(), Mock(), Mock(), current_widget]
    window._current_step = 3
    window._context = {}
    window._completed_steps = set()
    window._last_completed_step = None
    window._last_run_all = False
    window._step_output_paths = {}
    window._pipeline_session = Mock()
    window._pipeline_session.context = {}
    window._update_export_dnp_btn = lambda: None
    window._save_step_output = lambda *_args, **_kwargs: tmp_path / "STEP4_input.parquet"
    window._export_results = Mock(return_value=tmp_path / "ALL_input.xlsx")

    logs: list[str] = []
    window._log = logs.append

    window._on_step_complete(data, metadata={})

    window._export_results.assert_called_once_with()
    assert any("Auto-exporting results" in message for message in logs)


def test_pipeline_profile_selection_applies_step_parameters_to_all_widgets() -> None:
    window = MainWindow.__new__(MainWindow)
    window.step_widgets = [Mock(), Mock(), Mock(), Mock()]
    window.run_all_profile_var = Mock()
    logs: list[str] = []
    window._log = logs.append

    window._on_pipeline_profile_selected("strict")

    profile = get_pipeline_profile("strict")
    window.step_widgets[0].apply_parameters.assert_called_once_with(profile["step1"])
    window.step_widgets[1].apply_parameters.assert_called_once_with(profile["step2"])
    window.step_widgets[2].apply_parameters.assert_called_once_with(profile["step3"])
    window.step_widgets[3].apply_parameters.assert_called_once_with(profile["step4"])
    window.run_all_profile_var.set.assert_called_once_with("strict")
    assert any("Applied Run All preset: strict" in message for message in logs)


class _RunAllAsyncHarness(MainWindowEventHandlersMixin, ctk.CTkFrame):
    def __init__(self, master, tmp_path, widget, data: pd.DataFrame) -> None:
        super().__init__(master)
        self._output_dir = tmp_path / "OUTPUT"
        self._source_file = tmp_path / "input.xlsx"
        self._current_data = data.copy()
        self._original_data = data.copy()
        self._current_step = 0
        self._last_completed_step = None
        self._last_run_all = False
        self._last_materialized_export_path = None
        self._completed_steps = set()
        self._pipeline_session = PipelineSession(
            output_dir=self._output_dir, source_file=self._source_file
        )
        self._step_output_paths = {}
        self._context = self._pipeline_session.context
        self._source_context_snapshot = None
        self.step_widgets = [widget]
        self.step_buttons = []
        self._step_status_labels = []
        self._log_messages: list[str] = []

    def _log(self, message: str) -> None:
        self._log_messages.append(message)

    def _switch_step(self, step_index: int) -> None:
        self._current_step = step_index

    def _update_export_dnp_btn(self) -> None:
        return None

    def _update_action_bar_progress(self, value: float, status: str = "") -> None:
        _ = (value, status)

    def _save_step_output(self, step_index: int, data: pd.DataFrame):
        _ = (step_index, data)
        return None


def test_run_all_steps_runs_in_background_when_ui_scheduler_available(ctk_root, tmp_path) -> None:
    release_worker = threading.Event()
    worker_started = threading.Event()
    input_df = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.0/1.0"], "S1": ["case", 123]})

    class _Widget:
        def __init__(self) -> None:
            self._processing_result = ProcessingResult(
                success=True,
                step="data_organizer",
                output_path=None,
                data=input_df.copy(),
                metadata=ProcessingMetadata(),
            )

        def get_parameters(self) -> dict:
            return {}

        def set_context(self, context: dict[str, object]) -> None:
            self._context = dict(context)

        def run_processing(self, data: pd.DataFrame, **params) -> pd.DataFrame:
            _ = params
            worker_started.set()
            release_worker.wait(timeout=1.0)
            self._processing_result = ProcessingResult(
                success=True,
                step="data_organizer",
                output_path=None,
                data=data.copy(),
                metadata=ProcessingMetadata(),
            )
            return data.copy()

        def get_processing_result(self) -> ProcessingResult:
            return self._processing_result

        def get_metadata(self) -> dict:
            return {}

    app = _RunAllAsyncHarness(ctk_root, tmp_path, _Widget(), input_df)
    app.pack()
    ctk_root.update_idletasks()
    try:
        started_at = time.monotonic()
        app._run_all_steps()
        elapsed = time.monotonic() - started_at

        assert elapsed < 0.1
        assert worker_started.wait(timeout=0.2)
        assert app._pipeline_is_processing is True

        release_worker.set()

        assert spin_until(ctk_root, lambda: not app._pipeline_is_processing)
        assert app._last_run_all is True
        assert app._last_completed_step == 0
    finally:
        app.destroy()


def test_run_all_auto_exports_final_results_when_pipeline_completes(ctk_root, tmp_path) -> None:
    release_worker = threading.Event()
    worker_started = threading.Event()
    input_df = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.0/1.0"], "S1": ["case", 123]})

    class _Widget:
        def __init__(self) -> None:
            self._processing_result = ProcessingResult(
                success=True,
                step="data_organizer",
                output_path=None,
                data=input_df.copy(),
                metadata=ProcessingMetadata(),
            )

        def get_parameters(self) -> dict:
            return {}

        def set_context(self, context: dict[str, object]) -> None:
            self._context = dict(context)

        def run_processing(self, data: pd.DataFrame, **params) -> pd.DataFrame:
            _ = params
            worker_started.set()
            release_worker.wait(timeout=1.0)
            self._processing_result = ProcessingResult(
                success=True,
                step="data_organizer",
                output_path=None,
                data=data.copy(),
                metadata=ProcessingMetadata(),
            )
            return data.copy()

        def get_processing_result(self) -> ProcessingResult:
            return self._processing_result

        def get_metadata(self) -> dict:
            return {}

    app = _RunAllAsyncHarness(ctk_root, tmp_path, _Widget(), input_df)
    app._export_results = Mock(return_value=tmp_path / "ALL_input.xlsx")
    app.pack()
    ctk_root.update_idletasks()
    try:
        app._run_all_steps()
        assert worker_started.wait(timeout=0.2)

        release_worker.set()

        assert spin_until(ctk_root, lambda: not app._pipeline_is_processing)
        app._export_results.assert_called_once_with()
        assert any("Auto-exporting results" in message for message in app._log_messages)
    finally:
        app.destroy()
