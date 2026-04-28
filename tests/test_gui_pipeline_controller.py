"""Tests for GUI pipeline boundary controller."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pandas as pd

from ms_preprocessing.gui.pipeline_controller import PipelineController
from ms_preprocessing.gui.pipeline_session import PipelineSession
from ms_preprocessing.gui.validation import ValidationWarning
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult


def _frame(label: str = "input") -> pd.DataFrame:
    return pd.DataFrame({"stage": [label], "value": [1]})


class _Host:
    def __init__(self, tmp_path: Path) -> None:
        self._output_dir = tmp_path / "OUTPUT"
        self._source_file = tmp_path / "input.xlsx"
        self._current_data = _frame()
        self._original_data = _frame()
        self._current_step = 0
        self._completed_steps: set[int] = {1, 2}
        self._last_completed_step = 2
        self._last_run_all = True
        self._last_materialized_export_path = tmp_path / "stale.xlsx"
        self._pipeline_session = PipelineSession(self._output_dir, self._source_file)
        self._step_output_paths: dict[int, Path] = {2: tmp_path / "stale.parquet"}
        self._context = self._pipeline_session.context
        self._source_context_snapshot = {"red_font_rows": set(), "protected_rows": set()}
        self.step_widgets: list[object] = []
        self.logs: list[str] = []
        self.progress: list[tuple[float, str]] = []
        self.latest_summaries: list[list[str]] = []
        self.run_context_updates = 0
        self.switch_calls: list[int] = []
        self.busy_states: list[bool] = []
        self.exported = False
        self.show_errors: list[str] = []
        self.run_all_profile_var = Mock()
        self.run_all_profile_var.get.return_value = "default"

    def _new_pipeline_session(self, source_file: Path | None) -> PipelineSession:
        return PipelineSession(self._output_dir, source_file)

    def _attach_pipeline_session(self, session: PipelineSession) -> None:
        self._pipeline_session = session
        self._step_output_paths = session.step_output_paths
        self._context = session.context

    def _has_active_processing(self) -> bool:
        return False

    def _log(self, message: str) -> None:
        self.logs.append(message)

    def _log_pipeline_profile_preview(self, profile_name: str) -> None:
        self.logs.append(f"preview:{profile_name}")

    def _set_pipeline_busy_state(self, processing: bool) -> None:
        self.busy_states.append(processing)

    def _safe_update_action_bar_progress(self, value: float, status: str = "") -> None:
        self.progress.append((value, status))

    def _show_error(self, message: str) -> None:
        self.show_errors.append(message)

    def _confirm_validation_warnings(self, warnings: list[ValidationWarning]) -> bool:
        _ = warnings
        return True

    def _collect_run_all_validation_warnings(
        self,
        params_by_step: list[dict],
    ) -> list[ValidationWarning]:
        _ = params_by_step
        return []

    def _can_schedule_ui_callbacks(self) -> bool:
        return False

    def _dispatch_to_ui(self, callback, *args) -> None:
        callback(*args)

    def _reset_pipeline_for_run_all(self) -> None:
        PipelineController(self).reset_pipeline_for_run_all()

    def _save_step_output(self, step_index: int, data: pd.DataFrame) -> Path:
        path = self._output_dir / f"STEP{step_index + 1}.parquet"
        self._pipeline_session.step_output_paths[step_index] = path
        return path

    def _summarize_widget_result(self, step_index: int, widget, params: dict | None = None) -> list[str]:
        _ = (widget, params)
        return [f"summary {step_index + 1}"]

    def _update_latest_result_summary(self, lines: list[str]) -> None:
        self.latest_summaries.append(lines)

    def _update_run_context_summary(self) -> None:
        self.run_context_updates += 1

    def _auto_export_final_results(self):
        self.exported = True
        return self._output_dir / "ALL_input.xlsx"

    def _switch_step(self, step_index: int) -> None:
        self.switch_calls.append(step_index)


class _Widget:
    def __init__(self, step: str, output_label: str) -> None:
        self.step = step
        self.output_label = output_label
        self._processing_result: ProcessingResult | None = None

    def get_parameters(self) -> dict:
        return {"param": self.step}

    def set_context(self, context: dict) -> None:
        self.context = dict(context)

    def run_processing(self, data: pd.DataFrame, **params) -> pd.DataFrame:
        _ = params
        output = _frame(self.output_label)
        self._processing_result = ProcessingResult(
            success=True,
            step=self.step,
            output_path=None,
            data=output,
            metadata=ProcessingMetadata(red_font_rows={len(self.output_label)}),
        )
        return output

    def get_processing_result(self) -> ProcessingResult | None:
        return self._processing_result

    def get_metadata(self) -> dict:
        return {}


def test_run_all_prepares_clean_session_from_loaded_source(tmp_path) -> None:
    host = _Host(tmp_path)
    host._pipeline_session.update_context_from_metadata({"red_font_rows": [99], "protected_rows": [99]})
    host.step_widgets = [_Widget("data_organizer", "step1")]

    PipelineController(host).run_all_steps_worker(0, host._original_data.copy(), [{"param": "value"}])

    assert host._completed_steps == {0}
    assert host._last_materialized_export_path is None
    assert 99 not in host._pipeline_session.metadata.red_font_rows
    assert host._step_output_paths[0].name == "STEP1.parquet"


def test_validation_warnings_block_before_processing(tmp_path) -> None:
    host = _Host(tmp_path)
    widget = Mock()
    widget.get_parameters.return_value = {"high_det_thresh": 0.3}
    host.step_widgets = [widget]
    host._collect_run_all_validation_warnings = Mock(
        return_value=[ValidationWarning("bad", "Bad parameters", True)]
    )

    PipelineController(host).run_all_steps()

    widget.run_processing.assert_not_called()
    assert host.show_errors
    assert host.busy_states == []


def test_run_all_success_updates_state_paths_and_summaries(tmp_path) -> None:
    host = _Host(tmp_path)
    host.step_widgets = [
        _Widget("data_organizer", "step1"),
        _Widget("istd_marker", "step2"),
    ]

    PipelineController(host).run_all_steps()

    assert host._current_data["stage"].iloc[0] == "step2"
    assert host._completed_steps == {0, 1}
    assert host._last_completed_step == 1
    assert host._last_run_all is True
    assert sorted(host._step_output_paths) == [0, 1]
    assert host.latest_summaries[-1] == ["summary 2"]
    assert host.exported is True


def test_run_all_uses_workflow_runner_for_real_gui_widget_set(monkeypatch, tmp_path) -> None:
    host = _Host(tmp_path)

    class _RealWidget:
        __module__ = "ms_preprocessing.gui.widgets.fake_widget"

        def get_parameters(self) -> dict:
            return {"param": "value"}

    host.step_widgets = [_RealWidget(), _RealWidget(), _RealWidget(), _RealWidget()]
    captured: dict[str, object] = {}

    class _FakeWorkflowRunner:
        def __init__(self, *, file_handler=None) -> None:
            captured["file_handler"] = file_handler

        def run(self, data, **kwargs):
            captured["data"] = data
            captured.update(kwargs)
            session = kwargs["session"]
            session.step_output_paths[0] = tmp_path / "STEP1_input.parquet"
            return __import__(
                "ms_preprocessing.workflow.workflow_runner",
                fromlist=["WorkflowRunResult"],
            ).WorkflowRunResult(
                success=True,
                data=_frame("runner"),
                step="all",
                completed_steps=["data_organizer"],
                last_completed_step_index=0,
                step_results={
                    "data_organizer": ProcessingResult(
                        success=True,
                        step="data_organizer",
                        output_path=None,
                        data=_frame("runner"),
                        metadata=ProcessingMetadata(red_font_rows={3}),
                        statistics={"features": 1},
                    )
                },
                session=session,
                step_output_paths=dict(session.step_output_paths),
                validation_warnings=[],
                errors=[],
                message="Done",
                final_export_ready=True,
            )

    import ms_preprocessing.gui.pipeline_controller as controller_module

    monkeypatch.setattr(controller_module, "WorkflowRunner", _FakeWorkflowRunner)

    PipelineController(host).run_all_steps_worker(0, host._original_data.copy(), [{"a": 1}] * 4)

    assert captured["step"] == "all"
    assert captured["persist_intermediate"] is True
    assert captured["resolved_parameters"]["step1"] == {"a": 1}
    assert host._current_data["stage"].iloc[0] == "runner"
    assert host._completed_steps == {0}
    assert host._last_completed_step == 0
    assert host._step_output_paths[0].name == "STEP1_input.parquet"
    assert host.latest_summaries[-1][0] == "Features: 1"


def test_run_all_failure_reports_error_and_clears_busy_state(tmp_path) -> None:
    host = _Host(tmp_path)
    widget = _Widget("data_organizer", "step1")
    widget.run_processing = Mock(side_effect=RuntimeError("boom"))
    host.step_widgets = [widget]

    PipelineController(host).run_all_steps()

    assert any("Pipeline error: boom" in message for message in host.logs)
    assert host._last_run_all is False
    assert host.progress[-1] == (0, "Run All failed")
    assert host.busy_states[-1] is False


def test_final_export_delegates_to_export_service(tmp_path) -> None:
    host = _Host(tmp_path)
    host._last_completed_step = 3
    host.step_widgets = [Mock(), Mock(), Mock(), Mock()]
    host.step_widgets[3]._export_deleted_var.get.return_value = True
    export_service = Mock()
    export_service.export_final.return_value = tmp_path / "ALL_input.xlsx"

    out = PipelineController(host, export_service=export_service).export_results()

    assert out == tmp_path / "ALL_input.xlsx"
    export_service.export_final.assert_called_once()
    assert host._last_materialized_export_path == out
