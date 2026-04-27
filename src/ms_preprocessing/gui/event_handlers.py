"""Workflow and export handlers for the main preprocessing window."""

from __future__ import annotations

import copy
import os
import platform
import queue
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Any, Protocol

import pandas as pd

from ms_preprocessing.adapters import data_organizer as data_organizer_adapter
from ms_preprocessing.bootstrap_paths import ensure_dnp_bridge_on_path, find_dnp_main_module
from ms_preprocessing.config import format_pipeline_profile_preview, get_pipeline_profile
from ms_preprocessing.config.settings import Settings
from ms_preprocessing.gui.path_display import display_basename
from ms_preprocessing.gui.pipeline_session import PipelineSession
from ms_preprocessing.gui.step_summary import summarize_step_result
from ms_preprocessing.gui.styles import COLORS
from ms_preprocessing.gui.validation import (
    ValidationWarning,
    format_validation_warnings,
    has_blocking_warnings,
)

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
        export_dnp_btn: Any
        log_text: Any
        run_context_label: Any
        latest_result_label: Any
        run_all_profile_var: Any

        def _show_step(self, step_index: int) -> None: ...
        def update_idletasks(self) -> None: ...
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

        context = self.__dict__.get("_context", {}) or {}
        step1_params = self._safe_step_params(0)
        step2_params = self._safe_step_params(1)

        method_file = context.get("method_file") or step1_params.get("method_file")
        istd_record = context.get("istd_record_file") or step2_params.get("istd_record_file")
        istd_date = context.get("istd_record_date") or step2_params.get("istd_record_date")

        lines = [
            "Run: "
            f"Source: {self._display_name(self.__dict__.get('_source_file'))} | "
            f"Step: {int(self.__dict__.get('_current_step', 0)) + 1} | "
            f"Completed: {len(self.__dict__.get('_completed_steps', set()))}",
            "Files: "
            f"Method: {self._display_name(method_file)} | "
            f"ISTD: {self._display_name(istd_record)} | "
            f"Date: {istd_date or 'not set'}",
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
        warnings: list[ValidationWarning] = []
        for index, params in enumerate(params_by_step):
            if index >= len(self.__dict__.get("step_widgets", [])):
                continue
            validator = getattr(self.step_widgets[index], "validate_parameters", None)
            if not callable(validator):
                continue
            step_warnings = validator(params)
            if not isinstance(step_warnings, (list, tuple)):
                continue
            for warning in step_warnings:
                warnings.append(
                    ValidationWarning(
                        code=warning.code,
                        message=f"Step {index + 1}: {warning.message}",
                        blocking=warning.blocking,
                    )
                )
        return warnings

    def _on_pipeline_profile_selected(self: _MainWindowEventHost, profile_name: str) -> None:
        self._apply_pipeline_profile_to_widgets(profile_name)

    def _ensure_async_state(self: _MainWindowEventHost) -> None:
        if "_ui_thread_id" not in self.__dict__:
            self._ui_thread_id = threading.get_ident()
        if "_ui_queue" not in self.__dict__:
            self._ui_queue = queue.SimpleQueue()
        if "_ui_queue_after_id" not in self.__dict__:
            self._ui_queue_after_id = None
        if "_pipeline_worker_thread" not in self.__dict__:
            self._pipeline_worker_thread = None
        if "_pipeline_is_processing" not in self.__dict__:
            self._pipeline_is_processing = False
        if "_step_output_save_threads" not in self.__dict__:
            self._step_output_save_threads = []

    def _can_schedule_ui_callbacks(self: _MainWindowEventHost) -> bool:
        after = getattr(self, "after", None)
        winfo_exists = getattr(self, "winfo_exists", None)
        return "tk" in self.__dict__ and callable(after) and callable(winfo_exists)

    def _dispatch_to_ui(
        self: _MainWindowEventHost,
        callback: Any,
        *args: Any,
    ) -> None:
        self._ensure_async_state()
        if threading.get_ident() == self._ui_thread_id or not self._can_schedule_ui_callbacks():
            callback(*args)
            return
        self._ui_queue.put((callback, args))

    def _schedule_ui_queue_drain(self: _MainWindowEventHost) -> None:
        self._ensure_async_state()
        if not self._can_schedule_ui_callbacks():
            return
        if self._ui_queue_after_id is not None:
            return
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        self._ui_queue_after_id = self.after(16, self._drain_ui_queue)

    def _drain_ui_queue(self: _MainWindowEventHost) -> None:
        self._ui_queue_after_id = None
        if not self._can_schedule_ui_callbacks():
            return
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        while True:
            try:
                callback, args = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            callback(*args)

        save_threads = [
            thread
            for thread in self.__dict__.get("_step_output_save_threads", [])
            if thread.is_alive()
        ]
        self._step_output_save_threads = save_threads
        worker_alive = (
            self._pipeline_worker_thread is not None and self._pipeline_worker_thread.is_alive()
        ) or bool(save_threads)
        if worker_alive or not self._ui_queue.empty():
            self._schedule_ui_queue_drain()

    def _iter_pipeline_controls(self: _MainWindowEventHost) -> list[Any]:
        controls: list[Any] = []
        for attr_name in (
            "run_step_btn",
            "reset_step_btn",
            "export_results_btn",
            "open_output_folder_btn",
            "run_all_btn",
            "export_dnp_btn",
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
        return copy.deepcopy(context)

    def _reset_pipeline_for_run_all(self: _MainWindowEventHost) -> None:
        """Start Run All from the originally loaded source metadata, not prior run state."""
        self._completed_steps = set()
        self._last_completed_step = None
        self._last_run_all = False
        self._last_materialized_export_path = None

        source_snapshot = copy.deepcopy(self.__dict__.get("_source_context_snapshot"))
        if source_snapshot is None:
            if "_step_output_paths" in self.__dict__:
                self._step_output_paths.clear()
            return

        session = self._new_pipeline_session(self._source_file)
        self._attach_pipeline_session(session)
        session.update_context_from_metadata(source_snapshot)
        self._context = session.context

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
                self.step_widgets[step_index].set_context(self._context)

            load_format = metadata.get("format", "unknown")
            self._log(f"Loaded successfully: {len(df)} rows, {len(df.columns)} columns (format: {load_format})")
            self._update_export_dnp_btn()
            self._update_run_context_summary()
        except Exception as exc:
            self._log(f"Error loading file: {exc}")
            self._show_error(f"Failed to load file:\n{exc}")

    def _build_combined_fix_output_path(
        self: _MainWindowEventHost,
        raw_path: Path,
    ) -> Path:
        output_dir = self._output_dir / "combined_fix"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = output_dir / f"{raw_path.stem}_combined_fix_{timestamp}.xlsx"
        if not base.exists():
            return base

        counter = 2
        while True:
            candidate = output_dir / f"{raw_path.stem}_combined_fix_{timestamp}_{counter}.xlsx"
            if not candidate.exists():
                return candidate
            counter += 1

    def _run_combined_tsv_preprocessor(self: _MainWindowEventHost) -> None:
        if self._has_active_processing():
            self._log("Busy: wait for the current task to finish before creating combined_fix.")
            return

        if not self.__dict__.get("step_widgets"):
            self._show_error("Step 1 widget is not available.")
            return

        widget = self.step_widgets[0]
        path_getter = getattr(widget, "get_combined_preprocessor_paths", None)
        if not callable(path_getter):
            self._show_error("Combined TSV controls are not available.")
            return

        paths = path_getter()
        raw_text = str(paths.get("combined_tsv") or "").strip()
        method_text = str(paths.get("method_file") or "").strip()
        if not raw_text:
            self._show_error("Please select a combined TSV file first.")
            return

        raw_path = Path(raw_text)
        if not raw_path.exists():
            self._show_error(f"Combined TSV file not found:\n{raw_path}")
            return

        output_path = self._build_combined_fix_output_path(raw_path)
        loaded_path: Path | None = None

        self._set_pipeline_busy_state(True)
        try:
            self._log(f"Creating combined_fix file from: {raw_path}")
            result = data_organizer_adapter.run_combined_fix(
                str(raw_path),
                method_file=method_text or None,
                progress_callback=self._safe_update_action_bar_progress,
            )
            if not result.success or result.data is None:
                self._show_error(result.error or "Combined TSV preprocessing failed.")
                return

            output_path.parent.mkdir(parents=True, exist_ok=True)
            saved_path = self._file_handler.save_data(
                result.data,
                output_path,
                save_parquet_cache=False,
            )
            loaded_path = Path(saved_path)

            stats = result.statistics or {}
            removed = stats.get("removed_features", "unknown")
            output_features = stats.get("output_features", len(result.data))
            self._log(
                f"Combined TSV preprocessing complete: {output_features} features kept, "
                f"{removed} removed. Output: {loaded_path}"
            )
        except Exception as exc:
            self._show_error(f"Combined TSV preprocessing failed:\n{exc}")
            return
        finally:
            self._set_pipeline_busy_state(False)

        if loaded_path is None:
            return

        self._load_file_for_step(0, path=loaded_path)
        prefill = getattr(self.step_widgets[0], "prefill_normal_method_from_combined", None)
        if callable(prefill):
            prefill()
        self._last_materialized_export_path = loaded_path
        self._update_run_context_summary()
        self._log("Ready: review Step 1 settings, then run Step 1 or Run All.")

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
        self.step_widgets[step_index].set_context(self._context)

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
            self.step_widgets[next_step].set_context(self._context)
            self._switch_step(next_step)
            self._safe_update_action_bar_progress(
                100,
                f"Step {step_index + 1} complete. Step {next_step + 1} ready.",
            )
            self._update_latest_result_summary(summary_lines)
            self._update_export_dnp_btn()
            self._update_run_context_summary()
            self._log(f"Data passed to Step {next_step + 1}")
            self._schedule_step_output_save(step_index, result_data, next_step_index=next_step)
            return

        self._update_latest_result_summary(summary_lines)
        self._update_export_dnp_btn()
        self._auto_export_final_results()
        self._update_run_context_summary()

    def _run_all_steps(self: _MainWindowEventHost) -> None:
        if self._has_active_processing():
            self._log("Busy: wait for the current step to finish before running the full pipeline.")
            return

        if self._current_data is None or self._original_data is None:
            self._log("Error: Please load a file first")
            return

        original_step = self._current_step
        try:
            data = self._original_data.copy()
            params_by_step = [dict(widget.get_parameters()) for widget in self.step_widgets]
        except Exception as exc:
            self._log(f"Error preparing Run All: {exc}")
            return

        profile_var = self.__dict__.get("run_all_profile_var")
        profile_name = "default"
        if profile_var is not None:
            try:
                profile_name = str(profile_var.get())
            except Exception:
                profile_name = "default"
        self._log(f"Run All preset: {profile_name}")
        self._log_pipeline_profile_preview(profile_name)

        validation_warnings = self._collect_run_all_validation_warnings(params_by_step)
        if validation_warnings:
            validation_message = format_validation_warnings(validation_warnings)
            if has_blocking_warnings(validation_warnings):
                self._log(f"Validation blocked Run All:\n{validation_message}")
                self._show_error(validation_message)
                return
            self._log(f"Validation warning before Run All:\n{validation_message}")
            if not self._confirm_validation_warnings(validation_warnings):
                self._log("Run All cancelled after validation warning.")
                return

        self._set_pipeline_busy_state(True)
        self._safe_update_action_bar_progress(0, "Running all steps...")

        if self._can_schedule_ui_callbacks():
            self._schedule_ui_queue_drain()
            self._pipeline_worker_thread = threading.Thread(
                target=self._run_all_steps_worker,
                args=(original_step, data, params_by_step),
                daemon=True,
                name="run-all-worker",
            )
            self._pipeline_worker_thread.start()
            return

        self._run_all_steps_worker(original_step, data, params_by_step)

    def _run_all_steps_worker(
        self: _MainWindowEventHost,
        original_step: int,
        data: pd.DataFrame,
        params_by_step: list[dict[str, Any]],
    ) -> None:
        success = False
        try:
            self._reset_pipeline_for_run_all()

            for index, widget in enumerate(self.step_widgets):
                step_name = Settings.WORKFLOW_STEPS[index][0]
                if not self._pipeline_session.can_run_step(step_name):
                    raise RuntimeError(
                        f"Cannot run Step {index + 1} ({step_name}) before its prerequisites are complete."
                    )

                self._current_step = index
                self._dispatch_to_ui(
                    self._safe_update_action_bar_progress,
                    0,
                    f"Running Step {index + 1}/{len(self.step_widgets)}...",
                )
                self._log(f"Running Step {index + 1}...")

                params = dict(params_by_step[index])
                widget._data = data
                widget._last_parameters = dict(params)
                widget._last_metadata = {}
                widget._processing_result = None
                widget._result = None
                widget.set_context(self._context)
                data = widget.run_processing(data, **params)
                widget._result = data

                self._pipeline_session.record_step_parameters(index, params)
                processing_result = widget.get_processing_result()
                if processing_result is not None:
                    self._pipeline_session.update_from_result(processing_result)
                else:
                    self._update_context_from_metadata(widget.get_metadata())
                self._context = self._pipeline_session.context
                self._completed_steps.add(index)

                self._current_data = data
                self._last_completed_step = index
                output_path = self._save_step_output(index, data)
                if output_path:
                    self._step_output_paths[index] = output_path
                self._log(f"Step {index + 1} completed")
                summary_lines = self._summarize_widget_result(index, widget, params)
                for line in summary_lines:
                    self._log(f"Step {index + 1} summary: {line}")
                self._dispatch_to_ui(self._update_latest_result_summary, summary_lines)
                self._dispatch_to_ui(self._update_run_context_summary)

            self._last_run_all = True
            self._dispatch_to_ui(self._safe_update_action_bar_progress, 100, "All steps complete!")
            self._log("All steps completed successfully!")
            success = True
        except Exception as exc:
            self._last_run_all = False
            self._dispatch_to_ui(self._safe_update_action_bar_progress, 0, f"Pipeline error: {exc}")
            self._log(f"Pipeline error: {exc}")
        finally:
            self._dispatch_to_ui(self._finish_run_all_steps, original_step, success)

    def _finish_run_all_steps(
        self: _MainWindowEventHost,
        original_step: int,
        success: bool,
    ) -> None:
        self._pipeline_worker_thread = None
        self._set_pipeline_busy_state(False)
        try:
            self._update_export_dnp_btn()
        except Exception:
            pass
        if not success:
            self._safe_update_action_bar_progress(0, "Run All failed")
        else:
            self._auto_export_final_results()
            self._update_run_context_summary()
        self._switch_step(min(original_step, len(self.step_widgets) - 1))

    def _export_results(self: _MainWindowEventHost) -> Path | None:
        if self._has_active_processing():
            self._log("Busy: wait for processing to finish before exporting results.")
            return None

        if self._current_data is None:
            materialized = self._materialize_final_xlsx_from_latest_step()
            if materialized is None:
                self._log("Error: No data to export")
            return materialized

        self._pipeline_session.set_source_file(self._source_file)
        filepath = self._pipeline_session.build_final_export_path(
            last_completed_step=self._last_completed_step,
            last_run_all=self._last_run_all,
            suffix=".xlsx",
        )

        try:
            session_context = self._pipeline_session.context
            extra_sheets: dict[str, pd.DataFrame] = {}
            sample_info = session_context.get("sample_info")
            if sample_info is not None:
                extra_sheets["SampleInfo"] = sample_info
            if self.step_widgets[3]._export_deleted_var.get():
                deleted_df = session_context.get("deleted_feature_df")
                if isinstance(deleted_df, pd.DataFrame) and not deleted_df.empty:
                    extra_sheets["deleted_feature"] = deleted_df

            self._file_handler.save_data(
                self._current_data,
                filepath,
                sheet_name="RawIntensity",
                highlight_rows=session_context.get("highlight_rows"),
                blue_font_cells=session_context.get("blue_font_cells"),
                red_font_rows=session_context.get("red_font_rows"),
                extra_sheets=extra_sheets or None,
                save_parquet_cache=False,
            )
            self._last_materialized_export_path = filepath
            self._log(f"Exported to: {filepath}")
            self._update_run_context_summary()
            return filepath
        except Exception as exc:
            self._log(f"Export error: {exc}")
            return None

    def _update_export_dnp_btn(self: _MainWindowEventHost) -> None:
        ready = self._last_completed_step is not None and self._last_completed_step >= 3
        if ready:
            self.export_dnp_btn.configure(
                state="normal",
                text="Export DNP",
            )
            if hasattr(self, "_apply_action_button_theme"):
                self._apply_action_button_theme(self.export_dnp_btn, "secondary")
        else:
            self.export_dnp_btn.configure(
                state="disabled",
                text="Export DNP",
            )
            if hasattr(self, "_apply_action_button_theme"):
                self._apply_action_button_theme(self.export_dnp_btn, "disabled")

    def _export_to_dnp(self: _MainWindowEventHost) -> None:
        if self._has_active_processing():
            self._log("Busy: wait for processing to finish before exporting to DNP.")
            return

        if self._last_completed_step is None or self._last_completed_step < 3:
            messagebox.showwarning(
                "Not Ready",
                "Please complete Step 4 (Feature Filtering) before exporting to DNP.",
            )
            return

        source_path = self._export_results()
        if source_path is None:
            messagebox.showerror("Error", "No output file found. Please export first.")
            return

        output_path = filedialog.asksaveasfilename(
            title="Save DNP-compatible file",
            defaultextension=".xlsx",
            initialfile=f"DNP_import_{Path(source_path).stem}.xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
        )
        if not output_path:
            return

        original_text = self.export_dnp_btn.cget("text")
        self.export_dnp_btn.configure(text="Exporting...", state="disabled")
        self.configure(cursor="wait")
        self.update_idletasks()

        try:
            dnp_src = ensure_dnp_bridge_on_path(self._project_root)
            if dnp_src is None:
                raise ImportError("Data_Normalization_project_v2 src not found")
            self._log(f"Using DNP bridge source: {dnp_src}")

            from metabolomics.adapters.preprocessing_to_dnp import convert_preprocessing_to_dnp

            self._log(f"Converting to DNP format: {source_path}")
            result = Path(convert_preprocessing_to_dnp(str(source_path), output_path))
            self._log(f"DNP export complete: {result}")
            self._open_file_in_system_app(result)
            needs_completion = self._sample_info_requires_user_completion(result)
            message = (
                "請在 SampleInfo 工作表補齊 Batch 與 DNA_mg/20uL 欄位後，再手動啟動 DNP。"
                if needs_completion
                else "Bridge 檔案已可直接匯入 DNP。"
            )
            messagebox.showinfo(
                "匯出完成",
                f"DNP bridge 檔案已匯出：\n{result}\n\n{message}",
            )
        except ImportError:
            self._log("Error: DNP adapter not found. Ensure Data_Normalization_project_v2 is available.")
            messagebox.showerror(
                "Adapter Not Found",
                "Could not find the DNP adapter module.\nEnsure Data_Normalization_project_v2 is available.",
            )
        except Exception as exc:
            self._log(f"DNP export error: {exc}")
            messagebox.showerror("Export Failed", f"Conversion error:\n{exc}")
        finally:
            self.configure(cursor="")
            self.export_dnp_btn.configure(text=original_text, state="normal")
            self._update_export_dnp_btn()

    def _sample_info_requires_user_completion(self, bridge_path: str | Path) -> bool:
        """Return True when SampleInfo sheet is missing Batch or DNA_mg/20uL values."""
        try:
            sample_info = pd.read_excel(Path(bridge_path), sheet_name="SampleInfo")
        except Exception:
            return True
        for column in ("Batch", "DNA_mg/20uL"):
            if column not in sample_info.columns:
                return True
            if sample_info[column].fillna("").astype(str).str.strip().eq("").any():
                return True
        return False

    def _open_file_in_system_app(self, target: str | Path) -> None:
        """Open a file using the system default application."""
        try:
            target_path = Path(target)
            system = platform.system()
            if system == "Windows":
                os.startfile(target_path)
            elif system == "Darwin":
                subprocess.Popen(["open", str(target_path)])
            else:
                subprocess.Popen(["xdg-open", str(target_path)])
        except Exception as exc:
            self._log(f"Open file error: {exc}")

    def _materialize_final_xlsx_from_latest_step(self: _MainWindowEventHost) -> Path | None:
        if self._last_completed_step is None:
            return None
        source_path = self._step_output_paths.get(self._last_completed_step)
        if source_path is None:
            return None

        source_path = Path(source_path)
        if source_path.suffix.lower() == ".xlsx":
            self._last_materialized_export_path = source_path
            return source_path

        self._pipeline_session.set_source_file(self._source_file)
        target_path = self._pipeline_session.build_final_export_path(
            last_completed_step=self._last_completed_step,
            last_run_all=self._last_run_all,
            suffix=".xlsx",
        )

        try:
            data, metadata = self._file_handler.load_data(source_path)
            self._pipeline_session.update_context_from_metadata(metadata)
            self._context = self._pipeline_session.context
            self._current_data = data

            session_context = self._pipeline_session.context
            extra_sheets: dict[str, pd.DataFrame] = {}
            sample_info = session_context.get("sample_info")
            if sample_info is not None:
                extra_sheets["SampleInfo"] = sample_info
            if self.step_widgets[3]._export_deleted_var.get():
                deleted_df = session_context.get("deleted_feature_df")
                if isinstance(deleted_df, pd.DataFrame) and not deleted_df.empty:
                    extra_sheets["deleted_feature"] = deleted_df

            self._file_handler.save_data(
                data,
                target_path,
                sheet_name="RawIntensity",
                highlight_rows=session_context.get("highlight_rows"),
                blue_font_cells=session_context.get("blue_font_cells"),
                red_font_rows=session_context.get("red_font_rows"),
                extra_sheets=extra_sheets or None,
                save_parquet_cache=False,
            )
            self._step_output_paths[self._last_completed_step] = target_path
            self._last_materialized_export_path = target_path
            self._log(f"Materialized final xlsx from parquet: {target_path}")
            self._update_run_context_summary()
            return target_path
        except Exception as exc:
            self._log(f"Materialization error: {exc}")
            return None

    def _launch_dnp(self: _MainWindowEventHost) -> None:
        main_py = find_dnp_main_module(self._project_root)
        if main_py is not None:
            self._log(f"Launching DNP: {main_py}")
            subprocess.Popen(
                [sys.executable, "-m", "metabolomics"],
                cwd=str(main_py.parent.parent),
            )
            return
        messagebox.showwarning(
            "Not Found",
            "Could not find Data_Normalization_project_v2.\nPlease launch it manually.",
        )

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
        if data is None:
            return
        try:
            self._ensure_async_state()
            session = self._pipeline_session
            session.set_source_file(getattr(self, "_source_file", None))
            output_path = session.build_step_output_path(step_index)
            formatting_context = {
                "highlight_rows": set(session.context.get("highlight_rows") or []),
                "blue_font_cells": list(session.context.get("blue_font_cells") or []),
                "red_font_rows": set(session.context.get("red_font_rows") or []),
            }
            session_token = id(session)
            data_snapshot = data.copy(deep=False)
        except Exception as exc:
            self._log(f"Auto-save error: {exc}")
            return

        worker = threading.Thread(
            target=self._run_step_output_save_worker,
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
        self._step_output_save_threads.append(worker)
        self._schedule_ui_queue_drain()
        worker.start()

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
