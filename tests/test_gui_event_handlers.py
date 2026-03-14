"""Focused tests for main-window event handler guardrails."""

from __future__ import annotations

from unittest.mock import Mock

import pandas as pd

from ms_preprocessing.gui.main_window import MainWindow


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
