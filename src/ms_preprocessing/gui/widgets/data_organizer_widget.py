"""
Data Organizer Widget - GUI for Step 1.
"""

import re
from tkinter import filedialog
from typing import Callable, Optional

import customtkinter as ctk
import pandas as pd

from ms_preprocessing.adapters import data_organizer as data_organizer_adapter
from ms_preprocessing.gui.styles import FONTS, PADDING
from ms_preprocessing.gui.validation import ValidationWarning, validate_step1_params
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
        on_run_combined_preprocessor: Optional[Callable[[], None]] = None,
    ):
        self._on_run_combined_preprocessor = on_run_combined_preprocessor
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

        combined_title = ctk.CTkLabel(
            self.params_frame,
            text="Combined TSV 前處理（選用）",
            font=FONTS["small"],
            text_color="#9fb8d0",
        )
        combined_title.grid(
            row=0,
            column=0,
            columnspan=3,
            padx=PADDING["small"],
            pady=(PADDING["small"], 2),
            sticky="w",
        )

        combined_tsv_label = ctk.CTkLabel(
            self.params_frame,
            text="Combined TSV",
            font=FONTS["body"],
        )
        self._style_form_label(combined_tsv_label)
        combined_tsv_label.grid(
            row=1,
            column=0,
            padx=PADDING["small"],
            pady=PADDING["small"],
            sticky="e",
        )

        self.combined_tsv_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="選擇 raw combined TSV",
            font=FONTS["body"],
        )
        self.combined_tsv_entry.grid(
            row=1,
            column=1,
            padx=PADDING["small"],
            pady=PADDING["small"],
            sticky="ew",
        )

        self.combined_tsv_btn = ctk.CTkButton(
            self.params_frame,
            text="瀏覽",
            command=self._browse_combined_tsv_file,
            width=90,
            font=FONTS["body"],
        )
        self.combined_tsv_btn.grid(row=1, column=2, padx=PADDING["small"], pady=PADDING["small"])

        combined_method_label = ctk.CTkLabel(
            self.params_frame,
            text="前處理方法檔",
            font=FONTS["body"],
        )
        self._style_form_label(combined_method_label)
        combined_method_label.grid(
            row=2,
            column=0,
            padx=PADDING["small"],
            pady=PADDING["small"],
            sticky="e",
        )

        self.combined_method_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="選擇 combined TSV 使用的方法檔",
            font=FONTS["body"],
        )
        self.combined_method_entry.grid(
            row=2,
            column=1,
            padx=PADDING["small"],
            pady=PADDING["small"],
            sticky="ew",
        )

        self.combined_method_btn = ctk.CTkButton(
            self.params_frame,
            text="瀏覽",
            command=self._browse_combined_method_file,
            width=90,
            font=FONTS["body"],
        )
        self.combined_method_btn.grid(row=2, column=2, padx=PADDING["small"], pady=PADDING["small"])

        self.combined_run_btn = ctk.CTkButton(
            self.params_frame,
            text="產生 combined_fix",
            command=self._run_combined_preprocessor,
            font=FONTS["body"],
        )
        self.combined_run_btn.grid(
            row=3,
            column=1,
            padx=PADDING["small"],
            pady=(PADDING["small"], PADDING["medium"]),
            sticky="w",
        )

        normal_title = ctk.CTkLabel(
            self.params_frame,
            text="一般 Toolkit 流程",
            font=FONTS["small"],
            text_color="#9fb8d0",
        )
        normal_title.grid(
            row=4,
            column=0,
            columnspan=3,
            padx=PADDING["small"],
            pady=(PADDING["small"], 2),
            sticky="w",
        )

        method_label = ctk.CTkLabel(self.params_frame, text="方法檔案 (.docx)", font=FONTS["body"])
        self._style_form_label(method_label)
        method_label.grid(row=5, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="e")

        self.method_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="選填方法檔案 (.docx)",
            font=FONTS["body"],
        )
        self.method_entry.grid(row=5, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="ew")

        self.method_btn = ctk.CTkButton(
            self.params_frame,
            text="瀏覽",
            command=self._browse_method_file,
            width=90,
            font=FONTS["body"],
        )
        self.method_btn.grid(row=5, column=2, padx=PADDING["small"], pady=PADDING["small"])

    def _set_entry_value(self, entry: ctk.CTkEntry, value: str) -> None:
        entry.delete(0, "end")
        entry.insert(0, value)

    def _browse_combined_tsv_file(self) -> None:
        filepath = filedialog.askopenfilename(
            title="選擇 combined TSV",
            filetypes=[("TSV files", "*.tsv *.txt"), ("All files", "*.*")],
        )
        if filepath:
            self._set_entry_value(self.combined_tsv_entry, filepath)

    def _browse_combined_method_file(self) -> None:
        filepath = filedialog.askopenfilename(
            title="選擇 combined TSV 方法檔案",
            filetypes=[("Word files", "*.docx *.doc"), ("All files", "*.*")],
        )
        if filepath:
            self._set_entry_value(self.combined_method_entry, filepath)
            self.prefill_normal_method_from_combined()

    def _run_combined_preprocessor(self) -> None:
        if self._on_run_combined_preprocessor is not None:
            self._on_run_combined_preprocessor()

    def _browse_method_file(self) -> None:
        """Open file dialog to select method file."""
        filepath = filedialog.askopenfilename(
            title="選擇方法檔案",
            filetypes=[("Word files", "*.docx *.doc"), ("All files", "*.*")],
        )
        if filepath:
            self._set_entry_value(self.method_entry, filepath)

    def get_combined_preprocessor_paths(self) -> dict:
        """Return paths selected for the optional combined TSV preprocessor."""
        return {
            "combined_tsv": self.combined_tsv_entry.get().strip(),
            "method_file": self.combined_method_entry.get().strip(),
        }

    def prefill_normal_method_from_combined(self) -> None:
        method_file = self.combined_method_entry.get().strip()
        if method_file:
            self._set_entry_value(self.method_entry, method_file)

    def get_parameters(self) -> dict:
        """Get current parameter values."""
        params = {
            "mode": "normalization",
            "auto_detect": True,
        }

        method_file = self.method_entry.get().strip()
        if not method_file:
            method_file = self.combined_method_entry.get().strip()
        if method_file:
            params["method_file"] = method_file

        return params

    def apply_parameters(self, params: dict) -> None:
        """Apply a pipeline profile to the Step 1 controls."""
        method_file = params.get("method_file")
        if method_file is not None:
            self._set_entry_value(self.method_entry, str(method_file))

    def validate_parameters(self, params: dict) -> list[ValidationWarning]:
        return validate_step1_params(params)

    def _looks_like_raw_combined_tsv(self, df: pd.DataFrame) -> bool:
        for idx, col in enumerate(df.columns):
            compact = re.sub(r"[^a-z0-9]+", "", str(col).strip().lower())
            if compact == "mzmineid":
                return 2 < idx < len(df.columns) - 1
        return False

    def run_processing(self, data: pd.DataFrame, **params) -> pd.DataFrame:
        """Run the data organization step."""
        if self._looks_like_raw_combined_tsv(data):
            raise Exception(
                "偵測到 raw combined TSV。請先在「Combined TSV 前處理」選擇 TSV 與方法檔，"
                "按「產生 combined_fix」，再用產出的 .xlsx 跑一般 Toolkit 流程。"
            )

        result = data_organizer_adapter.run_from_df(
            data,
            mode="normalization",
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
