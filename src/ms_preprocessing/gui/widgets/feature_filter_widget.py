"""
Feature Filter Widget - GUI for Step 4.
"""

from typing import Optional, Callable
import customtkinter as ctk
import pandas as pd

from ms_preprocessing.gui.widgets.base_widget import BaseProcessingWidget
from ms_preprocessing.gui.styles import PADDING, FONTS, COLORS
from ms_core.preprocessing.ms_quality_filter import FeatureFilter


class FeatureFilterWidget(BaseProcessingWidget):
    """Widget for the Feature Filtering and Missing Value Imputation step."""

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
            title="Step 4: 特徵篩選與缺失值填補",
            description=(
                "依各組別 ratio 進行特徵篩選，並補值缺失訊號。"
                "另外可設定最小 QC_ratio，過低時直接刪除特徵。"
            ),
            step_index=step_index,
            on_load_file=on_load_file,
            on_complete=on_complete,
            on_log=on_log,
        )
        self._processor = FeatureFilter()

    def _create_parameters(self) -> None:
        """Create parameter inputs."""
        signal_label = ctk.CTkLabel(
            self.params_frame,
            text="訊號門檻值",
            font=FONTS["body"],
        )
        signal_label.grid(row=0, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        self.signal_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="5000",
            width=100,
            font=FONTS["body"],
        )
        self.signal_entry.insert(0, "5000")
        self.signal_entry.grid(row=0, column=1, padx=PADDING["small"], pady=PADDING["small"])

        bg_label = ctk.CTkLabel(
            self.params_frame,
            text="背景比例門檻",
            font=FONTS["body"],
        )
        bg_label.grid(row=1, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="w")
        self.bg_slider = self._create_threshold_slider(row=1, default_value=0.33, on_change=self._update_bg)
        self.bg_entry = self._create_threshold_entry(row=1, default_value=0.33, on_apply=self._apply_bg)

        skew_label = ctk.CTkLabel(
            self.params_frame,
            text="偏斜比例門檻",
            font=FONTS["body"],
        )
        skew_label.grid(row=2, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="w")
        self.skew_slider = self._create_threshold_slider(row=2, default_value=0.66, on_change=self._update_skew)
        self.skew_entry = self._create_threshold_entry(row=2, default_value=0.66, on_apply=self._apply_skew)

        diff_label = ctk.CTkLabel(
            self.params_frame,
            text="組間差異門檻",
            font=FONTS["body"],
        )
        diff_label.grid(row=3, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="w")
        self.diff_slider = self._create_threshold_slider(row=3, default_value=0.30, on_change=self._update_diff)
        self.diff_entry = self._create_threshold_entry(row=3, default_value=0.30, on_apply=self._apply_diff)

        qc_ratio_label = ctk.CTkLabel(
            self.params_frame,
            text="最小 QC_ratio",
            font=FONTS["body"],
        )
        qc_ratio_label.grid(row=4, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="w")
        self.qc_ratio_slider = self._create_threshold_slider(
            row=4,
            default_value=0.00,
            on_change=self._update_qc_ratio,
        )
        self.qc_ratio_entry = self._create_threshold_entry(
            row=4,
            default_value=0.00,
            on_apply=self._apply_qc_ratio,
        )

        criteria_text = (
            "篩選規則：\n"
            "  1. 穩定型：至少 2 組的 ratio >= 背景比例門檻\n"
            "  2. 偏斜型：任一組 ratio >= 偏斜比例門檻\n"
            "  3. 差異型：最大 ratio - 最小 ratio >= 組間差異門檻\n"
            "  4. QC 規則：QC_ratio = 0 必刪；若設定最小 QC_ratio，低於該值也刪除"
        )
        criteria_label = ctk.CTkLabel(
            self.params_frame,
            text=criteria_text,
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            justify="left",
        )
        criteria_label.grid(
            row=5,
            column=0,
            columnspan=3,
            padx=PADDING["small"],
            pady=PADDING["small"],
            sticky="w",
        )

    def _create_threshold_slider(
        self,
        row: int,
        default_value: float,
        on_change: Callable[[float], None],
    ) -> ctk.CTkSlider:
        slider = ctk.CTkSlider(
            self.params_frame,
            from_=0,
            to=1,
            number_of_steps=1000,
            command=on_change,
        )
        slider.set(default_value)
        slider.grid(row=row, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="ew")
        return slider

    def _create_threshold_entry(
        self,
        row: int,
        default_value: float,
        on_apply: Callable[[], float],
    ) -> ctk.CTkEntry:
        entry = ctk.CTkEntry(
            self.params_frame,
            width=80,
            font=FONTS["small"],
            justify="center",
        )
        entry.insert(0, f"{default_value:.3f}")
        entry.grid(row=row, column=2, padx=PADDING["small"], pady=PADDING["small"])
        entry.bind("<Return>", lambda _: on_apply())
        entry.bind("<KP_Enter>", lambda _: on_apply())
        entry.bind("<FocusOut>", lambda _: on_apply())
        return entry

    def _sync_entry_from_slider(self, value: float, entry: ctk.CTkEntry) -> None:
        value = self._clamp_threshold(value)
        if self.focus_get() is entry:
            return
        entry.delete(0, "end")
        entry.insert(0, f"{value:.3f}")

    def _commit_entry_to_slider(self, entry: ctk.CTkEntry, slider: ctk.CTkSlider) -> float:
        current = float(slider.get())
        text = entry.get().strip()
        try:
            parsed = self._clamp_threshold(float(text))
        except ValueError:
            parsed = self._clamp_threshold(current)
        slider.set(parsed)
        entry.delete(0, "end")
        entry.insert(0, f"{parsed:.3f}")
        return parsed

    @staticmethod
    def _clamp_threshold(value: float) -> float:
        return max(0.0, min(1.0, value))

    def _update_bg(self, value: float) -> None:
        self._sync_entry_from_slider(float(value), self.bg_entry)

    def _update_skew(self, value: float) -> None:
        self._sync_entry_from_slider(float(value), self.skew_entry)

    def _update_diff(self, value: float) -> None:
        self._sync_entry_from_slider(float(value), self.diff_entry)

    def _update_qc_ratio(self, value: float) -> None:
        self._sync_entry_from_slider(float(value), self.qc_ratio_entry)

    def _apply_bg(self) -> float:
        return self._commit_entry_to_slider(self.bg_entry, self.bg_slider)

    def _apply_skew(self) -> float:
        return self._commit_entry_to_slider(self.skew_entry, self.skew_slider)

    def _apply_diff(self) -> float:
        return self._commit_entry_to_slider(self.diff_entry, self.diff_slider)

    def _apply_qc_ratio(self) -> float:
        return self._commit_entry_to_slider(self.qc_ratio_entry, self.qc_ratio_slider)

    def get_parameters(self) -> dict:
        """Get current parameter values."""
        return {
            "signal_threshold": float(self.signal_entry.get() or "5000"),
            "background_threshold": self._apply_bg(),
            "skew_threshold": self._apply_skew(),
            "diff_threshold": self._apply_diff(),
            "qc_ratio_threshold": self._apply_qc_ratio(),
        }

    def run_processing(self, data: pd.DataFrame, **params) -> pd.DataFrame:
        """Run the feature filtering step."""
        self._processor.set_progress_callback(self.update_progress)
        self._processor.config.signal_threshold = params.get("signal_threshold", 5000)

        result = self._processor.process(
            data,
            background_threshold=params.get("background_threshold"),
            skew_threshold=params.get("skew_threshold"),
            diff_threshold=params.get("diff_threshold"),
            qc_ratio_threshold=params.get("qc_ratio_threshold"),
            protected_rows=set(
                self._context.get("protected_rows") or self._context.get("red_font_rows") or []
            ),
        )

        if not result.success:
            raise Exception(result.message)

        self.log(f"Statistics: {result.statistics}")
        self._last_metadata = result.metadata
        return result.data
