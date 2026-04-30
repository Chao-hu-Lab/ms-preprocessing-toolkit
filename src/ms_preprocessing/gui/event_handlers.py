"""Workflow and export handlers for the main preprocessing window."""

from __future__ import annotations

import copy
import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Any, Protocol

import pandas as pd

from ms_preprocessing.config import format_pipeline_profile_preview, get_pipeline_profile
from ms_preprocessing.config.settings import Settings
from ms_preprocessing.gui.async_task_runner import AsyncTaskRunner
from ms_preprocessing.gui.path_display import display_basename
from ms_preprocessing.gui.pipeline_controller import PipelineController
from ms_preprocessing.gui.pipeline_session import PipelineSession
from ms_preprocessing.gui.step_summary import summarize_step_result
from ms_preprocessing.gui.styles import COLORS
from ms_preprocessing.gui.validation import (
    ValidationWarning,
    format_validation_warnings,
)
from ms_preprocessing.workflow.parameter_resolver import ParameterResolver, WorkflowValidationService

if TYPE_CHECKING:
    class _MainWindowEventHost(Protocol):
        """Document the attributes and callbacks MainWindowEventHandlersMixin expects."""

        _output_dir: Path
        _project_root: Path
        _file_handler: Any
        _current_data: pd.DataFrame | None
        _original_data: pd.DataFrame | None
        _source_file: Path | None
        _current_step: int
        _completed_steps: set[int]
        _last_completed_step: int | None
        _last_run_all: bool
        _last_materialized_export_path: Path | None
        _pipeline_session: PipelineSession
        _step_output_paths: dict[int, Path]
        _context: dict[str, Any]
        _source_context_snapshot: dict[str, Any] | None
        step_widgets: list[Any]
        step_buttons: list[Any]
        _step_status_labels: list[Any]
        log_text: Any
        run_context_label: Any
        latest_result_label: Any
        run_all_profile_var: Any

        def _show_step(self, step_index: int) -> None: ...
        def configure(self, *args: Any, **kwargs: Any) -> None: ...


class MainWindowEventHandlersMixin:
    """Encapsulate file loading, step execution, and export flows.

    Expected host attributes and callbacks are documented by
    ``_MainWindowEventHost`` above.
    """

    def _new_pipeline_session(self: _MainWindowEventHost, source_file: Path | None) -> PipelineSession:
        return PipelineSession(output_dir=self._output_dir, source_file=source_file)

    def _display_name(self: _MainWindowEventHost, value: Any) -> str:
        if not value:
            return "not selected"
        return display_basename(value)

    def _safe_step_params(self: _MainWindowEventHost, step_index: int) -> dict[str, Any]:
        session_params = getattr(self._pipeline_session, "step_parameters", {}).get(step_index)
        if session_params:
            return dict(session_params)
        widgets = self.__dict__.get("step_widgets", [])
        if step_index >= len(widgets):
            return {}
        getter = getattr(widgets[step_index], "get_parameters", None)
        if not callable(getter):
            return {}
        try:
            return dict(getter())
        except Exception:
            return {}

    def _combined_tsv_state(self: _MainWindowEventHost) -> str:
        widgets = self.__dict__.get("step_widgets", [])
        if not widgets:
            return "not selected"
        getter = getattr(widgets[0], "get_combined_preprocessor_paths", None)
        if not callable(getter):
            return "not selected"
        try:
            paths = getter()
        except Exception:
            return "not selected"
        return "selected" if str(paths.get("combined_tsv") or "").strip() else "not selected"

    def _latest_output_name(self: _MainWindowEventHost) -> str:
        materialized = self.__dict__.get("_last_materialized_export_path")
        if materialized:
            return Path(materialized).name
        last_step = self.__dict__.get("_last_completed_step")
        step_paths = self.__dict__.get("_step_output_paths", {})
        if last_step is not None and step_paths.get(last_step):
            return Path(step_paths[last_step]).name
        return "not available"

    def _update_run_context_summary(self: _MainWindowEventHost) -> None:
        label = self.__dict__.get("run_context_label")
        if label is None:
            return

        step1_params = self._safe_step_params(0)
        step2_params = self._safe_step_params(1)

        method_file = step1_params.get("method_file")
        xic_results_file = step2_params.get("xic_results_file")

        lines = [
            "Run: "
            f"Source: {self._display_name(self.__dict__.get('_source_file'))} | "
            f"Step: {int(self.__dict__.get('_current_step', 0)) + 1} | "
            f"Completed: {len(self.__dict__.get('_completed_steps', set()))}",
            "Files: "
            f"Method: {self._display_name(method_file)} | "
            f"XIC: {self._display_name(xic_results_file)}",
            "Output: "
            f"Combined TSV: {self._combined_tsv_state()} | "
            f"Latest output: {self._latest_output_name()}",
        ]
        label.configure(text="\n".join(lines))

    def _update_latest_result_summary(
        self: _MainWindowEventHost,
        lines: list[str],
    ) -> None:
        label = self.__dict__.get("latest_result_label")
        if label is None:
            return
        if not lines:
            text = "Latest Result: waiting"
        elif len(lines) <= 2:
            text = f"Latest Result: {' | '.join(lines)}"
        else:
            text = "Latest Result:\n" + " | ".join(lines)
        label.configure(text=text)

    def _summarize_widget_result(
        self: _MainWindowEventHost,
        step_index: int,
        widget: Any,
        params: dict[str, Any] | None = None,
    ) -> list[str]:
        metadata_getter = getattr(widget, "get_metadata", None)
        metadata = metadata_getter() if callable(metadata_getter) else {}
        metadata = metadata or {}
        stats = metadata.get("statistics") or {}
        result_getter = getattr(widget, "get_processing_result", None)
        processing_result = result_getter() if callable(result_getter) else None
        if not stats and processing_result is not None:
            stats = getattr(processing_result, "statistics", {}) or {}
        if not isinstance(stats, dict):
            stats = {}
        parameters = dict(params or {})
        if not parameters:
            param_getter = getattr(widget, "get_last_parameters", None)
            if callable(param_getter):
                parameters = dict(param_getter())
        if step_index == 3 and hasattr(widget, "_export_deleted_var"):
            try:
                parameters["export_deleted_feature_sheet"] = bool(widget._export_deleted_var.get())
            except Exception:
                pass
        step_name = getattr(processing_result, "step", None)
        if not isinstance(step_name, str):
            step_name = Settings.WORKFLOW_STEPS[step_index][0]
        return summarize_step_result(step_name, stats, metadata, parameters)

    def _confirm_validation_warnings(
        self: _MainWindowEventHost,
        warnings: list[ValidationWarning],
    ) -> bool:
        try:
            return bool(
                messagebox.askokcancel(
                    "Parameter warning",
                    format_validation_warnings(warnings),
                )
            )
        except Exception:
            return True

    def _collect_run_all_validation_warnings(
        self: _MainWindowEventHost,
        params_by_step: list[dict[str, Any]],
    ) -> list[ValidationWarning]:
        resolved = ParameterResolver.from_gui_step_params(params_by_step)
        service = WorkflowValidationService()
        warnings: list[ValidationWarning] = []
        step_specs = (
            (0, "organize", "Step 1"),
            (1, "istd", "Step 2"),
            (3, "filter", "Step 4"),
        )
        for index, step_name, label in step_specs:
            if index >= len(params_by_step):
                continue
            for warning in service.collect(step_name, resolved):
                warnings.append(
                    ValidationWarning(
                        code=warning.code,
                        message=f"{label}: {warning.message}",
                        blocking=warning.blocking,
                    )
                )
        return warnings

    def _on_pipeline_profile_selected(self: _MainWindowEventHost, profile_name: str) -> None:
        self._apply_pipeline_profile_to_widgets(profile_name)

    def _ensure_async_state(self: _MainWindowEventHost) -> None:
        AsyncTaskRunner(self).ensure_state()

    def _can_schedule_ui_callbacks(self: _MainWindowEventHost) -> bool:
        return AsyncTaskRunner(self).can_schedule_ui_callbacks()

    def _dispatch_to_ui(
        self: _MainWindowEventHost,
        callback: Any,
        *args: Any,
    ) -> None:
        AsyncTaskRunner(self).dispatch(callback, *args)

    def _schedule_ui_queue_drain(self: _MainWindowEventHost) -> None:
        AsyncTaskRunner(self).schedule_ui_queue_drain()

    def _drain_ui_queue(self: _MainWindowEventHost) -> None:
        AsyncTaskRunner(self).drain_ui_queue()

    def _iter_pipeline_controls(self: _MainWindowEventHost) -> list[Any]:
        controls: list[Any] = []
        for attr_name in (
            "run_step_btn",
            "reset_step_btn",
            "export_results_btn",
            "open_output_folder_btn",
            "run_all_btn",
            "run_all_profile_menu",
        ):
            control = self.__dict__.get(attr_name)
            if control is not None and control not in controls:
                controls.append(control)

        for button in self.__dict__.get("step_buttons", []):
            if button not in controls:
                controls.append(button)

        for widget in self.__dict__.get("step_widgets", []):
            for attr_name in (
                "combined_tsv_btn",
                "combined_method_btn",
                "combined_run_btn",
            ):
                control = getattr(widget, attr_name, None)
                if control is not None and control not in controls:
                    controls.append(control)

        return controls

    def _set_pipeline_busy_state(self: _MainWindowEventHost, processing: bool) -> None:
        self._ensure_async_state()
        self._pipeline_is_processing = processing
        state = "disabled" if processing else "normal"
        for control in self._iter_pipeline_controls():
            try:
                control.configure(state=state)
            except Exception:
                continue
        try:
            self.configure(cursor="wait" if processing else "")
        except Exception:
            pass

    def _safe_update_action_bar_progress(
        self: _MainWindowEventHost,
        value: float,
        status: str = "",
    ) -> None:
        try:
            self._update_action_bar_progress(value, status)
        except Exception:
            pass

    def _apply_pipeline_profile_to_widgets(
        self: _MainWindowEventHost,
        profile_name: str,
        *,
        log: bool = True,
    ) -> None:
        profile = get_pipeline_profile(profile_name)
        for index, step_key in enumerate(("step1", "step2", "step3", "step4")):
            if index >= len(self.__dict__.get("step_widgets", [])):
                break
            apply_parameters = getattr(self.step_widgets[index], "apply_parameters", None)
            if callable(apply_parameters):
                apply_parameters(dict(profile[step_key]))

        profile_var = self.__dict__.get("run_all_profile_var")
        if profile_var is not None:
            profile_var.set(profile_name)

        if log:
            self._log(f"Applied Run All preset: {profile_name}")
            self._log_pipeline_profile_preview(profile_name)

    def _has_active_processing(self: _MainWindowEventHost) -> bool:
        self._ensure_async_state()
        if self._pipeline_is_processing:
            return True
        for widget in self.__dict__.get("step_widgets", []):
            state_getter = getattr(type(widget), "is_processing", None)
            if callable(state_getter):
                try:
                    if bool(widget.is_processing()):
                        return True
                except Exception:
                    continue
                continue

            explicit_state = getattr(widget, "_is_processing", False)
            if isinstance(explicit_state, bool) and explicit_state:
                return True

        return False

    def _auto_export_final_results(self: _MainWindowEventHost) -> Path | None:
        final_step_index = len(self.__dict__.get("step_widgets", [])) - 1
        if final_step_index < 0:
            return None
        if self._last_completed_step is None or self._last_completed_step < final_step_index:
            return None
        self._log("Final step complete. Auto-exporting results...")
        return self._export_results()

    def _attach_pipeline_session(self: _MainWindowEventHost, session: PipelineSession) -> None:
        self._pipeline_session = session
        self._step_output_paths = session.step_output_paths
        self._context = session.context

    def _snapshot_context(self: _MainWindowEventHost, context: dict[str, Any]) -> dict[str, Any]:
        """Copy source metadata so reruns can rebuild a clean pipeline session."""
        _ = context
        return copy.deepcopy(self._pipeline_session.metadata.as_context_dict())

    def _set_widget_session_metadata(self: _MainWindowEventHost, widget: Any) -> None:
        session = self.__dict__.get("_pipeline_session")
        if session is None:
            return

        metadata_setter = getattr(widget, "set_metadata", None)
        if callable(metadata_setter):
            metadata_setter(session.metadata)
            return

        context_setter = getattr(widget, "set_context", None)
        if callable(context_setter):
            context_setter(session.metadata.as_context_dict())

    def _reset_pipeline_for_run_all(self: _MainWindowEventHost) -> None:
        """Start Run All from the originally loaded source metadata, not prior run state."""
        PipelineController(self).reset_pipeline_for_run_all()

    def _load_file_for_step(
        self: _MainWindowEventHost,
        step_index: int,
        path: Path | None = None,
    ) -> None:
        if self._has_active_processing():
            self._log("Busy: wait for the current step to finish before loading another file.")
            return

        filetypes = [
            ("Excel files", "*.xlsx *.xls"),
            ("Parquet files", "*.parquet"),
            ("CSV files", "*.csv"),
            ("TSV files", "*.tsv *.txt"),
            ("All files", "*.*"),
        ]

        filepath = str(path) if path is not None else filedialog.askopenfilename(
            title="Select input file",
            filetypes=filetypes,
        )
        if not filepath:
            return

        try:
            self._log(f"Loading file: {filepath}")
            df, metadata = self._file_handler.load_data(filepath)
            loaded_path = Path(filepath)

            loaded_sample_info = None
            loaded_deleted_feature = None
            if loaded_path.suffix.lower() in {".xlsx", ".xls"}:
                try:
                    workbook = pd.ExcelFile(loaded_path)
                    if "SampleInfo" in workbook.sheet_names:
                        loaded_sample_info = pd.read_excel(loaded_path, sheet_name="SampleInfo")
                        self._log("Detected and loaded SampleInfo sheet.")
                    if "deleted_feature" in workbook.sheet_names:
                        loaded_deleted_feature = pd.read_excel(loaded_path, sheet_name="deleted_feature")
                        self._log("Detected and loaded deleted_feature sheet.")
                except Exception as exc:
                    self._log(f"Warning: could not read extra sheets from workbook: {exc}")

            self._current_data = df
            self._original_data = df.copy()
            self._source_file = loaded_path
            self._completed_steps = set()
            self._last_completed_step = None
            self._last_run_all = False
            self._last_materialized_export_path = None
            self._attach_pipeline_session(self._new_pipeline_session(loaded_path))
            self._pipeline_session.update_context_from_metadata(
                {
                    "red_font_rows": metadata.get("red_font_rows", []),
                    "protected_rows": metadata.get("protected_rows") or metadata.get("red_font_rows") or [],
                    "blue_font_cells": metadata.get("blue_font_cells", []),
                    "highlight_rows": metadata.get("highlight_rows", []),
                }
            )
            if loaded_sample_info is not None:
                self._pipeline_session.update_context_from_metadata({"sample_info": loaded_sample_info})
            if loaded_deleted_feature is not None:
                self._pipeline_session.update_context_from_metadata(
                    {"deleted_feature_df": loaded_deleted_feature}
                )
            self._context = self._pipeline_session.context
            self._source_context_snapshot = self._snapshot_context(self._context)

            if 0 <= step_index < len(self.step_widgets):
                self.step_widgets[step_index].set_input_file(filepath)
                self.step_widgets[step_index].set_data(df)
                self._set_widget_session_metadata(self.step_widgets[step_index])

            load_format = metadata.get("format", "unknown")
            self._log(f"Loaded successfully: {len(df)} rows, {len(df.columns)} columns (format: {load_format})")
            self._update_run_context_summary()
        except Exception as exc:
            self._log(f"Error loading file: {exc}")
            self._show_error(f"Failed to load file:\n{exc}")

    def _build_combined_fix_output_path(
        self: _MainWindowEventHost,
        raw_path: Path,
    ) -> Path:
        from ms_preprocessing.workflow.combined_tsv_service import CombinedTsvService

        return CombinedTsvService.build_output_path(raw_path=raw_path, output_dir=self._output_dir)

    def _run_combined_tsv_preprocessor(self: _MainWindowEventHost) -> None:
        PipelineController(self).run_combined_tsv_preprocessor()

    def _show_error(self: _MainWindowEventHost, message: str) -> None:
        self._log(f"ERROR: {message}")
        try:
            messagebox.showerror("Error", message)
        except Exception:
            pass

    def _switch_step(self: _MainWindowEventHost, step_index: int) -> None:
        if step_index < 0 or step_index >= len(self.step_widgets):
            return
        if self._has_active_processing() and step_index != self._current_step:
            self._log("Busy: cannot switch steps while processing is still running.")
            return

        self._current_step = step_index
        self._show_step(step_index)
        self._set_widget_session_metadata(self.step_widgets[step_index])

        for index, (button, status_label) in enumerate(
            zip(self.step_buttons, self._step_status_labels, strict=True)
        ):
            if index == step_index:
                button.configure(fg_color=COLORS["primary"])
                status_label.configure(text=">", text_color="#52b788")
            elif index in self._completed_steps:
                button.configure(fg_color="transparent")
                status_label.configure(text="OK", text_color="#52b788")
            else:
                button.configure(fg_color="transparent")
                status_label.configure(text="-", text_color="#4a6fa5")
        self._update_run_context_summary()

    def _run_current_step(self: _MainWindowEventHost) -> None:
        if 0 <= self._current_step < len(self.step_widgets):
            if getattr(self.step_widgets[self._current_step], "is_processing", lambda: False)():
                self._log("Busy: the current step is already processing.")
                return
            self.step_widgets[self._current_step]._on_run_clicked()

    def _reset_current_step(self: _MainWindowEventHost) -> None:
        if 0 <= self._current_step < len(self.step_widgets):
            if getattr(self.step_widgets[self._current_step], "is_processing", lambda: False)():
                self._log("Busy: wait for processing to finish before resetting the current step.")
                return
            self.step_widgets[self._current_step]._on_reset_clicked()

    def _on_step_complete(
        self: _MainWindowEventHost,
        result_data: pd.DataFrame,
        metadata: dict | None = None,
    ) -> None:
        step_index = self._current_step
        next_step = step_index + 1
        self._current_data = result_data
        current_widget = self.step_widgets[step_index]
        self._pipeline_session.record_step_parameters(
            step_index,
            current_widget.get_last_parameters(),
        )

        processing_result = current_widget.get_processing_result()
        if processing_result is not None:
            self._pipeline_session.update_from_result(processing_result)
        else:
            self._update_context_from_metadata(metadata)
        self._context = self._pipeline_session.context
        self._completed_steps.add(step_index)

        stats = current_widget.get_metadata().get("statistics") or {}
        current_widget.show_stats(stats)
        summary_lines = self._summarize_widget_result(step_index, current_widget)

        self._last_completed_step = step_index
        self._last_run_all = False

        if next_step < len(self.step_widgets):
            self.step_widgets[next_step].set_data(result_data)
            self._set_widget_session_metadata(self.step_widgets[next_step])
            self._switch_step(next_step)
            self._safe_update_action_bar_progress(
                100,
                f"Step {step_index + 1} complete. Step {next_step + 1} ready.",
            )
            self._update_latest_result_summary(summary_lines)
            self._update_run_context_summary()
            self._log(f"Data passed to Step {next_step + 1}")
            self._schedule_step_output_save(step_index, result_data, next_step_index=next_step)
            return

        self._update_latest_result_summary(summary_lines)
        self._auto_export_final_results()
        self._update_run_context_summary()

    def _run_all_steps(self: _MainWindowEventHost) -> None:
        PipelineController(self).run_all_steps()

    def _run_all_steps_worker(
        self: _MainWindowEventHost,
        original_step: int,
        data: pd.DataFrame,
        params_by_step: list[dict[str, Any]],
    ) -> None:
        PipelineController(self).run_all_steps_worker(original_step, data, params_by_step)

    def _finish_run_all_steps(
        self: _MainWindowEventHost,
        original_step: int,
        success: bool,
    ) -> None:
        PipelineController(self).finish_run_all_steps(original_step, success)

    def _export_results(self: _MainWindowEventHost) -> Path | None:
        return PipelineController(self).export_results()

    def _log_downstream_handoff_reminder(self: _MainWindowEventHost) -> None:
        step_widgets = self.__dict__.get("step_widgets", [])
        if not step_widgets:
            return
        final_step_index = len(step_widgets) - 1
        if self._last_completed_step is None or self._last_completed_step < final_step_index:
            return
        self._log("Step 4 final xlsx 已完成，可手動交給下游 normalization/statistics 使用。")
        self._log("Toolkit 不會再另外產生 DNP bridge 檔或啟動 DNP；請直接使用這份 final xlsx。")
        self._log(
            "進入下游流程前，請打開 SampleInfo，確認 Batch 已填寫，並補齊本批資料需要的"
            "校正欄位（例如組織量、肌酐或其他校正因子）與 metadata 欄位。"
        )

    def _materialize_final_xlsx_from_latest_step(self: _MainWindowEventHost) -> Path | None:
        return PipelineController(self).materialize_final_xlsx_from_latest_step()

    def _save_step_output(
        self: _MainWindowEventHost,
        step_index: int,
        data: pd.DataFrame,
    ) -> Path | None:
        if data is None:
            return None
        try:
            self._pipeline_session.set_source_file(self._source_file)
            filepath = self._pipeline_session.save_step_output(
                step_index=step_index,
                data=data,
                file_handler=self._file_handler,
            )
            self._log(f"Auto-saved: {filepath}")
            return filepath
        except Exception as exc:
            self._log(f"Auto-save error: {exc}")
            return None

    def _schedule_step_output_save(
        self: _MainWindowEventHost,
        step_index: int,
        data: pd.DataFrame,
        *,
        next_step_index: int | None = None,
    ) -> None:
        PipelineController(self).schedule_step_output_save(
            step_index,
            data,
            next_step_index=next_step_index,
        )

    def _run_step_output_save_worker(
        self: _MainWindowEventHost,
        step_index: int,
        data: pd.DataFrame,
        next_step_index: int | None,
        session_token: object,
        output_path: Path,
        formatting_context: dict[str, object],
    ) -> None:
        try:
            self._file_handler.save_data(
                data,
                output_path,
                sheet_name="RawIntensity",
                highlight_rows=formatting_context.get("highlight_rows"),
                blue_font_cells=formatting_context.get("blue_font_cells"),
                red_font_rows=formatting_context.get("red_font_rows"),
                save_parquet_cache=False,
            )
        except Exception as exc:
            error_message = str(exc)
            self._dispatch_to_ui(
                lambda: self._finish_deferred_step_output_save(
                    step_index=step_index,
                    next_step_index=next_step_index,
                    session_token=session_token,
                    path=None,
                    error_message=error_message,
                )
            )
            return

        self._dispatch_to_ui(
            lambda: self._finish_deferred_step_output_save(
                step_index=step_index,
                next_step_index=next_step_index,
                session_token=session_token,
                path=output_path,
                error_message=None,
            )
        )

    def _finish_deferred_step_output_save(
        self: _MainWindowEventHost,
        *,
        step_index: int,
        next_step_index: int | None,
        session_token: object,
        path: Path | None,
        error_message: str | None,
    ) -> None:
        if session_token != id(self._pipeline_session):
            return
        if error_message is not None:
            self._log(f"Auto-save error: {error_message}")
            return
        if path is None:
            self._log("Auto-save error: output path was not created")
            return

        self._step_output_paths[step_index] = path
        self._pipeline_session.step_output_paths[step_index] = path
        if next_step_index is not None and next_step_index < len(self.step_widgets):
            self.step_widgets[next_step_index].set_input_file(str(path))
        self._log(f"Auto-saved: {path}")
        self._update_run_context_summary()

    def _open_output_folder(self: _MainWindowEventHost) -> None:
        try:
            self._output_dir.mkdir(parents=True, exist_ok=True)
            system = platform.system()
            if system == "Windows":
                os.startfile(self._output_dir)
            elif system == "Darwin":
                subprocess.Popen(["open", str(self._output_dir)])
            else:
                subprocess.Popen(["xdg-open", str(self._output_dir)])
        except Exception as exc:
            self._log(f"Open output folder error: {exc}")

    def _log(self: _MainWindowEventHost, message: str) -> None:
        self._dispatch_to_ui(self._append_log_entry, message)

    def _log_pipeline_profile_preview(self: _MainWindowEventHost, profile_name: str) -> None:
        self._log("Preset parameters:")
        preview_lines = format_pipeline_profile_preview(profile_name).splitlines() or ["(none)"]
        for preview_line in preview_lines:
            self._log(f"  {preview_line}")

    def _append_log_entry(self: _MainWindowEventHost, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        self.log_text.see("end")

    def _clear_log(self: _MainWindowEventHost) -> None:
        self.log_text.delete("1.0", "end")

    def _update_context_from_metadata(
        self: _MainWindowEventHost,
        metadata: dict | None,
    ) -> None:
        self._pipeline_session.update_context_from_metadata(metadata)
        self._context = self._pipeline_session.context
