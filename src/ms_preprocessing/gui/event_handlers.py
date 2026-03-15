"""Workflow and export handlers for the main preprocessing window."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Any, Optional, Protocol

import pandas as pd

from ms_preprocessing.config.settings import Settings
from ms_preprocessing.gui.pipeline_session import PipelineSession
from ms_preprocessing.gui.styles import COLORS


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
        step_widgets: list[Any]
        step_buttons: list[Any]
        _step_status_labels: list[Any]
        export_dnp_btn: Any
        log_text: Any

        def _show_step(self, step_index: int) -> None: ...
        def update_idletasks(self) -> None: ...
        def configure(self, *args: Any, **kwargs: Any) -> None: ...


class MainWindowEventHandlersMixin:
    """Encapsulate file loading, step execution, and export flows.

    Expected host attributes and callbacks are documented by
    ``_MainWindowEventHost`` above.
    """

    def _new_pipeline_session(self: "_MainWindowEventHost", source_file: Path | None) -> PipelineSession:
        return PipelineSession(output_dir=self._output_dir, source_file=source_file)

    def _attach_pipeline_session(self: "_MainWindowEventHost", session: PipelineSession) -> None:
        self._pipeline_session = session
        self._step_output_paths = session.step_output_paths
        self._context = session.context

    def _load_file_for_step(
        self: "_MainWindowEventHost",
        step_index: int,
        path: Optional[Path] = None,
    ) -> None:
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

            if 0 <= step_index < len(self.step_widgets):
                self.step_widgets[step_index].set_input_file(filepath)
                self.step_widgets[step_index].set_data(df)
                self.step_widgets[step_index].set_context(self._context)

            load_format = metadata.get("format", "unknown")
            self._log(f"Loaded successfully: {len(df)} rows, {len(df.columns)} columns (format: {load_format})")
            self._update_export_dnp_btn()
        except Exception as exc:
            self._log(f"Error loading file: {exc}")
            self._show_error(f"Failed to load file:\n{exc}")

    def _show_error(self: "_MainWindowEventHost", message: str) -> None:
        self._log(f"ERROR: {message}")
        try:
            messagebox.showerror("Error", message)
        except Exception:
            pass

    def _switch_step(self: "_MainWindowEventHost", step_index: int) -> None:
        if step_index < 0 or step_index >= len(self.step_widgets):
            return

        self._current_step = step_index
        self._show_step(step_index)
        self.step_widgets[step_index].set_context(self._context)
        if hasattr(self, "_step_output_paths") and self._step_output_paths.get(step_index):
            self.step_widgets[step_index].set_input_file(str(self._step_output_paths[step_index]))

        for index, (button, status_label) in enumerate(zip(self.step_buttons, self._step_status_labels)):
            if index == step_index:
                button.configure(fg_color=COLORS["primary"])
                status_label.configure(text=">", text_color="#52b788")
            elif index in self._completed_steps:
                button.configure(fg_color="transparent")
                status_label.configure(text="OK", text_color="#52b788")
            else:
                button.configure(fg_color="transparent")
                status_label.configure(text="-", text_color="#4a6fa5")

    def _run_current_step(self: "_MainWindowEventHost") -> None:
        if 0 <= self._current_step < len(self.step_widgets):
            self.step_widgets[self._current_step]._on_run_clicked()

    def _reset_current_step(self: "_MainWindowEventHost") -> None:
        if 0 <= self._current_step < len(self.step_widgets):
            self.step_widgets[self._current_step]._on_reset_clicked()

    def _on_step_complete(
        self: "_MainWindowEventHost",
        result_data: pd.DataFrame,
        metadata: Optional[dict] = None,
    ) -> None:
        self._current_data = result_data
        current_widget = self.step_widgets[self._current_step]
        self._pipeline_session.record_step_parameters(
            self._current_step,
            current_widget.get_last_parameters(),
        )

        processing_result = current_widget.get_processing_result()
        if processing_result is not None:
            self._pipeline_session.update_from_result(processing_result)
        else:
            self._update_context_from_metadata(metadata)
        self._context = self._pipeline_session.context
        self._completed_steps.add(self._current_step)

        stats = current_widget.get_metadata().get("statistics") or {}
        current_widget.show_stats(stats)

        self._last_completed_step = self._current_step
        self._last_run_all = False
        self._update_export_dnp_btn()

        output_path = self._save_step_output(self._current_step, result_data)
        if output_path:
            self._step_output_paths[self._current_step] = output_path
            current_widget.set_input_file(str(output_path))

        next_step = self._current_step + 1
        if next_step < len(self.step_widgets):
            self.step_widgets[next_step].set_data(result_data)
            self.step_widgets[next_step].set_context(self._context)
            if output_path:
                self.step_widgets[next_step].set_input_file(str(output_path))
            self._log(f"Data passed to Step {next_step + 1}")

    def _run_all_steps(self: "_MainWindowEventHost") -> None:
        if self._current_data is None or self._original_data is None:
            self._log("Error: Please load a file first")
            return

        original_step = self._current_step
        try:
            data = self._original_data.copy()

            for index, widget in enumerate(self.step_widgets):
                step_name = Settings.WORKFLOW_STEPS[index][0]
                if not self._pipeline_session.can_run_step(step_name):
                    raise RuntimeError(
                        f"Cannot run Step {index + 1} ({step_name}) before its prerequisites are complete."
                    )
                self._current_step = index
                self._log(f"Running Step {index + 1}...")
                widget.set_data(data)
                widget.set_context(self._context)

                params = widget.get_parameters()
                self._pipeline_session.record_step_parameters(index, params)
                data = widget.run_processing(data, **params)

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
                    widget.set_input_file(str(output_path))
                    if index + 1 < len(self.step_widgets):
                        self.step_widgets[index + 1].set_input_file(str(output_path))
                self._log(f"Step {index + 1} completed")
                self.update_idletasks()

            self._last_run_all = True
            self._update_export_dnp_btn()
            self._log("All steps completed successfully!")
        except Exception as exc:
            self._log(f"Pipeline error: {exc}")
        finally:
            self._switch_step(min(original_step, len(self.step_widgets) - 1))

    def _export_results(self: "_MainWindowEventHost") -> Optional[Path]:
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
            return filepath
        except Exception as exc:
            self._log(f"Export error: {exc}")
            return None

    def _update_export_dnp_btn(self: "_MainWindowEventHost") -> None:
        ready = self._last_completed_step is not None and self._last_completed_step >= 3
        if ready:
            self.export_dnp_btn.configure(
                state="normal",
                text="Export DNP",
                fg_color="#1a73e8",
            )
        else:
            self.export_dnp_btn.configure(
                state="disabled",
                text="Export DNP",
                fg_color="#6b7280",
            )

    def _export_to_dnp(self: "_MainWindowEventHost") -> None:
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
            desktop = Path.home() / "Desktop"
            dnp_candidates = [
                desktop / "Data_Normalization_project_v2" / "src",
                self._project_root.parent / "Data_Normalization_project_v2" / "src",
            ]
            for dnp_src in dnp_candidates:
                if dnp_src.exists() and str(dnp_src) not in sys.path:
                    sys.path.insert(0, str(dnp_src))
                    break

            from metabolomics.adapters.preprocessing_to_dnp import convert_preprocessing_to_dnp

            self._log(f"Converting to DNP format: {source_path}")
            result = Path(convert_preprocessing_to_dnp(str(source_path), output_path))
            self._log(f"DNP export complete: {result}")
            self._open_file_in_system_app(result)
            needs_completion = self._sample_info_requires_user_completion(result)
            message = (
                "請在 SampleInfo 工作表補齊 Batch 與 DNA_mg/20uL 欄位後，再手動啟動 DNP。"
                if needs_completion
                else "Bridge 檔案已就緒，請手動啟動 DNP。"
            )
            messagebox.showinfo(
                "匯出成功",
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

    def _sample_info_requires_user_completion(self, bridge_path: "str | Path") -> bool:
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

    def _open_file_in_system_app(self, target: "str | Path") -> None:
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

    def _materialize_final_xlsx_from_latest_step(self: "_MainWindowEventHost") -> Optional[Path]:
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
            return target_path
        except Exception as exc:
            self._log(f"Materialization error: {exc}")
            return None

    def _launch_dnp(self: "_MainWindowEventHost") -> None:
        desktop = Path.home() / "Desktop"
        candidates = [
            desktop / "Data_Normalization_project_v2" / "src" / "metabolomics" / "__main__.py",
        ]
        for main_py in candidates:
            if main_py.exists():
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
        self: "_MainWindowEventHost",
        step_index: int,
        data: pd.DataFrame,
    ) -> Optional[Path]:
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

    def _open_output_folder(self: "_MainWindowEventHost") -> None:
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

    def _log(self: "_MainWindowEventHost", message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        self.log_text.see("end")

    def _clear_log(self: "_MainWindowEventHost") -> None:
        self.log_text.delete("1.0", "end")

    def _update_context_from_metadata(
        self: "_MainWindowEventHost",
        metadata: Optional[dict],
    ) -> None:
        self._pipeline_session.update_context_from_metadata(metadata)
        self._context = self._pipeline_session.context
