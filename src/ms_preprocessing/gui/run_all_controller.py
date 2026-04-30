"""Run All orchestration for the GUI pipeline."""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any, Protocol

import pandas as pd

from ms_preprocessing.config.settings import Settings
from ms_preprocessing.gui.async_task_runner import AsyncTaskRunner
from ms_preprocessing.gui.step_summary import summarize_step_result
from ms_preprocessing.gui.validation import format_validation_warnings, has_blocking_warnings
from ms_preprocessing.utils.file_handler import FileHandler
from ms_preprocessing.workflow.parameter_resolver import ParameterResolver
from ms_preprocessing.workflow.pipeline_session import PipelineSession
from ms_preprocessing.workflow.workflow_runner import WorkflowRunResult


class WorkflowRunnerLike(Protocol):
    def run(
        self,
        data: pd.DataFrame,
        *,
        step: str,
        resolved_parameters: dict[str, dict],
        session: PipelineSession,
        persist_intermediate: bool = False,
        progress_callback: Callable[[int, str], None] | None = None,
        log_callback: Callable[[str], None] | None = None,
    ) -> WorkflowRunResult: ...


class WorkflowRunnerFactory(Protocol):
    def __call__(self, *, file_handler: FileHandler | None = None) -> WorkflowRunnerLike: ...


class RunAllController:
    """Coordinate full-pipeline execution while keeping the host as UI facade."""

    def __init__(
        self,
        host: Any,
        *,
        async_runner: AsyncTaskRunner | None = None,
        workflow_runner_cls: WorkflowRunnerFactory,
    ) -> None:
        self._host = host
        self._async_runner = async_runner or AsyncTaskRunner(host)
        self._workflow_runner_cls = workflow_runner_cls

    def reset_pipeline_for_run_all(self) -> None:
        host = self._host
        host._completed_steps = set()
        host._last_completed_step = None
        host._last_run_all = False
        host._last_materialized_export_path = None

        source_snapshot = copy.deepcopy(host.__dict__.get("_source_context_snapshot"))
        if source_snapshot is None:
            if "_step_output_paths" in host.__dict__:
                host._step_output_paths.clear()
            return

        session = host._new_pipeline_session(host._source_file)
        host._attach_pipeline_session(session)
        session.update_context_from_metadata(source_snapshot)
        host._context = session.context

    def run_all_steps(self) -> None:
        host = self._host
        if host._has_active_processing():
            host._log("Busy: wait for the current step to finish before running the full pipeline.")
            return

        if host._current_data is None or host._original_data is None:
            host._log("Error: Please load a file first")
            return

        original_step = host._current_step
        try:
            data = host._original_data.copy()
            params_by_step = [dict(widget.get_parameters()) for widget in host.step_widgets]
        except Exception as exc:
            host._log(f"Error preparing Run All: {exc}")
            return

        profile_name = self._profile_name()
        host._log(f"Run All preset: {profile_name}")
        host._log_pipeline_profile_preview(profile_name)

        validation_warnings = host._collect_run_all_validation_warnings(params_by_step)
        if validation_warnings:
            validation_message = format_validation_warnings(validation_warnings)
            if has_blocking_warnings(validation_warnings):
                host._log(f"Validation blocked Run All:\n{validation_message}")
                host._show_error(validation_message)
                return
            host._log(f"Validation warning before Run All:\n{validation_message}")
            if not host._confirm_validation_warnings(validation_warnings):
                host._log("Run All cancelled after validation warning.")
                return

        host._safe_update_action_bar_progress(0, "Running all steps...")
        started = self._async_runner.start_task(
            lambda: self.run_all_steps_worker(original_step, data, params_by_step),
            name="run-all-worker",
        )
        if not started:
            host._log("Busy: wait for the current step to finish before running the full pipeline.")

    def run_all_steps_worker(
        self,
        original_step: int,
        data: pd.DataFrame,
        params_by_step: list[dict[str, Any]],
    ) -> None:
        if self._can_use_workflow_runner(params_by_step):
            self._run_all_steps_with_workflow_runner(original_step, data, params_by_step)
            return

        self._run_all_steps_with_widgets(original_step, data, params_by_step)

    def finish_run_all_steps(self, original_step: int, success: bool) -> None:
        host = self._host
        host._pipeline_worker_thread = None
        host._set_pipeline_busy_state(False)
        if not success:
            host._safe_update_action_bar_progress(0, "Run All failed")
        else:
            host._auto_export_final_results()
            host._update_run_context_summary()
        host._switch_step(min(original_step, len(host.step_widgets) - 1))

    def _run_all_steps_with_widgets(
        self,
        original_step: int,
        data: pd.DataFrame,
        params_by_step: list[dict[str, Any]],
    ) -> None:
        host = self._host
        success = False
        try:
            self.reset_pipeline_for_run_all()

            for index, widget in enumerate(host.step_widgets):
                step_name = Settings.WORKFLOW_STEPS[index][0]
                if not host._pipeline_session.can_run_step(step_name):
                    raise RuntimeError(
                        f"Cannot run Step {index + 1} ({step_name}) before its prerequisites are complete."
                    )

                host._current_step = index
                host._dispatch_to_ui(
                    host._safe_update_action_bar_progress,
                    0,
                    f"Running Step {index + 1}/{len(host.step_widgets)}...",
                )
                host._log(f"Running Step {index + 1}...")

                params = dict(params_by_step[index])
                widget._data = data
                widget._last_parameters = dict(params)
                widget._last_metadata = {}
                widget._processing_result = None
                widget._result = None
                self._set_widget_session_metadata(widget)
                data = widget.run_processing(data, **params)
                widget._result = data

                host._pipeline_session.record_step_parameters(index, params)
                processing_result = widget.get_processing_result()
                if processing_result is not None:
                    host._pipeline_session.update_from_result(processing_result)
                else:
                    host._update_context_from_metadata(widget.get_metadata())
                host._context = host._pipeline_session.context
                host._completed_steps.add(index)

                host._current_data = data
                host._last_completed_step = index
                output_path = host._save_step_output(index, data)
                if output_path:
                    host._step_output_paths[index] = output_path
                host._log(f"Step {index + 1} completed")
                summary_lines = host._summarize_widget_result(index, widget, params)
                for line in summary_lines:
                    host._log(f"Step {index + 1} summary: {line}")
                host._dispatch_to_ui(host._update_latest_result_summary, summary_lines)
                host._dispatch_to_ui(host._update_run_context_summary)

            host._last_run_all = True
            host._dispatch_to_ui(host._safe_update_action_bar_progress, 100, "All steps complete!")
            host._log("All steps completed successfully!")
            success = True
        except Exception as exc:
            host._last_run_all = False
            host._dispatch_to_ui(host._safe_update_action_bar_progress, 0, f"Pipeline error: {exc}")
            host._log(f"Pipeline error: {exc}")
        finally:
            host._dispatch_to_ui(self.finish_run_all_steps, original_step, success)

    def _run_all_steps_with_workflow_runner(
        self,
        original_step: int,
        data: pd.DataFrame,
        params_by_step: list[dict[str, Any]],
    ) -> None:
        host = self._host
        success = False
        try:
            self._raise_if_raw_combined_tsv_input(data)
            self.reset_pipeline_for_run_all()
            runner = self._workflow_runner_cls(file_handler=host.__dict__.get("_file_handler"))
            result = runner.run(
                data,
                step="all",
                resolved_parameters=self._resolved_parameters(params_by_step),
                session=host._pipeline_session,
                persist_intermediate=True,
                progress_callback=lambda step_index, message: host._dispatch_to_ui(
                    host._safe_update_action_bar_progress,
                    0,
                    f"Running Step {step_index + 1}/{len(host.step_widgets)}: {message}",
                ),
                log_callback=host._log,
            )
            if not result.success or result.data is None:
                raise RuntimeError(result.message or "Run All failed")

            self._apply_workflow_result(result, params_by_step)
            host._dispatch_to_ui(host._safe_update_action_bar_progress, 100, "All steps complete!")
            host._log("All steps completed successfully!")
            success = True
        except Exception as exc:
            host._last_run_all = False
            host._dispatch_to_ui(host._safe_update_action_bar_progress, 0, f"Pipeline error: {exc}")
            host._log(f"Pipeline error: {exc}")
        finally:
            host._dispatch_to_ui(self.finish_run_all_steps, original_step, success)

    def _apply_workflow_result(
        self,
        result: WorkflowRunResult,
        params_by_step: list[dict[str, Any]],
    ) -> None:
        host = self._host
        host._current_data = result.data
        host._last_completed_step = result.last_completed_step_index
        host._last_run_all = result.last_completed_step_index == len(Settings.WORKFLOW_STEPS) - 1
        host._step_output_paths.clear()
        host._step_output_paths.update(result.step_output_paths)
        host._context = result.session.context
        if result.last_completed_step_index is None:
            host._completed_steps = set()
        else:
            host._completed_steps = set(range(result.last_completed_step_index + 1))

        step_name_to_index = self._step_name_to_index()
        adapter_to_gui_step = {
            "data_organizer": "data_organizer",
            "istd_marker": "istd_marker",
            "duplicate_remover": "duplicate_remover",
            "feature_filter": "feature_filter",
        }
        for adapter_step, step_result in result.step_results.items():
            step_index = step_name_to_index.get(adapter_to_gui_step.get(adapter_step, ""))
            if step_index is None:
                continue
            host._log(f"Step {step_index + 1} completed")
            summary_lines = summarize_step_result(
                adapter_step,
                step_result.statistics,
                step_result.metadata.as_context_dict(),
                params_by_step[step_index] if step_index < len(params_by_step) else {},
            )
            for line in summary_lines:
                host._log(f"Step {step_index + 1} summary: {line}")
            host._dispatch_to_ui(host._update_latest_result_summary, summary_lines)
            host._dispatch_to_ui(host._update_run_context_summary)

        self._sync_widgets_from_workflow_result(result, params_by_step)

    def _sync_widgets_from_workflow_result(
        self,
        result: WorkflowRunResult,
        params_by_step: list[dict[str, Any]],
    ) -> None:
        host = self._host
        current_input = host._original_data.copy() if host._original_data is not None else result.data
        step_name_to_index = self._step_name_to_index()
        last_synced_index: int | None = None
        for adapter_step, step_result in result.step_results.items():
            step_index = step_name_to_index.get(adapter_step)
            if step_index is None or step_index >= len(host.step_widgets):
                continue
            widget = host.step_widgets[step_index]
            widget._data = current_input.copy(deep=False) if isinstance(current_input, pd.DataFrame) else current_input
            widget._last_parameters = (
                dict(params_by_step[step_index]) if step_index < len(params_by_step) else {}
            )
            widget._processing_result = step_result
            widget._last_metadata = {
                **step_result.metadata.as_context_dict(),
                "statistics": dict(step_result.statistics or {}),
            }
            output_data = step_result.data if step_result.data is not None else current_input
            widget._result = output_data
            self._set_widget_session_metadata(widget)
            current_input = output_data
            last_synced_index = step_index

        if (
            last_synced_index is not None
            and last_synced_index + 1 < len(host.step_widgets)
            and isinstance(current_input, pd.DataFrame)
        ):
            next_widget = host.step_widgets[last_synced_index + 1]
            next_widget._data = current_input.copy(deep=False)
            self._set_widget_session_metadata(next_widget)

    def _raise_if_raw_combined_tsv_input(self, data: pd.DataFrame) -> None:
        widgets = self._host.__dict__.get("step_widgets", [])
        if not widgets:
            return
        detector = getattr(widgets[0], "_looks_like_raw_combined_tsv", None)
        if callable(detector) and detector(data):
            raise RuntimeError(
                "偵測到 raw combined TSV。請先在「Combined TSV 前處理」選擇 TSV 與方法檔，"
                "按「產生 combined_fix」，再用產出的 .xlsx 跑一般 Toolkit 流程。"
            )

    @staticmethod
    def _resolved_parameters(params_by_step: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return ParameterResolver.from_gui_step_params(params_by_step)

    @staticmethod
    def _step_name_to_index() -> dict[str, int]:
        return {spec[0]: index for index, spec in enumerate(Settings.WORKFLOW_STEPS)}

    def _can_use_workflow_runner(self, params_by_step: list[dict[str, Any]]) -> bool:
        if len(params_by_step) != len(Settings.WORKFLOW_STEPS):
            return False
        widgets = self._host.__dict__.get("step_widgets", [])
        if len(widgets) != len(Settings.WORKFLOW_STEPS):
            return False
        return all(
            widget.__class__.__module__.startswith("ms_preprocessing.gui.widgets")
            for widget in widgets
        )

    def _profile_name(self) -> str:
        profile_var = self._host.__dict__.get("run_all_profile_var")
        if profile_var is None:
            return "default"
        try:
            return str(profile_var.get())
        except Exception:
            return "default"

    def _set_widget_session_metadata(self, widget: Any) -> None:
        metadata_setter = getattr(widget, "set_metadata", None)
        if callable(metadata_setter):
            metadata_setter(self._host._pipeline_session.metadata)
            return

        context_setter = getattr(widget, "set_context", None)
        if callable(context_setter):
            context_setter(self._host._pipeline_session.metadata.as_context_dict())
