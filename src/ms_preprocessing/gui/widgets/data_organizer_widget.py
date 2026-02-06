"""
Data Organizer Widget - GUI for Step 1.
"""

from typing import Optional, Callable, Dict
from tkinter import filedialog
import customtkinter as ctk
import pandas as pd

from ms_preprocessing.gui.widgets.base_widget import BaseProcessingWidget
from ms_preprocessing.gui.styles import PADDING, FONTS
from ms_preprocessing.core.data_organizer import DataOrganizer


class DataOrganizerWidget(BaseProcessingWidget):
    """Widget for the Data Organization step."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        on_complete: Optional[Callable[[pd.DataFrame], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(
            parent,
            title="Step 1: 資料整理 (Data Organization)",
            description="標準化資料結構、設定欄位名稱、建立 Sample Type 列",
            on_complete=on_complete,
            on_log=on_log,
        )
        self._processor = DataOrganizer()

    def _create_parameters(self) -> None:
        """Create parameter inputs."""
        # Sample type detection patterns
        pattern_label = ctk.CTkLabel(
            self.params_frame,
            text="Sample Type 偵測模式：",
            font=FONTS["body"],
        )
        pattern_label.grid(row=0, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        self.auto_detect_var = ctk.BooleanVar(value=True)
        auto_detect_cb = ctk.CTkCheckBox(
            self.params_frame,
            text="自動偵測 Sample Type",
            variable=self.auto_detect_var,
            font=FONTS["body"],
        )
        auto_detect_cb.grid(row=0, column=1, padx=PADDING["small"], pady=PADDING["small"])

        # Method file selection (optional)
        method_label = ctk.CTkLabel(
            self.params_frame,
            text="Method 檔案 (docx，可選)：",
            font=FONTS["body"],
        )
        method_label.grid(row=1, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        self.method_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="選擇上機順序文件 (.docx)",
            width=220,
            font=FONTS["body"],
        )
        self.method_entry.grid(row=1, column=1, padx=PADDING["small"], pady=PADDING["small"])

        self.method_btn = ctk.CTkButton(
            self.params_frame,
            text="選擇檔案",
            command=self._browse_method_file,
            width=90,
            font=FONTS["body"],
        )
        self.method_btn.grid(row=1, column=2, padx=PADDING["small"], pady=PADDING["small"])

    def _browse_method_file(self) -> None:
        """Open file dialog to select method file."""
        filepath = filedialog.askopenfilename(
            title="選擇上機順序文件",
            filetypes=[("Word files", "*.docx *.doc"), ("All files", "*.*")],
        )
        if filepath:
            self.method_entry.delete(0, "end")
            self.method_entry.insert(0, filepath)

    def _get_parameters(self) -> dict:
        """Get current parameter values."""
        params = {
            "auto_detect": self.auto_detect_var.get(),
        }

        method_file = self.method_entry.get().strip()
        if method_file:
            params["method_file"] = method_file

        return params

    def _run_processing(self, data: pd.DataFrame, **params) -> pd.DataFrame:
        """Run the data organization step."""
        self._processor.set_progress_callback(self.update_progress)

        sample_type_mapping = params.get("sample_type_mapping")
        if params.get("auto_detect", True) and not sample_type_mapping:
            # Auto-detect sample types from column names
            sample_type_mapping = self._processor.auto_detect_sample_types(
                list(data.columns[2:])
            )

        result = self._processor.process(
            data,
            sample_type_mapping=sample_type_mapping,
            method_file=params.get("method_file"),
        )

        if not result.success:
            raise Exception(result.message)

        self.log(f"Statistics: {result.statistics}")
        self._last_metadata = result.metadata
        return result.data
