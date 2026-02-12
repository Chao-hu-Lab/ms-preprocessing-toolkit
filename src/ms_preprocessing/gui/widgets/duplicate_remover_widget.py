"""
Duplicate Remover Widget - GUI for Step 3.
"""

from typing import Optional, Callable
import customtkinter as ctk
import pandas as pd

from ms_preprocessing.gui.widgets.base_widget import BaseProcessingWidget
from ms_preprocessing.gui.styles import PADDING, FONTS
from ms_preprocessing.core.duplicate_remover import DuplicateRemover


class DuplicateRemoverWidget(BaseProcessingWidget):
    """Widget for the Duplicate Removal step."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        step_index: int,
        on_load_file: Optional[Callable[[int], None]] = None,
        on_complete: Optional[Callable[[pd.DataFrame], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(
            parent,
            title="Step 3: 重複訊號刪除 (Duplicate Removal)",
            description="基於 m/z 和 RT 容差智慧識別並移除重複訊號，保留最高強度",
            step_index=step_index,
            on_load_file=on_load_file,
            on_complete=on_complete,
            on_log=on_log,
        )
        self._processor = DuplicateRemover()

    def _create_parameters(self) -> None:
        """Create parameter inputs."""
        # m/z tolerance
        mz_label = ctk.CTkLabel(
            self.params_frame,
            text="m/z 容差 (ppm)：",
            font=FONTS["body"],
        )
        mz_label.grid(row=0, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        self.mz_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="20",
            width=100,
            font=FONTS["body"],
        )
        self.mz_entry.insert(0, "20")
        self.mz_entry.grid(row=0, column=1, padx=PADDING["small"], pady=PADDING["small"])

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

        # Top N limit
        topn_label = ctk.CTkLabel(
            self.params_frame,
            text="輸出前 N 個訊號：",
            font=FONTS["body"],
        )
        topn_label.grid(row=2, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        self.topn_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="留空表示全部",
            width=100,
            font=FONTS["body"],
        )
        self.topn_entry.grid(row=2, column=1, padx=PADDING["small"], pady=PADDING["small"])

        # Preserve red font option
        self.preserve_red_var = ctk.BooleanVar(value=True)
        preserve_cb = ctk.CTkCheckBox(
            self.params_frame,
            text="保護內標(ISTD)標記列",
            variable=self.preserve_red_var,
            font=FONTS["body"],
        )
        preserve_cb.grid(row=3, column=0, columnspan=2, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

    def get_parameters(self) -> dict:
        """Get current parameter values."""
        params = {
            "mz_tolerance_ppm": float(self.mz_entry.get() or "20"),
            "rt_tolerance": float(self.rt_entry.get() or "1.0"),
            "preserve_red_font": self.preserve_red_var.get(),
        }

        topn_text = self.topn_entry.get().strip()
        if topn_text:
            try:
                params["top_n"] = int(topn_text)
            except ValueError:
                pass

        return params

    def run_processing(self, data: pd.DataFrame, **params) -> pd.DataFrame:
        """Run the duplicate removal step."""
        self._processor.set_progress_callback(self.update_progress)

        protected_rows = set()
        if params.get("preserve_red_font", True):
            protected_rows = set(
                self._context.get("protected_rows") or self._context.get("red_font_rows") or []
            )

        result = self._processor.process(
            data,
            mz_tolerance_ppm=params.get("mz_tolerance_ppm"),
            rt_tolerance=params.get("rt_tolerance"),
            top_n=params.get("top_n"),
            protected_rows=protected_rows,
        )

        if not result.success:
            raise Exception(result.message)

        self.log(f"Statistics: {result.statistics}")
        self._last_metadata = result.metadata
        return result.data
