"""
Duplicate Remover Widget - GUI for Step 3.
"""

from typing import Callable, Optional

import customtkinter as ctk
import pandas as pd

from ms_preprocessing.adapters import duplicate_remover as duplicate_remover_adapter
from ms_preprocessing.gui.styles import FONTS, PADDING
from ms_preprocessing.gui.widgets.base_widget import BaseProcessingWidget


class DuplicateRemoverWidget(BaseProcessingWidget):
    """Widget for the Duplicate Removal step."""

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
            title="Step 3: 重複訊號刪除 (Duplicate Removal)",
            description="依 m/z 與 RT 容差比對重複特徵，保留代表性訊號並移除冗餘峰值。",
            step_index=step_index,
            on_load_file=on_load_file,
            on_complete=on_complete,
            on_log=on_log,
            on_progress=on_progress,
        )

    def _create_parameters(self) -> None:
        """Create parameter inputs."""
        self._configure_form_grid()

        mz_label = ctk.CTkLabel(self.params_frame, text="m/z 容差 (ppm)", font=FONTS["body"])
        self._style_form_label(mz_label)
        mz_label.grid(row=0, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="e")

        self.mz_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="20",
            font=FONTS["body"],
        )
        self._style_numeric_entry(self.mz_entry)
        self.mz_entry.insert(0, "20")
        self.mz_entry.grid(row=0, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        rt_label = ctk.CTkLabel(self.params_frame, text="RT 容差 (min)", font=FONTS["body"])
        self._style_form_label(rt_label)
        rt_label.grid(row=1, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="e")

        self.rt_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="1.0",
            font=FONTS["body"],
        )
        self._style_numeric_entry(self.rt_entry)
        self.rt_entry.insert(0, "1.0")
        self.rt_entry.grid(row=1, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        topn_label = ctk.CTkLabel(self.params_frame, text="保留前 Top N", font=FONTS["body"])
        self._style_form_label(topn_label)
        topn_label.grid(row=2, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="e")

        self.topn_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="留空表示全部保留",
            font=FONTS["body"],
        )
        self._style_numeric_entry(self.topn_entry)
        self.topn_entry.grid(row=2, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

    def get_parameters(self) -> dict:
        """Get current parameter values."""
        params = {
            "mz_tolerance_ppm": float(self.mz_entry.get() or "20"),
            "rt_tolerance": float(self.rt_entry.get() or "1.0"),
            "preserve_red_font": True,
        }

        topn_text = self.topn_entry.get().strip()
        if topn_text:
            try:
                params["top_n"] = int(topn_text)
            except ValueError:
                pass

        return params

    def apply_parameters(self, params: dict) -> None:
        """Apply a pipeline profile to the Step 3 controls."""
        if "mz_tolerance_ppm" in params:
            self.mz_entry.delete(0, "end")
            self.mz_entry.insert(0, str(params["mz_tolerance_ppm"]))

        if "rt_tolerance" in params:
            self.rt_entry.delete(0, "end")
            self.rt_entry.insert(0, str(params["rt_tolerance"]))

        top_n = params.get("top_n")
        self.topn_entry.delete(0, "end")
        if top_n is not None:
            self.topn_entry.insert(0, str(top_n))

    def run_processing(self, data: pd.DataFrame, **params) -> pd.DataFrame:
        """Run the duplicate removal step."""
        protected_rows = set(
            self._context.get("protected_rows") or self._context.get("red_font_rows") or []
        )

        result = duplicate_remover_adapter.run_from_df(
            data,
            mz_tolerance_ppm=params.get("mz_tolerance_ppm"),
            rt_tolerance=params.get("rt_tolerance"),
            top_n=params.get("top_n"),
            protected_rows=protected_rows,
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
