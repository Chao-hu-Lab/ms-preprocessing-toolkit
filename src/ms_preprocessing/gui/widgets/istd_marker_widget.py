"""
ISTD Marker Widget - GUI for Step 2.
"""

from typing import Optional, Callable, Set, List
from tkinter import filedialog
import customtkinter as ctk
import pandas as pd

from ms_preprocessing.gui.widgets.base_widget import BaseProcessingWidget
from ms_preprocessing.gui.styles import PADDING, FONTS
from ms_preprocessing.core.istd_marker import ISTDMarker


class ISTDMarkerWidget(BaseProcessingWidget):
    """Widget for the ISTD Marking step."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        step_index: int,
        on_load_file: Optional[Callable[[int], None]] = None,
        on_complete: Optional[Callable[[pd.DataFrame], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ):
        # Initialize processor before BaseProcessingWidget builds UI
        # (BaseProcessingWidget.__init__ calls _create_parameters)
        self._processor = ISTDMarker()
        self._istd_features: Set[str] = set()
        super().__init__(
            parent,
            title="Step 2: ISTD 標記 (ISTD Marking)",
            description="標記內標(ISTD)、依 m/z 排序、偵測並標記重複訊號",
            step_index=step_index,
            on_load_file=on_load_file,
            on_complete=on_complete,
            on_log=on_log,
        )

    def _create_parameters(self) -> None:
        """Create parameter inputs."""
        # PPM tolerance
        ppm_label = ctk.CTkLabel(
            self.params_frame,
            text="m/z 容差 (ppm)：",
            font=FONTS["body"],
        )
        ppm_label.grid(row=0, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        self.ppm_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="20",
            width=100,
            font=FONTS["body"],
        )
        self.ppm_entry.insert(0, "20")
        self.ppm_entry.grid(row=0, column=1, padx=PADDING["small"], pady=PADDING["small"])

        # RT tolerance
        rt_label = ctk.CTkLabel(
            self.params_frame,
            text="RT 容差 (min)：",
            font=FONTS["body"],
        )
        rt_label.grid(row=1, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        self.rt_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="1.0",
            width=100,
            font=FONTS["body"],
        )
        self.rt_entry.insert(0, "1.0")
        self.rt_entry.grid(row=1, column=1, padx=PADDING["small"], pady=PADDING["small"])

        # Known ISTD m/z values
        istd_label = ctk.CTkLabel(
            self.params_frame,
            text="已知 ISTD m/z：",
            font=FONTS["body"],
        )
        istd_label.grid(row=2, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        self.istd_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="例: 261.1273, 245.1324",
            width=200,
            font=FONTS["body"],
        )
        # Pre-fill default ISTD list
        default_list = ", ".join(f"{mz:.4f}" for mz in self._processor.config.default_istd_mz)
        self.istd_entry.insert(0, default_list)
        self.istd_entry.grid(row=2, column=1, padx=PADDING["small"], pady=PADDING["small"])

        # ISTD record file (optional)
        record_label = ctk.CTkLabel(
            self.params_frame,
            text="ISTD 記錄表 (可選)：",
            font=FONTS["body"],
        )
        record_label.grid(row=3, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        self.record_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="選擇 ISTD 記錄表 (.xlsx)",
            width=200,
            font=FONTS["body"],
        )
        self.record_entry.grid(row=3, column=1, padx=PADDING["small"], pady=PADDING["small"])

        self.record_btn = ctk.CTkButton(
            self.params_frame,
            text="選擇檔案",
            command=self._browse_record_file,
            width=120,
            font=FONTS["body"],
        )
        self.record_btn.grid(row=3, column=2, padx=PADDING["small"], pady=PADDING["small"])

        # ISTD record date
        date_label = ctk.CTkLabel(
            self.params_frame,
            text="ISTD 日期(YYYYMMDD)：",
            font=FONTS["body"],
        )
        date_label.grid(row=4, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        self.date_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="例: 20260106",
            width=120,
            font=FONTS["body"],
        )
        self.date_entry.grid(row=4, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

    def _browse_record_file(self) -> None:
        """Open file dialog to select ISTD record file."""
        filepath = filedialog.askopenfilename(
            title="選擇 ISTD 記錄表",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")],
        )
        if filepath:
            self.record_entry.delete(0, "end")
            self.record_entry.insert(0, filepath)

    def _get_parameters(self) -> dict:
        """Get current parameter values."""
        params = {
            "ppm_tolerance": float(self.ppm_entry.get() or "20"),
            "rt_tolerance": float(self.rt_entry.get() or "0.5"),
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

    def _parse_istd_mz_list(self) -> List[float]:
        """Parse ISTD m/z list from entry, fallback to default."""
        istd_text = self.istd_entry.get().strip()
        if not istd_text:
            return list(self._processor.config.default_istd_mz)
        try:
            return [float(x.strip()) for x in istd_text.split(",") if x.strip()]
        except ValueError:
            return []

    def _run_processing(self, data: pd.DataFrame, **params) -> pd.DataFrame:
        """Run the ISTD marking step."""
        self._processor.set_progress_callback(self.update_progress)

        # Update processor config
        self._processor.config.default_ppm_tolerance = params.get("ppm_tolerance", 20)
        self._processor.config.default_rt_tolerance = params.get("rt_tolerance", 1.0)

        result = self._processor.process(
            data,
            istd_features=params.get("istd_features", set()),
            istd_mz_list=params.get("istd_mz_list"),
            istd_record_file=params.get("istd_record_file"),
            istd_record_date=params.get("istd_record_date"),
        )

        if not result.success:
            raise Exception(result.message)

        self.log(f"Statistics: {result.statistics}")
        if result.metadata.get("warning"):
            self.log(f"Warning: {result.metadata.get('warning')}")
        if result.metadata.get("available_dates"):
            self.log(f"Available ISTD dates: {result.metadata.get('available_dates')}")
        self._last_metadata = result.metadata
        return result.data
