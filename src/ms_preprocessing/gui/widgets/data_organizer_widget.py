"""
Data Organizer Widget - GUI for Step 1.
"""

from typing import Callable, Optional
from tkinter import filedialog

import customtkinter as ctk
import pandas as pd

from ms_preprocessing.adapters import data_organizer as data_organizer_adapter
from ms_preprocessing.gui.styles import FONTS, PADDING
from ms_preprocessing.gui.widgets.base_widget import BaseProcessingWidget


class DataOrganizerWidget(BaseProcessingWidget):
    """Widget for the Data Organization step."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        step_index: int,
        on_load_file: Optional[Callable[[int], None]] = None,
        on_complete: Optional[Callable[[pd.DataFrame], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[float, str], None]] = None,
    ):
        super().__init__(
            parent,
            title="Step 1: 資料整理 (Data Organization)",
            description="整理原始表格欄位與樣本資訊，建立後續正規化或統計分析可直接使用的輸入格式。",
            step_index=step_index,
            on_load_file=on_load_file,
            on_complete=on_complete,
            on_log=on_log,
            on_progress=on_progress,
        )

    def _create_parameters(self) -> None:
        """Create parameter inputs."""
        self._configure_form_grid()

        mode_label = ctk.CTkLabel(self.params_frame, text="轉換模式", font=FONTS["body"])
        self._style_form_label(mode_label)
        mode_label.grid(row=0, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="e")

        self.mode_var = ctk.StringVar(value="normalization")
        self.mode_selector = ctk.CTkSegmentedButton(
            self.params_frame,
            values=["normalization", "statistics"],
            variable=self.mode_var,
            font=FONTS["body"],
        )
        self.mode_selector.grid(
            row=0,
            column=1,
            columnspan=2,
            padx=PADDING["small"],
            pady=PADDING["small"],
            sticky="w",
        )

        method_label = ctk.CTkLabel(self.params_frame, text="方法檔案 (.docx)", font=FONTS["body"])
        self._style_form_label(method_label)
        method_label.grid(row=1, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="e")

        self.method_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="選填方法檔案 (.docx)",
            font=FONTS["body"],
        )
        self.method_entry.grid(row=1, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="ew")

        self.method_btn = ctk.CTkButton(
            self.params_frame,
            text="瀏覽",
            command=self._browse_method_file,
            width=90,
            font=FONTS["body"],
        )
        self.method_btn.grid(row=1, column=2, padx=PADDING["small"], pady=PADDING["small"])

    def _browse_method_file(self) -> None:
        """Open file dialog to select method file."""
        filepath = filedialog.askopenfilename(
            title="選擇方法檔案",
            filetypes=[("Word files", "*.docx *.doc"), ("All files", "*.*")],
        )
        if filepath:
            self.method_entry.delete(0, "end")
            self.method_entry.insert(0, filepath)

    def get_parameters(self) -> dict:
        """Get current parameter values."""
        params = {
            "mode": self.mode_var.get(),
            "auto_detect": True,
        }

        method_file = self.method_entry.get().strip()
        if method_file:
            params["method_file"] = method_file

        return params

    def apply_parameters(self, params: dict) -> None:
        """Apply a pipeline profile to the Step 1 controls."""
        mode = params.get("mode")
        if mode in {"normalization", "statistics"}:
            self.mode_var.set(mode)

        method_file = params.get("method_file")
        if method_file is not None:
            self.method_entry.delete(0, "end")
            self.method_entry.insert(0, str(method_file))

    def run_processing(self, data: pd.DataFrame, **params) -> pd.DataFrame:
        """Run the data organization step."""
        result = data_organizer_adapter.run_from_df(
            data,
            mode=params.get("mode", "normalization"),
            sample_type_mapping=params.get("sample_type_mapping"),
            auto_detect=True,
            method_file=params.get("method_file"),
            progress_callback=self.update_progress,
        )

        if not result.success:
            raise Exception(result.error or "Processing failed")

        self._processing_result = result
        if result.statistics:
            self.log(f"Statistics: {result.statistics}")
        self._last_metadata = {
            **result.metadata.as_context_dict(),
            "statistics": dict(result.statistics),
        }
        if result.data is None:
            raise Exception("Adapter returned no data")
        return result.data
