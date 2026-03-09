"""
Main Window for MS Preprocessing Toolkit GUI.
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

import customtkinter as ctk
from tkinter import filedialog, messagebox
import pandas as pd

from ms_preprocessing.gui.styles import COLORS, FONTS, PADDING, DIMENSIONS
from ms_preprocessing.gui.widgets.data_organizer_widget import DataOrganizerWidget
from ms_preprocessing.gui.widgets.istd_marker_widget import ISTDMarkerWidget
from ms_preprocessing.gui.widgets.duplicate_remover_widget import DuplicateRemoverWidget
from ms_preprocessing.gui.widgets.feature_filter_widget import FeatureFilterWidget
from ms_preprocessing.gui.pipeline_session import PipelineSession
from ms_core.utils.file_handler import FileHandler
from ms_preprocessing.config.settings import Settings


class MainWindow(ctk.CTk):
    """
    Main application window for MS Preprocessing Toolkit.

    Provides a workflow-based interface for preprocessing mass spectrometry data
    through four steps:
    1. Data Organization
    2. ISTD Marking
    3. Duplicate Removal
    4. Feature Filtering
    """

    def __init__(self):
        """Initialize the main window."""
        super().__init__()

        # Configure customtkinter
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # Window setup
        self.title(Settings.WINDOW_TITLE)
        self.geometry(f"{Settings.WINDOW_SIZE[0]}x{Settings.WINDOW_SIZE[1]}")
        self.minsize(1000, 650)

        # Project root/output
        self._project_root = Path(__file__).resolve().parents[3]
        self._output_dir = self._project_root / "OUTPUT"

        # Data state
        self._file_handler = FileHandler()
        self._current_data: Optional[pd.DataFrame] = None
        self._original_data: Optional[pd.DataFrame] = None
        self._source_file: Optional[Path] = None
        self._current_step = 0
        self._last_completed_step: Optional[int] = None
        self._last_run_all: bool = False
        self._completed_steps: set = set()
        self._pipeline_session = PipelineSession(output_dir=self._output_dir, source_file=None)
        self._step_output_paths = self._pipeline_session.step_output_paths
        self._context = self._pipeline_session.context
        self._last_materialized_export_path: Optional[Path] = None

        # Create layout
        self._create_layout()

        # Bind keyboard shortcuts
        self._bind_shortcuts()

    def _create_layout(self) -> None:
        """Create the main window layout (5 zones)."""
        # column 0: sidebar (fixed), column 1: main content (expands)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        # row 0: pipeline nav (fixed)
        # row 1: main content (expands)
        # row 2: action bar (fixed)
        # row 3: log (fixed)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)

        self._create_pipeline_nav()   # row 0, col 0-1
        self._create_sidebar()        # row 1-3, col 0
        self._create_main_area()      # row 1, col 1
        self._create_action_bar()     # row 2, col 1
        self._create_log_area()       # row 3, col 1

    def _create_action_bar(self) -> None:
        """Create fixed action bar with progress, run/reset, and status."""
        self.action_bar = ctk.CTkFrame(
            self,
            height=DIMENSIONS["action_bar_height"],
            fg_color="#0d1b2a",
        )
        self.action_bar.grid(row=2, column=1, sticky="ew")
        self.action_bar.grid_propagate(False)
        self.action_bar.grid_columnconfigure(0, weight=1)

        # Progress bar row
        self.progress_bar = ctk.CTkProgressBar(self.action_bar, height=6)
        self.progress_bar.grid(
            row=0, column=0, sticky="ew",
            padx=PADDING["large"], pady=(PADDING["small"], 0),
        )
        self.progress_bar.set(0)

        # Button + status row
        btn_row = ctk.CTkFrame(self.action_bar, fg_color="transparent")
        btn_row.grid(row=1, column=0, sticky="ew", padx=PADDING["large"], pady=(4, PADDING["small"]))
        btn_row.grid_columnconfigure(2, weight=1)

        self.run_step_btn = ctk.CTkButton(
            btn_row,
            text="▶  執行",
            command=self._run_current_step,
            width=110,
            height=30,
            font=FONTS["body"],
            fg_color=COLORS["primary"],
        )
        self.run_step_btn.grid(row=0, column=0, padx=(0, PADDING["medium"]))

        self.reset_step_btn = ctk.CTkButton(
            btn_row,
            text="↺  重置",
            command=self._reset_current_step,
            width=90,
            height=30,
            font=FONTS["body"],
            fg_color="transparent",
            border_width=1,
        )
        self.reset_step_btn.grid(row=0, column=1, padx=(0, PADDING["large"]))

        self.status_label = ctk.CTkLabel(
            btn_row,
            text="Ready",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        )
        self.status_label.grid(row=0, column=2, sticky="w")

    def _update_action_bar_progress(self, value: float, status: str = "") -> None:
        """Update Action Bar progress bar and status label."""
        self.progress_bar.set(value / 100)
        if status:
            self.status_label.configure(text=status)

    def _create_pipeline_nav(self) -> None:
        """Create the pipeline navigation bar showing overall workflow position."""
        nav_frame = ctk.CTkFrame(self, height=36, fg_color="#0d1b2a")
        nav_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        nav_frame.grid_propagate(False)

        inner = ctk.CTkFrame(nav_frame, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        steps = [
            ("Step 1: Preprocessing", True),
            ("Step 2: Normalization", False),
            ("Step 3: Statistical Analysis", False),
        ]

        for i, (label, is_current) in enumerate(steps):
            if i > 0:
                arrow = ctk.CTkLabel(
                    inner, text="  →  ",
                    font=("Consolas", 14),
                    text_color="#4a6fa5",
                )
                arrow.pack(side="left")

            fg = "#e0e0e0" if is_current else "#5a6a7a"
            bg = "#1f538d" if is_current else "transparent"
            font = (FONTS["body"][0], FONTS["body"][1], "bold") if is_current else FONTS["small"]

            step_label = ctk.CTkLabel(
                inner, text=label,
                font=font, text_color=fg,
                fg_color=bg,
                corner_radius=4,
                padx=10, pady=2,
            )
            step_label.pack(side="left")

    def _create_sidebar(self) -> None:
        """Create compact sidebar (180px) — navigation only."""
        self.sidebar = ctk.CTkFrame(self, width=DIMENSIONS["sidebar_width"])
        self.sidebar.grid(row=1, column=0, rowspan=3, sticky="nsw")
        self.sidebar.grid_propagate(False)

        # App title (compact, 2 lines)
        ctk.CTkLabel(
            self.sidebar,
            text="MS Preprocessing\nToolkit",
            font=FONTS["heading"],
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=PADDING["medium"], pady=(PADDING["large"], PADDING["small"]))

        # Separator
        ctk.CTkFrame(self.sidebar, height=1, fg_color="#2a3f5a").pack(
            fill="x", padx=PADDING["medium"], pady=(0, PADDING["small"])
        )

        # Workflow section label
        ctk.CTkLabel(
            self.sidebar,
            text="工作流程",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(fill="x", padx=PADDING["medium"], pady=(0, PADDING["small"]))

        # Step buttons with status circle
        self.step_buttons = []
        self._step_status_labels = []

        for i, (step_id, name_zh, name_en) in enumerate(Settings.WORKFLOW_STEPS):
            row_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
            row_frame.pack(fill="x", padx=PADDING["small"], pady=2)
            row_frame.grid_columnconfigure(1, weight=1)

            status_lbl = ctk.CTkLabel(
                row_frame,
                text="○",
                font=FONTS["body"],
                text_color="#4a6fa5",
                width=20,
            )
            status_lbl.grid(row=0, column=0, padx=(4, 0))
            self._step_status_labels.append(status_lbl)

            btn = ctk.CTkButton(
                row_frame,
                text=f"{i+1}. {name_zh}",
                command=lambda idx=i: self._switch_step(idx),
                anchor="w",
                height=32,
                fg_color=COLORS["primary"] if i == 0 else "transparent",
                border_width=0,
                font=FONTS["body"],
            )
            btn.grid(row=0, column=1, sticky="ew", padx=4)
            self.step_buttons.append(btn)

        # Spacer
        ctk.CTkFrame(self.sidebar, fg_color="transparent").pack(fill="both", expand=True)

        # Actions separator
        ctk.CTkFrame(self.sidebar, height=1, fg_color="#2a3f5a").pack(
            fill="x", padx=PADDING["medium"], pady=(0, PADDING["small"])
        )

        ctk.CTkLabel(
            self.sidebar,
            text="動作",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(fill="x", padx=PADDING["medium"], pady=(0, PADDING["small"]))

        # Action buttons (compact, height=32)
        action_buttons = [
            ("↑ 匯出結果", self._export_results, COLORS["secondary"]),
            ("📁 開啟資料夾", self._open_output_folder, "transparent"),
            ("⚡ 執行全部", self._run_all_steps, COLORS["accent"]),
        ]
        for text, cmd, color in action_buttons:
            ctk.CTkButton(
                self.sidebar,
                text=text,
                command=cmd,
                height=32,
                fg_color=color,
                font=FONTS["small"],
                anchor="w",
            ).pack(fill="x", padx=PADDING["medium"], pady=2)

        # DNP export button
        self.export_dnp_btn = ctk.CTkButton(
            self.sidebar,
            text="→ 匯出 DNP",
            command=self._export_to_dnp,
            height=32,
            fg_color="#6b7280",
            font=FONTS["small"],
            anchor="w",
            state="disabled",
        )
        self.export_dnp_btn.pack(
            fill="x",
            padx=PADDING["medium"],
            pady=(2, PADDING["large"]),
        )

    def _create_main_area(self) -> None:
        """Create the main content area with step widgets."""
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=0)
        self.main_frame.grid_propagate(True)

        # Create step widgets
        self.step_widgets = []

        # Step 1: Data Organizer
        self.data_organizer_widget = DataOrganizerWidget(
            self.main_frame,
            step_index=0,
            on_load_file=self._load_file_for_step,
            on_complete=self._on_step_complete,
            on_log=self._log,
            on_progress=self._update_action_bar_progress,
        )
        self.step_widgets.append(self.data_organizer_widget)

        # Step 2: ISTD Marker
        self.istd_marker_widget = ISTDMarkerWidget(
            self.main_frame,
            step_index=1,
            on_load_file=self._load_file_for_step,
            on_complete=self._on_step_complete,
            on_log=self._log,
            on_progress=self._update_action_bar_progress,
        )
        self.step_widgets.append(self.istd_marker_widget)

        # Step 3: Duplicate Remover
        self.duplicate_remover_widget = DuplicateRemoverWidget(
            self.main_frame,
            step_index=2,
            on_load_file=self._load_file_for_step,
            on_complete=self._on_step_complete,
            on_log=self._log,
            on_progress=self._update_action_bar_progress,
        )
        self.step_widgets.append(self.duplicate_remover_widget)

        # Step 4: Feature Filter
        self.feature_filter_widget = FeatureFilterWidget(
            self.main_frame,
            step_index=3,
            on_load_file=self._load_file_for_step,
            on_complete=self._on_step_complete,
            on_log=self._log,
            on_progress=self._update_action_bar_progress,
        )
        self.step_widgets.append(self.feature_filter_widget)

        # Show first step by default
        self._show_step(0)

    def _create_log_area(self) -> None:
        """Create log area — display only, no action buttons."""
        self.log_frame = ctk.CTkFrame(self, height=DIMENSIONS["log_height"])
        self.log_frame.grid(row=3, column=1, sticky="sew")
        self.log_frame.grid_propagate(False)
        self.log_frame.pack_propagate(False)

        # Header
        log_header = ctk.CTkFrame(self.log_frame, fg_color="transparent")
        log_header.pack(fill="x", padx=PADDING["medium"], pady=(PADDING["small"], 0))

        ctk.CTkLabel(
            log_header,
            text="處理紀錄",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
        ).pack(side="left")

        ctk.CTkButton(
            log_header,
            text="清除",
            command=self._clear_log,
            width=50,
            height=22,
            font=FONTS["small"],
            fg_color="transparent",
            border_width=1,
        ).pack(side="right")

        self.log_text = ctk.CTkTextbox(
            self.log_frame,
            font=FONTS["mono"],
        )
        self.log_text.pack(
            fill="both", expand=True,
            padx=PADDING["medium"],
            pady=(4, PADDING["small"]),
        )

    def _bind_shortcuts(self) -> None:
        """Bind keyboard shortcuts."""
        self.bind("<Control-o>", lambda e: self._load_file_for_step(self._current_step))
        self.bind("<Control-s>", lambda e: self._export_results())
        self.bind("<Control-1>", lambda e: self._switch_step(0))
        self.bind("<Control-2>", lambda e: self._switch_step(1))
        self.bind("<Control-3>", lambda e: self._switch_step(2))
        self.bind("<Control-4>", lambda e: self._switch_step(3))

    def _load_file_for_step(self, step_index: int, path: Optional[Path] = None) -> None:
        """Open file dialog and load data for a specific step."""
        filetypes = [
            ("Excel files", "*.xlsx *.xls"),
            ("Parquet files", "*.parquet"),
            ("CSV files", "*.csv"),
            ("TSV files", "*.tsv *.txt"),
            ("All files", "*.*"),
        ]

        filepath = None
        if path is None:
            filepath = filedialog.askopenfilename(
                title="選擇資料檔案",
                filetypes=filetypes,
            )
        else:
            filepath = str(path)

        if filepath:
            try:
                self._log(f"Loading file: {filepath}")
                df, metadata = self._file_handler.load_data(filepath)
                loaded_path = Path(filepath)

                loaded_sample_info = None
                loaded_deleted_feature = None
                if loaded_path.suffix.lower() in {".xlsx", ".xls"}:
                    try:
                        excel_book = pd.ExcelFile(loaded_path)
                        if "SampleInfo" in excel_book.sheet_names:
                            loaded_sample_info = pd.read_excel(loaded_path, sheet_name="SampleInfo")
                            self._log("Detected and loaded SampleInfo sheet.")
                        if "deleted_feature" in excel_book.sheet_names:
                            loaded_deleted_feature = pd.read_excel(loaded_path, sheet_name="deleted_feature")
                            self._log("Detected and loaded deleted_feature sheet.")
                    except Exception as exc:
                        self._log(f"Warning: could not read extra sheets from workbook: {exc}")

                self._current_data = df
                self._original_data = df.copy()
                self._source_file = loaded_path
                self._pipeline_session = PipelineSession(output_dir=self._output_dir, source_file=loaded_path)
                self._step_output_paths = self._pipeline_session.step_output_paths
                self._context = self._pipeline_session.context
                self._last_materialized_export_path = None
                self._context["red_font_rows"] = set(metadata.get("red_font_rows", []))
                self._context["protected_rows"] = set(
                    metadata.get("protected_rows") or metadata.get("red_font_rows") or []
                )
                self._context["blue_font_cells"] = []
                self._context["highlight_rows"] = set()
                self._context["sample_info"] = loaded_sample_info
                self._context["deleted_feature_df"] = loaded_deleted_feature
                self._context["metadata_refs"]["sample_info_ref"] = "SampleInfo" if loaded_sample_info is not None else None
                self._context["metadata_refs"]["deleted_feature_ref"] = (
                    "deleted_feature" if loaded_deleted_feature is not None else None
                )

                # Update input display for this step
                if 0 <= step_index < len(self.step_widgets):
                    self.step_widgets[step_index].set_input_file(filepath)
                    self.step_widgets[step_index].set_data(df)
                    self.step_widgets[step_index].set_context(self._context)

                load_fmt = metadata.get("format", "unknown")
                self._log(f"Loaded successfully: {len(df)} rows, {len(df.columns)} columns (format: {load_fmt})")

            except Exception as e:
                self._log(f"Error loading file: {str(e)}")
                self._show_error(f"載入檔案失敗:\n{str(e)}")

    def _show_error(self, message: str) -> None:
        """Show error dialog."""
        self._log(f"ERROR: {message}")
        try:
            messagebox.showerror("錯誤", message)
        except Exception:
            pass

    def _switch_step(self, step_index: int) -> None:
        """Switch to a different workflow step."""
        if step_index < 0 or step_index >= len(self.step_widgets):
            return

        self._current_step = step_index
        self._show_step(step_index)
        self.step_widgets[step_index].set_context(self._context)
        # If we have a saved output for this step, populate its input field
        if hasattr(self, "_step_output_paths") and self._step_output_paths.get(step_index):
            self.step_widgets[step_index].set_input_file(str(self._step_output_paths[step_index]))

        # 更新 sidebar 按鈕樣式 + 狀態圓圈
        for i, (btn, status_lbl) in enumerate(zip(self.step_buttons, self._step_status_labels)):
            if i == step_index:
                btn.configure(fg_color=COLORS["primary"])
                status_lbl.configure(text="→", text_color="#52b788")
            elif i in self._completed_steps:
                btn.configure(fg_color="transparent")
                status_lbl.configure(text="✓", text_color="#52b788")
            else:
                btn.configure(fg_color="transparent")
                status_lbl.configure(text="○", text_color="#4a6fa5")

    def _show_step(self, step_index: int) -> None:
        """Show the widget for a specific step."""
        for widget in self.step_widgets:
            widget.grid_forget()
        self.step_widgets[step_index].grid(
            row=0, column=0, sticky="nsew",
            padx=0, pady=0,
        )

    def _run_current_step(self) -> None:
        """Run the currently selected step."""
        if 0 <= self._current_step < len(self.step_widgets):
            self.step_widgets[self._current_step]._on_run_clicked()

    def _reset_current_step(self) -> None:
        """Reset the currently selected step."""
        if 0 <= self._current_step < len(self.step_widgets):
            self.step_widgets[self._current_step]._on_reset_clicked()

    def _on_step_complete(self, result_data: pd.DataFrame, metadata: Optional[dict] = None) -> None:
        """Handle completion of a processing step."""
        self._current_data = result_data
        if 0 <= self._current_step < len(self.step_widgets):
            self._pipeline_session.record_step_parameters(
                self._current_step,
                self.step_widgets[self._current_step].get_last_parameters(),
            )
        self._update_context_from_metadata(metadata)
        self._completed_steps.add(self._current_step)  # 追蹤已完成步驟

        # Show stats in right panel
        stats = {}
        if hasattr(self.step_widgets[self._current_step], '_last_metadata') and self.step_widgets[self._current_step]._last_metadata:
            stats = self.step_widgets[self._current_step]._last_metadata.get("statistics") or {}
        self.step_widgets[self._current_step].show_stats(stats)

        self._last_completed_step = self._current_step
        self._last_run_all = False
        self._update_export_dnp_btn()

        # Auto-save output for this step
        output_path = self._save_step_output(self._current_step, result_data)
        if output_path:
            self._step_output_paths[self._current_step] = output_path
            self.step_widgets[self._current_step].set_input_file(str(output_path))

        # Automatically pass data to next step
        next_step = self._current_step + 1
        if next_step < len(self.step_widgets):
            self.step_widgets[next_step].set_data(result_data)
            self.step_widgets[next_step].set_context(self._context)
            # Set default input for next step to this step's output file
            if output_path:
                self.step_widgets[next_step].set_input_file(str(output_path))
            self._log(f"Data passed to Step {next_step + 1}")

    def _run_all_steps(self) -> None:
        """Run all processing steps in sequence."""
        if self._current_data is None:
            self._log("Error: Please load a file first")
            return

        try:
            data = self._original_data.copy()

            for i, widget in enumerate(self.step_widgets):
                self._log(f"Running Step {i + 1}...")
                widget.set_data(data)
                widget.set_context(self._context)

                # Trigger processing (this is simplified - actual implementation would be more complex)
                params = widget.get_parameters()
                self._pipeline_session.record_step_parameters(i, params)
                data = widget.run_processing(data, **params)
                self._update_context_from_metadata(widget.get_metadata())

                self._current_data = data
                self._last_completed_step = i
                output_path = self._save_step_output(i, data)
                if output_path:
                    self._step_output_paths[i] = output_path
                    widget.set_input_file(str(output_path))
                    if i + 1 < len(self.step_widgets):
                        self.step_widgets[i + 1].set_input_file(str(output_path))
                self._log(f"Step {i + 1} completed")
                self.update_idletasks()

            self._last_run_all = True
            self._update_export_dnp_btn()
            self._log("All steps completed successfully!")

        except Exception as e:
            self._log(f"Pipeline error: {str(e)}")

    def _export_results(self) -> Optional[Path]:
        """Export the processed data and return the materialized xlsx path."""
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
            extra_sheets = {}
            sample_info = self._context.get("sample_info")
            if sample_info is not None:
                extra_sheets["SampleInfo"] = sample_info
            deleted_df = self._context.get("deleted_feature_df")
            if isinstance(deleted_df, pd.DataFrame) and not deleted_df.empty:
                extra_sheets["deleted_feature"] = deleted_df

            self._file_handler.save_data(
                self._current_data,
                filepath,
                sheet_name="RawIntensity",
                highlight_rows=self._context.get("highlight_rows"),
                blue_font_cells=self._context.get("blue_font_cells"),
                red_font_rows=self._context.get("red_font_rows"),
                extra_sheets=extra_sheets or None,
                save_parquet_cache=False,
            )
            self._last_materialized_export_path = filepath
            self._log(f"Exported to: {filepath}")
            return filepath
        except Exception as e:
            self._log(f"Export error: {str(e)}")
            return None

    def _update_export_dnp_btn(self) -> None:
        """Enable/disable the DNP export button based on pipeline completion."""
        ready = (self._last_completed_step is not None and self._last_completed_step >= 3)
        if ready:
            self.export_dnp_btn.configure(
                state="normal",
                text="匯出至 DNP →",
                fg_color="#1a73e8",
            )
        else:
            self.export_dnp_btn.configure(
                state="disabled",
                text="匯出至 DNP ⛔",
                fg_color="#6b7280",
            )

    def _export_to_dnp(self) -> None:
        """Export current results to DNP-compatible format via Adapter A."""
        # Check Step 4 (Feature Filter) completed
        if self._last_completed_step is None or self._last_completed_step < 3:
            messagebox.showwarning(
                "Not Ready",
                "Please complete Step 4 (Feature Filtering) before exporting to DNP."
            )
            return

        # First materialize a fresh xlsx source from latest state
        source_path = self._export_results()
        if source_path is None:
            messagebox.showerror("Error", "No output file found. Please export first.")
            return

        # Ask user for output location
        output_path = filedialog.asksaveasfilename(
            title="Save DNP-compatible file",
            defaultextension=".xlsx",
            initialfile=f"DNP_import_{Path(source_path).stem}.xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
        )
        if not output_path:
            return

        # Show loading state
        original_text = self.export_dnp_btn.cget("text")
        self.export_dnp_btn.configure(text="⏳ Exporting...", state="disabled")
        self.configure(cursor="wait")
        self.update_idletasks()

        try:
            # Import adapter dynamically (lives in DNP project)
            # Search common locations relative to Desktop
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
            result = convert_preprocessing_to_dnp(str(source_path), output_path)
            self._log(f"DNP export complete: {result}")
            if messagebox.askyesno(
                "Export Successful",
                f"File exported:\n{Path(result).name}\n\n"
                "Launch DNP (Data Normalization) now?"
            ):
                self._launch_dnp()
        except ImportError:
            self._log("Error: DNP adapter not found. Ensure Data_Normalization_project_v2 is available.")
            messagebox.showerror(
                "Adapter Not Found",
                "Could not find DNP adapter module.\n"
                "Ensure Data_Normalization_project_v2 project is in the expected location."
            )
        except Exception as e:
            self._log(f"DNP export error: {str(e)}")
            messagebox.showerror("Export Failed", f"Conversion error:\n{e}")
        finally:
            self.configure(cursor="")
            self.export_dnp_btn.configure(text=original_text, state="normal")
            self._update_export_dnp_btn()

    def _materialize_final_xlsx_from_latest_step(self) -> Optional[Path]:
        """Materialize final xlsx from the latest intermediate path."""
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

            extra_sheets = {}
            sample_info = self._context.get("sample_info")
            if sample_info is not None:
                extra_sheets["SampleInfo"] = sample_info
            deleted_df = self._context.get("deleted_feature_df")
            if isinstance(deleted_df, pd.DataFrame) and not deleted_df.empty:
                extra_sheets["deleted_feature"] = deleted_df

            self._file_handler.save_data(
                data,
                target_path,
                sheet_name="RawIntensity",
                highlight_rows=self._context.get("highlight_rows"),
                blue_font_cells=self._context.get("blue_font_cells"),
                red_font_rows=self._context.get("red_font_rows"),
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

    def _launch_dnp(self) -> None:
        """Launch Data Normalization Project GUI as a separate process."""
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
            "Could not find Data_Normalization_project_v2 project.\n"
            "Please launch it manually."
        )

    def _get_base_stem(self, path: Optional[Path]) -> str:
        """Normalize base stem by stripping step prefixes and timestamps."""
        import re

        if not path:
            return "output"
        stem = path.stem
        for prefix in ["STEP1_", "STEP2_", "STEP3_", "STEP4_", "ALL_"]:
            if stem.startswith(prefix):
                stem = stem[len(prefix):]
                break
        # Remove trailing timestamp (_YYYYMMDD_HHMMSS) if present
        stem = re.sub(r"_\d{8}_\d{6}$", "", stem)
        return stem

    def _save_step_output(self, step_index: int, data: pd.DataFrame) -> Optional[Path]:
        """Save step output to OUTPUT directory and return path."""
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
        except Exception as e:
            self._log(f"Auto-save error: {str(e)}")
            return None

    def _open_output_folder(self) -> None:
        """Open OUTPUT folder in file explorer (cross-platform)."""
        import platform
        import subprocess

        try:
            self._output_dir.mkdir(parents=True, exist_ok=True)
            system = platform.system()
            if system == "Windows":
                os.startfile(self._output_dir)
            elif system == "Darwin":
                subprocess.Popen(["open", str(self._output_dir)])
            else:
                subprocess.Popen(["xdg-open", str(self._output_dir)])
        except Exception as e:
            self._log(f"Open output folder error: {str(e)}")

    def _log(self, message: str) -> None:
        """Add a message to the log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"

        self.log_text.insert("end", log_entry)
        self.log_text.see("end")

    def _clear_log(self) -> None:
        """Clear the log text."""
        self.log_text.delete("1.0", "end")

    def _update_context_from_metadata(self, metadata: Optional[dict]) -> None:
        """Update shared context from processing metadata."""
        self._pipeline_session.update_context_from_metadata(metadata)
        self._context = self._pipeline_session.context


def run_app():
    """Run the application."""
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    run_app()
