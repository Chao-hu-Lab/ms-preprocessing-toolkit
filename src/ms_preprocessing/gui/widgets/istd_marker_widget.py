"""
ISTD Marker Widget - GUI for Step 2.
"""

from typing import Callable, List, Optional, Set
from tkinter import filedialog

import customtkinter as ctk
import pandas as pd

from ms_preprocessing.adapters import istd_marker as istd_marker_adapter
from ms_preprocessing.gui.styles import FONTS, PADDING
from ms_preprocessing.gui.widgets.base_widget import BaseProcessingWidget


class ISTDMarkerWidget(BaseProcessingWidget):
    """Widget for the ISTD Marking step."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        step_index: int,
        on_load_file: Optional[Callable[[int], None]] = None,
        on_complete: Optional[Callable[[pd.DataFrame], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[float, str], None]] = None,
    ):
        self._istd_features: Set[str] = set()
        super().__init__(
            parent,
            title="Step 2: ISTD 標記 (ISTD Marking)",
            description="依據 m/z 與 RT 容差比對內標特徵，可搭配 ISTD 記錄檔與日期資訊補強辨識結果。",
            step_index=step_index,
            on_load_file=on_load_file,
            on_complete=on_complete,
            on_log=on_log,
            on_progress=on_progress,
        )

    def _create_parameters(self) -> None:
        """Create parameter inputs."""
        self._configure_form_grid()

        ppm_label = ctk.CTkLabel(self.params_frame, text="m/z 容差 (ppm)", font=FONTS["body"])
        self._style_form_label(ppm_label)
        ppm_label.grid(row=0, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="e")

        self.ppm_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="20",
            font=FONTS["body"],
        )
        self._style_numeric_entry(self.ppm_entry)
        self.ppm_entry.insert(0, "20")
        self.ppm_entry.grid(row=0, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        rt_label = ctk.CTkLabel(self.params_frame, text="RT 容差 (min)", font=FONTS["body"])
        self._style_form_label(rt_label)
        rt_label.grid(row=1, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="e")

        self.rt_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="1.5",
            font=FONTS["body"],
        )
        self._style_numeric_entry(self.rt_entry)
        self.rt_entry.insert(0, "1.5")
        self.rt_entry.grid(row=1, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        istd_label = ctk.CTkLabel(self.params_frame, text="預設 ISTD m/z", font=FONTS["body"])
        self._style_form_label(istd_label)
        istd_label.grid(row=2, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="e")

        self.istd_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="例如 261.1273, 245.1324",
            width=160,
            font=FONTS["body"],
        )
        default_list = ", ".join(f"{mz:.4f}" for mz in istd_marker_adapter.get_default_istd_mz())
        self.istd_entry.insert(0, default_list)
        self.istd_entry.grid(row=2, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="ew")

        record_label = ctk.CTkLabel(self.params_frame, text="ISTD 記錄檔 (.xlsx)", font=FONTS["body"])
        self._style_form_label(record_label)
        record_label.grid(row=3, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="e")

        self.record_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="選擇 ISTD 記錄檔 (.xlsx)",
            width=160,
            font=FONTS["body"],
        )
        self.record_entry.grid(row=3, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="ew")

        self.record_btn = ctk.CTkButton(
            self.params_frame,
            text="瀏覽",
            command=self._browse_record_file,
            width=120,
            font=FONTS["body"],
        )
        self.record_btn.grid(row=3, column=2, padx=PADDING["small"], pady=PADDING["small"])

        date_label = ctk.CTkLabel(
            self.params_frame,
            text="ISTD 日期 (YYYYMMDD)",
            font=FONTS["body"],
        )
        self._style_form_label(date_label)
        date_label.grid(row=4, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="e")

        self.date_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="例如 20260106",
            font=FONTS["body"],
        )
        self._style_numeric_entry(self.date_entry)
        self.date_entry.grid(row=4, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

    def _browse_record_file(self) -> None:
        """Open file dialog to select ISTD record file."""
        filepath = filedialog.askopenfilename(
            title="選擇 ISTD 記錄檔",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")],
        )
        if filepath:
            self.record_entry.delete(0, "end")
            self.record_entry.insert(0, filepath)

    def get_parameters(self) -> dict:
        """Get current parameter values."""
        params = {
            "ppm_tolerance": float(self.ppm_entry.get() or "20"),
            "rt_tolerance": float(self.rt_entry.get() or "1.5"),
            "istd_features": set(),
            "istd_mz_list": self._parse_istd_mz_list(),
        }

        record_file = self.record_entry.get().strip()
        if record_file:
            params["istd_record_file"] = record_file
            record_date = self.date_entry.get().strip()
            if record_date:
                params["istd_record_date"] = record_date

        return params

    def apply_parameters(self, params: dict) -> None:
        """Apply a pipeline profile to the Step 2 controls."""
        if "ppm_tolerance" in params:
            self.ppm_entry.delete(0, "end")
            self.ppm_entry.insert(0, str(params["ppm_tolerance"]))

        if "rt_tolerance" in params:
            self.rt_entry.delete(0, "end")
            self.rt_entry.insert(0, str(params["rt_tolerance"]))

        if "istd_mz_list" in params:
            mz_list = params.get("istd_mz_list") or []
            self.istd_entry.delete(0, "end")
            self.istd_entry.insert(0, ", ".join(str(value) for value in mz_list))

        if "istd_record_file" in params:
            self.record_entry.delete(0, "end")
            self.record_entry.insert(0, str(params["istd_record_file"]))

        if "istd_record_date" in params:
            self.date_entry.delete(0, "end")
            self.date_entry.insert(0, str(params["istd_record_date"]))

    def _parse_istd_mz_list(self) -> List[float]:
        """Parse ISTD m/z list from entry, fallback to default."""
        istd_text = self.istd_entry.get().strip()
        if not istd_text:
            return list(istd_marker_adapter.get_default_istd_mz())
        try:
            return [float(x.strip()) for x in istd_text.split(",") if x.strip()]
        except ValueError:
            return []

    def run_processing(self, data: pd.DataFrame, **params) -> pd.DataFrame:
        """Run the ISTD marking step."""
        result = istd_marker_adapter.run_from_df(
            data,
            istd_features=params.get("istd_features", set()),
            istd_mz_list=params.get("istd_mz_list"),
            istd_record_file=params.get("istd_record_file"),
            istd_record_date=params.get("istd_record_date"),
            ppm_tolerance=params.get("ppm_tolerance", 20),
            rt_tolerance=params.get("rt_tolerance", 1.5),
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
