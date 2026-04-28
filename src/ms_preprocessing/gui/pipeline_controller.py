"""GUI pipeline controller boundary."""

from __future__ import annotations

import copy
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from ms_preprocessing.config.settings import Settings
from ms_preprocessing.gui.async_task_runner import AsyncTaskRunner
from ms_preprocessing.gui.step_summary import summarize_step_result
from ms_preprocessing.gui.validation import format_validation_warnings, has_blocking_warnings
from ms_preprocessing.utils.results import ProcessingMetadata
from ms_preprocessing.workflow.workflow_runner import WorkflowRunner, WorkflowRunResult

if TYPE_CHECKING:
    from ms_preprocessing.workflow.combined_tsv_service import CombinedTsvService
    from ms_preprocessing.workflow.export_service import ExportService


class PipelineController:
    """Move Run All, export, and combined TSV orchestration out of event handlers."""

    def __init__(
        self,
        host: Any,
        *,
        export_service: ExportService | None = None,
        combined_tsv_service: CombinedTsvService | None = None,
        async_runner: AsyncTaskRunner | None = None,
    ) -> None:
        self._host = host
        file_handler = host.__dict__.get("_file_handler")
        if export_service is None:
            from ms_preprocessing.workflow.export_service import ExportService

            export_service = ExportService(file_handler=file_handler)
        if combined_tsv_service is None:
            from ms_preprocessing.workflow.combined_tsv_service import CombinedTsvService

            combined_tsv_service = CombinedTsvService(file_handler=file_handler)
        self._export_service = export_service
        self._combined_tsv_service = combined_tsv_service
        self._async_runner = async_runner or AsyncTaskRunner(host)

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
                widget.set_context(host._context)
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
            self.reset_pipeline_for_run_all()
            runner = WorkflowRunner(file_handler=host.__dict__.get("_file_handler"))
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

        step_name_to_index = {spec[0]: index for index, spec in enumerate(Settings.WORKFLOW_STEPS)}
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

    @staticmethod
    def _resolved_parameters(params_by_step: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {
            "step1": dict(params_by_step[0]) if len(params_by_step) > 0 else {},
            "step2": dict(params_by_step[1]) if len(params_by_step) > 1 else {},
            "step3": dict(params_by_step[2]) if len(params_by_step) > 2 else {},
            "step4": dict(params_by_step[3]) if len(params_by_step) > 3 else {},
        }

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

    def export_results(self) -> Path | None:
        host = self._host
        if host._has_active_processing():
            host._log("Busy: wait for processing to finish before exporting results.")
            return None

        if host._current_data is None:
            materialized = self.materialize_final_xlsx_from_latest_step()
            if materialized is None:
                host._log("Error: No data to export")
            return materialized

        try:
            filepath = self._export_service.export_final(
                host._current_data,
                output_path=self._final_export_path(),
                input_path=host._source_file,
                step="all" if host._last_run_all else self._last_step_name(),
                session=self._export_session_view(),
                export_deleted_feature=self._export_deleted_feature(),
            )
            host._last_materialized_export_path = filepath
            host._log(f"Exported to: {filepath}")
            self._log_downstream_handoff_reminder()
            self._update_run_context_summary()
            return filepath
        except Exception as exc:
            host._log(f"Export error: {exc}")
            return None

    def materialize_final_xlsx_from_latest_step(self) -> Path | None:
        host = self._host
        if host._last_completed_step is None:
            return None
        source_path = host._step_output_paths.get(host._last_completed_step)
        if source_path is None:
            return None

        source_path = Path(source_path)
        if source_path.suffix.lower() == ".xlsx":
            host._last_materialized_export_path = source_path
            host._log(f"Final xlsx available: {source_path}")
            self._log_downstream_handoff_reminder()
            return source_path

        target_path = self._final_export_path()
        try:
            data, metadata = host._file_handler.load_data(source_path)
            host._pipeline_session.update_context_from_metadata(metadata)
            host._context = host._pipeline_session.context
            host._current_data = data

            filepath = self._export_service.export_final(
                data,
                output_path=target_path,
                input_path=host._source_file,
                step="all" if host._last_run_all else self._last_step_name(),
                session=self._export_session_view(),
                export_deleted_feature=self._export_deleted_feature(),
            )
            host._step_output_paths[host._last_completed_step] = filepath
            host._last_materialized_export_path = filepath
            host._log(f"Materialized final xlsx from parquet: {filepath}")
            self._log_downstream_handoff_reminder()
            self._update_run_context_summary()
            return filepath
        except Exception as exc:
            host._log(f"Materialization error: {exc}")
            return None

    def schedule_step_output_save(
        self,
        step_index: int,
        data: pd.DataFrame,
        *,
        next_step_index: int | None = None,
    ) -> None:
        host = self._host
        if data is None:
            return
        try:
            self._async_runner.ensure_state()
            session = host._pipeline_session
            session.set_source_file(getattr(host, "_source_file", None))
            output_path = session.build_step_output_path(step_index)
            formatting_context = {
                "highlight_rows": set(session.context.get("highlight_rows") or []),
                "blue_font_cells": list(session.context.get("blue_font_cells") or []),
                "red_font_rows": set(session.context.get("red_font_rows") or []),
            }
            session_token = id(session)
            data_snapshot = data.copy(deep=False)
        except Exception as exc:
            host._log(f"Auto-save error: {exc}")
            return

        worker = threading.Thread(
            target=host._run_step_output_save_worker,
            args=(
                step_index,
                data_snapshot,
                next_step_index,
                session_token,
                output_path,
                formatting_context,
            ),
            daemon=True,
            name=f"step-{step_index + 1}-autosave-worker",
        )
        host._step_output_save_threads.append(worker)
        host._schedule_ui_queue_drain()
        worker.start()

    def run_combined_tsv_preprocessor(self) -> None:
        host = self._host
        if host._has_active_processing():
            host._log("Busy: wait for the current task to finish before creating combined_fix.")
            return

        if not host.__dict__.get("step_widgets"):
            host._show_error("Step 1 widget is not available.")
            return

        widget = host.step_widgets[0]
        path_getter = getattr(widget, "get_combined_preprocessor_paths", None)
        if not callable(path_getter):
            host._show_error("Combined TSV controls are not available.")
            return

        paths = path_getter()
        raw_text = str(paths.get("combined_tsv") or "").strip()
        method_text = str(paths.get("method_file") or "").strip()
        if not raw_text:
            host._show_error("Please select a combined TSV file first.")
            return

        raw_path = Path(raw_text)
        if not raw_path.exists():
            host._show_error(f"Combined TSV file not found:\n{raw_path}")
            return

        loaded_path: Path | None = None
        host._set_pipeline_busy_state(True)
        try:
            host._log(f"Creating combined_fix file from: {raw_path}")
            loaded_path = self._combined_tsv_service.create_combined_fix(
                raw_path=raw_path,
                method_file=Path(method_text) if method_text else None,
                output_dir=host._output_dir,
                progress_callback=host._safe_update_action_bar_progress,
            )
            stats = getattr(self._combined_tsv_service, "last_statistics", {}) or {}
            removed = stats.get("removed_features", "unknown")
            output_features = stats.get(
                "output_features",
                getattr(self._combined_tsv_service, "last_output_features", "unknown"),
            )
            host._log(
                f"Combined TSV preprocessing complete: {output_features} features kept, "
                f"{removed} removed. Output: {loaded_path}"
            )
        except Exception as exc:
            host._show_error(f"Combined TSV preprocessing failed:\n{exc}")
            return
        finally:
            host._set_pipeline_busy_state(False)

        host._load_file_for_step(0, path=loaded_path)
        prefill = getattr(host.step_widgets[0], "prefill_normal_method_from_combined", None)
        if callable(prefill):
            prefill()
        host._last_materialized_export_path = loaded_path
        self._update_run_context_summary()
        host._log("Ready: review Step 1 settings, then run Step 1 or Run All.")

    def _profile_name(self) -> str:
        profile_var = self._host.__dict__.get("run_all_profile_var")
        if profile_var is None:
            return "default"
        try:
            return str(profile_var.get())
        except Exception:
            return "default"

    def _final_export_path(self) -> Path:
        host = self._host
        host._pipeline_session.set_source_file(host._source_file)
        return host._pipeline_session.build_final_export_path(
            last_completed_step=host._last_completed_step,
            last_run_all=host._last_run_all,
            suffix=".xlsx",
        )

    def _last_step_name(self) -> str:
        last_completed = self._host._last_completed_step
        mapping = {
            0: "organize",
            1: "istd",
            2: "duplicate-removal",
            3: "filter",
        }
        return mapping.get(last_completed, "filter")

    def _export_session_view(self) -> Any:
        session = self._host._pipeline_session
        context = self._session_context(session)
        metadata = getattr(session, "metadata", None)
        if not isinstance(metadata, ProcessingMetadata):
            metadata = ProcessingMetadata(
                red_font_rows=set(context.get("red_font_rows") or []),
                protected_rows=set(
                    context.get("protected_rows") or context.get("red_font_rows") or []
                ),
                blue_font_cells=list(context.get("blue_font_cells") or []),
                highlight_rows=set(context.get("highlight_rows") or []),
                sample_info=context.get("sample_info"),
                deleted_feature_df=context.get("deleted_feature_df"),
            )
        return _ExportSessionView(session=session, metadata=metadata)

    def _session_context(self, session: Any) -> dict[str, Any]:
        context = session.__dict__.get("context") if hasattr(session, "__dict__") else None
        if isinstance(context, dict):
            return context
        host_context = self._host.__dict__.get("_context")
        return host_context if isinstance(host_context, dict) else {}

    def _export_deleted_feature(self) -> bool:
        step_widgets = self._host.__dict__.get("step_widgets", [])
        if len(step_widgets) < 4:
            return False
        export_var = getattr(step_widgets[3], "_export_deleted_var", None)
        getter = getattr(export_var, "get", None)
        if not callable(getter):
            return False
        try:
            return bool(getter())
        except Exception:
            return False

    def _log_downstream_handoff_reminder(self) -> None:
        reminder = getattr(self._host, "_log_downstream_handoff_reminder", None)
        if callable(reminder):
            reminder()

    def _update_run_context_summary(self) -> None:
        updater = getattr(self._host, "_update_run_context_summary", None)
        if callable(updater):
            updater()


class _ExportSessionView:
    """Adapter exposing typed export metadata while delegating path behavior."""

    def __init__(self, *, session: Any, metadata: ProcessingMetadata) -> None:
        self._session = session
        self.metadata = metadata
        preserved = session.__dict__.get("preserved_sheets") if hasattr(session, "__dict__") else None
        self.preserved_sheets = preserved if isinstance(preserved, dict) else {}

    def set_source_file(self, source_file: Path | None) -> None:
        self._session.set_source_file(source_file)

    def build_final_export_path(
        self,
        last_completed_step: int | None,
        last_run_all: bool,
        suffix: str = ".xlsx",
    ) -> Path:
        return self._session.build_final_export_path(
            last_completed_step=last_completed_step,
            last_run_all=last_run_all,
            suffix=suffix,
        )
