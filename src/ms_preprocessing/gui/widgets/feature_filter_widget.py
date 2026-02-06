"""
Feature Filter Widget - GUI for Step 4.
"""

from typing import Optional, Callable
import customtkinter as ctk
import pandas as pd

from ms_preprocessing.gui.widgets.base_widget import BaseProcessingWidget
from ms_preprocessing.gui.styles import PADDING, FONTS, COLORS
from ms_preprocessing.core.feature_filter import FeatureFilter


class FeatureFilterWidget(BaseProcessingWidget):
    """Widget for the Feature Filtering and Missing Value Imputation step."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        on_complete: Optional[Callable[[pd.DataFrame], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(
            parent,
            title="Step 4: 篩選與填補 (Feature Filtering)",
            description="依據 ratio 門檻篩選有效特徵，並以組內最小值/2 填補缺失值",
            on_complete=on_complete,
            on_log=on_log,
        )
        self._processor = FeatureFilter()

    def _create_parameters(self) -> None:
        """Create parameter inputs."""
        # Signal threshold
        signal_label = ctk.CTkLabel(
            self.params_frame,
            text="訊號閾值：",
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

        # Background threshold
        bg_label = ctk.CTkLabel(
            self.params_frame,
            text="背景門檻 (穩定)：",
            font=FONTS["body"],
        )
        bg_label.grid(row=1, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        self.bg_slider = ctk.CTkSlider(
            self.params_frame,
            from_=0,
            to=1,
            number_of_steps=100,
            command=self._update_bg_label,
        )
        self.bg_slider.set(0.33)
        self.bg_slider.grid(row=1, column=1, padx=PADDING["small"], pady=PADDING["small"])

        self.bg_value_label = ctk.CTkLabel(
            self.params_frame,
            text="33%",
            font=FONTS["small"],
            width=50,
        )
        self.bg_value_label.grid(row=1, column=2, padx=PADDING["small"], pady=PADDING["small"])

        # Skew threshold
        skew_label = ctk.CTkLabel(
            self.params_frame,
            text="偏態門檻：",
            font=FONTS["body"],
        )
        skew_label.grid(row=2, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        self.skew_slider = ctk.CTkSlider(
            self.params_frame,
            from_=0,
            to=1,
            number_of_steps=100,
            command=self._update_skew_label,
        )
        self.skew_slider.set(0.66)
        self.skew_slider.grid(row=2, column=1, padx=PADDING["small"], pady=PADDING["small"])

        self.skew_value_label = ctk.CTkLabel(
            self.params_frame,
            text="66%",
            font=FONTS["small"],
            width=50,
        )
        self.skew_value_label.grid(row=2, column=2, padx=PADDING["small"], pady=PADDING["small"])

        # Diff threshold
        diff_label = ctk.CTkLabel(
            self.params_frame,
            text="差異門檻：",
            font=FONTS["body"],
        )
        diff_label.grid(row=3, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        self.diff_slider = ctk.CTkSlider(
            self.params_frame,
            from_=0,
            to=1,
            number_of_steps=100,
            command=self._update_diff_label,
        )
        self.diff_slider.set(0.30)
        self.diff_slider.grid(row=3, column=1, padx=PADDING["small"], pady=PADDING["small"])

        self.diff_value_label = ctk.CTkLabel(
            self.params_frame,
            text="30%",
            font=FONTS["small"],
            width=50,
        )
        self.diff_value_label.grid(row=3, column=2, padx=PADDING["small"], pady=PADDING["small"])

        # Criteria explanation
        criteria_text = (
            "保留條件 (符合任一)：\n"
            "  1. 穩定：>=2組 ratio >= 背景門檻\n"
            "  2. 偏態：任一組 ratio >= 偏態門檻\n"
            "  3. 差異：任兩組差異 >= 差異門檻"
        )
        criteria_label = ctk.CTkLabel(
            self.params_frame,
            text=criteria_text,
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            justify="left",
        )
        criteria_label.grid(row=4, column=0, columnspan=3, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

    def _update_bg_label(self, value: float) -> None:
        """Update background threshold label."""
        self.bg_value_label.configure(text=f"{int(value * 100)}%")

    def _update_skew_label(self, value: float) -> None:
        """Update skew threshold label."""
        self.skew_value_label.configure(text=f"{int(value * 100)}%")

    def _update_diff_label(self, value: float) -> None:
        """Update diff threshold label."""
        self.diff_value_label.configure(text=f"{int(value * 100)}%")

    def _get_parameters(self) -> dict:
        """Get current parameter values."""
        return {
            "signal_threshold": float(self.signal_entry.get() or "5000"),
            "background_threshold": self.bg_slider.get(),
            "skew_threshold": self.skew_slider.get(),
            "diff_threshold": self.diff_slider.get(),
        }

    def _run_processing(self, data: pd.DataFrame, **params) -> pd.DataFrame:
        """Run the feature filtering step."""
        self._processor.set_progress_callback(self.update_progress)

        # Update config
        self._processor.config.signal_threshold = params.get("signal_threshold", 5000)

        result = self._processor.process(
            data,
            background_threshold=params.get("background_threshold"),
            skew_threshold=params.get("skew_threshold"),
            diff_threshold=params.get("diff_threshold"),
            protected_rows=set(
                self._context.get("protected_rows") or self._context.get("red_font_rows") or []
            ),
        )

        if not result.success:
            raise Exception(result.message)

        self.log(f"Statistics: {result.statistics}")
        self._last_metadata = result.metadata
        return result.data
