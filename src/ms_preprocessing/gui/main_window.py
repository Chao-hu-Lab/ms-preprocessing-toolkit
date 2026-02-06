"""
Main Window for MS Preprocessing Toolkit GUI.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
import threading

import customtkinter as ctk
from tkinter import filedialog, messagebox
import pandas as pd

from ms_preprocessing.gui.styles import COLORS, FONTS, PADDING, DIMENSIONS
from ms_preprocessing.gui.widgets.data_organizer_widget import DataOrganizerWidget
from ms_preprocessing.gui.widgets.istd_marker_widget import ISTDMarkerWidget
from ms_preprocessing.gui.widgets.duplicate_remover_widget import DuplicateRemoverWidget
from ms_preprocessing.gui.widgets.feature_filter_widget import FeatureFilterWidget
from ms_preprocessing.utils.file_handler import FileHandler
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
        self.minsize(900, 600)

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
        self._context = {
            "red_font_rows": set(),
            "protected_rows": set(),
            "blue_font_cells": [],
            "highlight_rows": set(),
            "sample_info": None,
        }

        # Create layout
        self._create_layout()

        # Bind keyboard shortcuts
        self._bind_shortcuts()

    def _create_layout(self) -> None:
        """Create the main window layout."""
        # Configure grid
        self.grid_columnconfigure(1, weight=1)
        # Let the main content take its natural height; log expands instead
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        # Sidebar
        self._create_sidebar()

        # Main content area
        self._create_main_area()

        # Bottom log area
        self._create_log_area()

    def _create_sidebar(self) -> None:
        """Create the left sidebar with workflow steps."""
        self.sidebar = ctk.CTkFrame(self, width=DIMENSIONS["sidebar_width"])
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=0, pady=0)
        self.sidebar.grid_propagate(False)

        # Logo/Title
        title_label = ctk.CTkLabel(
            self.sidebar,
            text="MS Preprocessing Toolkit",
            font=FONTS["title"],
        )
        title_label.pack(pady=PADDING["medium"])

        # File section
        file_frame = ctk.CTkFrame(self.sidebar)
        file_frame.pack(fill="x", padx=PADDING["small"], pady=PADDING["medium"])

        self.load_btn = ctk.CTkButton(
            file_frame,
            text="載入檔案",
            command=self._load_file,
            width=180,
            font=FONTS["body"],
        )
        self.load_btn.pack(pady=PADDING["small"])

        self.file_label = ctk.CTkLabel(
            file_frame,
            text="未載入檔案",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            wraplength=180,
        )
        self.file_label.pack(pady=PADDING["small"])

        # Workflow steps
        steps_label = ctk.CTkLabel(
            self.sidebar,
            text="工作流程 Workflow",
            font=FONTS["heading"],
        )
        steps_label.pack(pady=(PADDING["medium"], PADDING["small"]))

        self.step_buttons = []
        for i, (step_id, name_zh, name_en) in enumerate(Settings.WORKFLOW_STEPS):
            btn = ctk.CTkButton(
                self.sidebar,
                text=f"{i+1}. {name_zh}",
                command=lambda idx=i: self._switch_step(idx),
                width=180,
                fg_color="transparent" if i != 0 else None,
                border_width=1,
                font=FONTS["body"],
            )
            btn.pack(pady=PADDING["small"])
            self.step_buttons.append(btn)

        # Spacer
        spacer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        # Export section
        export_frame = ctk.CTkFrame(self.sidebar)
        export_frame.pack(fill="x", padx=PADDING["small"], pady=PADDING["medium"])

        self.export_btn = ctk.CTkButton(
            export_frame,
            text="匯出結果",
            command=self._export_results,
            width=180,
            fg_color=COLORS["secondary"],
            font=FONTS["body"],
        )
        self.export_btn.pack(pady=PADDING["small"])

        self.open_output_btn = ctk.CTkButton(
            export_frame,
            text="開啟輸出資料夾",
            command=self._open_output_folder,
            width=180,
            font=FONTS["body"],
        )
        self.open_output_btn.pack(pady=PADDING["small"])

        # Run all button
        self.run_all_btn = ctk.CTkButton(
            export_frame,
            text="執行全部流程",
            command=self._run_all_steps,
            width=180,
            fg_color=COLORS["accent"],
            font=FONTS["body"],
        )
        self.run_all_btn.pack(pady=PADDING["small"])

    def _create_main_area(self) -> None:
        """Create the main content area with step widgets."""
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=0)
        self.main_frame.grid_propagate(True)

        # Create step widgets
        self.step_widgets = []

        # Step 1: Data Organizer
        self.data_organizer_widget = DataOrganizerWidget(
            self.main_frame,
            on_complete=self._on_step_complete,
            on_log=self._log,
        )
        self.step_widgets.append(self.data_organizer_widget)

        # Step 2: ISTD Marker
        self.istd_marker_widget = ISTDMarkerWidget(
            self.main_frame,
            on_complete=self._on_step_complete,
            on_log=self._log,
        )
        self.step_widgets.append(self.istd_marker_widget)

        # Step 3: Duplicate Remover
        self.duplicate_remover_widget = DuplicateRemoverWidget(
            self.main_frame,
            on_complete=self._on_step_complete,
            on_log=self._log,
        )
        self.step_widgets.append(self.duplicate_remover_widget)

        # Step 4: Feature Filter
        self.feature_filter_widget = FeatureFilterWidget(
            self.main_frame,
            on_complete=self._on_step_complete,
            on_log=self._log,
        )
        self.step_widgets.append(self.feature_filter_widget)

        # Show first step by default
        self._show_step(0)

    def _create_log_area(self) -> None:
        """Create the bottom log/status area."""
        self.log_frame = ctk.CTkFrame(self, height=DIMENSIONS["log_height"])
        self.log_frame.grid(row=1, column=1, sticky="sew", padx=0, pady=0)
        self.log_frame.grid_propagate(False)

        # Control + Log header
        log_header = ctk.CTkFrame(self.log_frame, fg_color="transparent")
        log_header.pack(fill="x", padx=PADDING["small"], pady=PADDING["small"])
        log_header.grid_columnconfigure(0, weight=1)
        log_header.grid_columnconfigure(1, weight=0)
        log_header.grid_columnconfigure(2, weight=1)

        log_label = ctk.CTkLabel(
            log_header,
            text="處理紀錄 Log",
            font=FONTS["body"],
        )
        log_label.grid(row=0, column=0, sticky="w")

        # Run/Reset buttons (centered above log)
        control_frame = ctk.CTkFrame(log_header, fg_color="transparent")
        control_frame.grid(row=0, column=1)
        self.run_step_btn = ctk.CTkButton(
            control_frame,
            text="執行 Run",
            command=self._run_current_step,
            width=120,
            font=FONTS["body"],
        )
        self.run_step_btn.pack(side="left", padx=(0, PADDING["small"]))

        self.reset_step_btn = ctk.CTkButton(
            control_frame,
            text="重置 Reset",
            command=self._reset_current_step,
            width=120,
            fg_color=COLORS["text_secondary"],
            font=FONTS["body"],
        )
        self.reset_step_btn.pack(side="left")

        clear_btn = ctk.CTkButton(
            log_header,
            text="清除",
            command=self._clear_log,
            width=60,
            height=24,
            font=FONTS["small"],
        )
        clear_btn.grid(row=0, column=2, sticky="e")

        # Log text area
        self.log_text = ctk.CTkTextbox(
            self.log_frame,
            font=FONTS["mono"],
            height=100,
        )
        self.log_text.pack(fill="both", expand=True, padx=PADDING["small"], pady=(0, PADDING["small"]))

    def _bind_shortcuts(self) -> None:
        """Bind keyboard shortcuts."""
        self.bind("<Control-o>", lambda e: self._load_file())
        self.bind("<Control-s>", lambda e: self._export_results())
        self.bind("<Control-1>", lambda e: self._switch_step(0))
        self.bind("<Control-2>", lambda e: self._switch_step(1))
        self.bind("<Control-3>", lambda e: self._switch_step(2))
        self.bind("<Control-4>", lambda e: self._switch_step(3))

    def _load_file(self) -> None:
        """Open file dialog and load data."""
        filetypes = [
            ("Excel files", "*.xlsx *.xls"),
            ("CSV files", "*.csv"),
            ("TSV files", "*.tsv *.txt"),
            ("All files", "*.*"),
        ]

        filepath = filedialog.askopenfilename(
            title="選擇資料檔案",
            filetypes=filetypes,
        )

        if filepath:
            try:
                self._log(f"Loading file: {filepath}")
                df, metadata = self._file_handler.load_data(filepath)

                self._current_data = df
                self._original_data = df.copy()
                self._source_file = Path(filepath)
                self._context["red_font_rows"] = set(metadata.get("red_font_rows", []))
                self._context["protected_rows"] = set(
                    metadata.get("protected_rows") or metadata.get("red_font_rows") or []
                )
                self._context["blue_font_cells"] = []
                self._context["highlight_rows"] = set()
                self._context["sample_info"] = None

                # Update file label
                filename = Path(filepath).name
                self.file_label.configure(text=f"{filename}\n({len(df)} rows, {len(df.columns)} cols)")

                # Set data for first step
                self.step_widgets[0].set_data(df)
                self.step_widgets[0].set_context(self._context)

                self._log(f"Loaded successfully: {len(df)} rows, {len(df.columns)} columns")

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

        # Update sidebar button styles
        for i, btn in enumerate(self.step_buttons):
            if i == step_index:
                btn.configure(fg_color=COLORS["primary"])
            else:
                btn.configure(fg_color="transparent")

    def _show_step(self, step_index: int) -> None:
        """Show the widget for a specific step."""
        # Hide all widgets
        for widget in self.step_widgets:
            widget.pack_forget()

        # Show selected widget
        self.step_widgets[step_index].pack(fill="x", expand=False, padx=0, pady=0)

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
        self._update_context_from_metadata(metadata)
        self._last_completed_step = self._current_step
        self._last_run_all = False

        # Automatically pass data to next step
        next_step = self._current_step + 1
        if next_step < len(self.step_widgets):
            self.step_widgets[next_step].set_data(result_data)
            self.step_widgets[next_step].set_context(self._context)
            self._log(f"Data passed to Step {next_step + 1}")

    def _run_all_steps(self) -> None:
        """Run all processing steps in sequence."""
        if self._current_data is None:
            self._log("Error: Please load a file first")
            return

        def run_pipeline():
            try:
                data = self._original_data.copy()

                for i, widget in enumerate(self.step_widgets):
                    self._log(f"Running Step {i + 1}...")
                    widget.set_data(data)
                    widget.set_context(self._context)

                    # Trigger processing (this is simplified - actual implementation would be more complex)
                    params = widget._get_parameters()
                    data = widget._run_processing(data, **params)
                    self._update_context_from_metadata(widget.get_metadata())

                    self._current_data = data
                    self._last_completed_step = i
                    self._log(f"Step {i + 1} completed")

                self._last_run_all = True
                self._log("All steps completed successfully!")

            except Exception as e:
                self._log(f"Pipeline error: {str(e)}")

        # Run in thread to keep UI responsive
        thread = threading.Thread(target=run_pipeline)
        thread.start()

    def _export_results(self) -> None:
        """Export the processed data."""
        if self._current_data is None:
            self._log("Error: No data to export")
            return

        output_dir = self._output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        step_prefix = None
        if self._last_run_all:
            step_prefix = "ALL"
        elif self._last_completed_step is not None:
            step_prefix = f"STEP{self._last_completed_step + 1}"
        else:
            step_prefix = f"STEP{self._current_step + 1}"

        stem = self._source_file.stem if self._source_file else "output"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if step_prefix == "ALL":
            filename = f"{step_prefix}_{stem}.xlsx"
            filepath = output_dir / filename
            if filepath.exists():
                filename = f"{step_prefix}_{stem}_{timestamp}.xlsx"
                filepath = output_dir / filename
        else:
            filename = f"{step_prefix}_{stem}_{timestamp}.xlsx"
            filepath = output_dir / filename

        try:
            self._file_handler.save_data(
                self._current_data,
                filepath,
                sheet_name="RawIntensity",
                highlight_rows=self._context.get("highlight_rows"),
                blue_font_cells=self._context.get("blue_font_cells"),
                red_font_rows=self._context.get("red_font_rows"),
                extra_sheets={"SampleInfo": self._context.get("sample_info")},
            )
            self._log(f"Exported to: {filepath}")
        except Exception as e:
            self._log(f"Export error: {str(e)}")

    def _open_output_folder(self) -> None:
        """Open OUTPUT folder in file explorer."""
        try:
            self._output_dir.mkdir(parents=True, exist_ok=True)
            os.startfile(self._output_dir)
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
        if not metadata:
            return
        if "red_font_rows" in metadata:
            self._context["red_font_rows"] = set(metadata.get("red_font_rows") or [])
        if "protected_rows" in metadata:
            self._context["protected_rows"] = set(metadata.get("protected_rows") or [])
        elif "red_font_rows" in metadata:
            self._context["protected_rows"] = set(metadata.get("red_font_rows") or [])
        if "sample_info" in metadata:
            self._context["sample_info"] = metadata.get("sample_info")
        if "blue_font_cells" in metadata:
            self._context["blue_font_cells"] = metadata.get("blue_font_cells") or []
        if "highlight_rows" in metadata:
            self._context["highlight_rows"] = set(metadata.get("highlight_rows") or [])


def run_app():
    """Run the application."""
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    run_app()
