"""
ISTD Marker Widget - GUI for Step 2.
"""

from collections.abc import Callable
from tkinter import filedialog

import customtkinter as ctk
import pandas as pd

from ms_preprocessing.adapters import istd_marker as istd_marker_adapter
from ms_preprocessing.gui.styles import FONTS, PADDING
from ms_preprocessing.gui.validation import ValidationWarning, validate_step2_params
from ms_preprocessing.gui.widgets.base_widget import BaseProcessingWidget


class ISTDMarkerWidget(BaseProcessingWidget):
    """Widget for the ISTD Marking step."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        step_index: int,
        on_load_file: Callable[[int], None] | None = None,
        on_complete: Callable[[pd.DataFrame], None] | None = None,
        on_log: Callable[[str], None] | None = None,
        on_progress: Callable[[float, str], None] | None = None,
    ):
        self._istd_features: set[str] = set()
        super().__init__(
            parent,
            title="Step 2: ISTD 標記 (ISTD Marking)",
            description="使用 XIC Extractor 結果檔中的 ISTD targets，選出最符合的內標特徵列。",
            step_index=step_index,
            on_load_file=on_load_file,
            on_complete=on_complete,
            on_log=on_log,
            on_progress=on_progress,
        )

    def _create_parameters(self) -> None:
        """Create parameter inputs."""
        self._configure_form_grid()

        xic_label = ctk.CTkLabel(self.params_frame, text="XIC 結果檔 (.xlsx)", font=FONTS["body"])
        self._style_form_label(xic_label)
        xic_label.grid(row=0, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="e")

        self.xic_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="選擇 XIC Extractor 結果檔 (.xlsx)",
            width=160,
            font=FONTS["body"],
        )
        self.xic_entry.grid(row=0, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="ew")

        self.xic_btn = ctk.CTkButton(
            self.params_frame,
            text="瀏覽",
            command=self._browse_xic_results_file,
            width=120,
            font=FONTS["body"],
        )
        self.xic_btn.grid(row=0, column=2, padx=PADDING["small"], pady=PADDING["small"])

    def _browse_xic_results_file(self) -> None:
        """Open file dialog to select an XIC Extractor result workbook."""
        filepath = filedialog.askopenfilename(
            title="選擇 XIC Extractor 結果檔",
            filetypes=[("Excel workbook", "*.xlsx"), ("All files", "*.*")],
        )
        if filepath:
            self.xic_entry.delete(0, "end")
            self.xic_entry.insert(0, filepath)

    def get_parameters(self) -> dict:
        """Get current parameter values."""
        params = {
            "xic_results_file": self.xic_entry.get().strip(),
        }

        return params

    def apply_parameters(self, params: dict) -> None:
        """Apply a pipeline profile to the Step 2 controls."""
        if "xic_results_file" in params:
            self.xic_entry.delete(0, "end")
            self.xic_entry.insert(0, str(params["xic_results_file"]))

    def validate_parameters(self, params: dict) -> list[ValidationWarning]:
        return validate_step2_params(params)

    def run_processing(self, data: pd.DataFrame, **params) -> pd.DataFrame:
        """Run the ISTD marking step."""
        result = istd_marker_adapter.run_from_df(
            data,
            xic_results_file=params.get("xic_results_file"),
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
