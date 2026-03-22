"""Focused tests for main-window event handler guardrails."""

from __future__ import annotations

from unittest.mock import Mock

import pandas as pd

from ms_preprocessing.gui.main_window import MainWindow
from ms_preprocessing.gui.pipeline_session import PipelineSession
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult


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
            self._result = result
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
            return data.copy()

        def get_processing_result(self) -> ProcessingResult:
            return self._result

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
    window._pipeline_session = PipelineSession(output_dir=window._output_dir, source_file=window._source_file)
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
                metadata=ProcessingMetadata(),
            )
        ),
        _Widget(
            ProcessingResult(
                success=True,
                step="duplicate_remover",
                output_path=None,
                data=data.copy(),
                metadata=ProcessingMetadata(),
            )
        ),
        _Widget(
            ProcessingResult(
                success=True,
                step="feature_filter",
                output_path=None,
                data=data.copy(),
                metadata=ProcessingMetadata(highlight_rows={8}),
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
