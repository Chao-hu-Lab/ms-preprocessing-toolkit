"""Feature Filter Widget - GUI for Step 4."""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk
import pandas as pd

from ms_preprocessing.adapters import feature_filter as feature_filter_adapter
from ms_preprocessing.gui.styles import COLORS, FONTS, PADDING
from ms_preprocessing.gui.widgets.base_widget import BaseProcessingWidget


class FeatureFilterWidget(BaseProcessingWidget):
    """Widget for the Step 4 feature filter and imputation workflow."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        step_index: int,
        on_load_file: Optional[Callable[[int], None]] = None,
        on_complete: Optional[Callable[[pd.DataFrame], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[float, str], None]] = None,
    ):
        self._threshold_controls: dict[str, tuple[tk.BooleanVar, ctk.CTkSlider, ctk.CTkEntry]] = {}
        super().__init__(
            parent,
            title="Step 4: 特徵篩選與缺失值填補",
            description="",
            step_index=step_index,
            on_load_file=on_load_file,
            on_complete=on_complete,
            on_log=on_log,
            on_progress=on_progress,
        )

    def _create_parameters(self) -> None:
        """Create parameter inputs."""
        self.params_frame.grid_columnconfigure(1, weight=1)

        signal_label = ctk.CTkLabel(
            self.params_frame,
            text="訊號門檻值",
            font=FONTS["body"],
        )
        signal_label.grid(row=0, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        self.signal_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="5000",
            width=160,
            font=FONTS["body"],
        )
        self.signal_entry.insert(0, "5000")
        self.signal_entry.grid(row=0, column=1, padx=PADDING["small"], pady=PADDING["small"])

        ctk.CTkLabel(
            self.params_frame,
            text="ratio = 組內高於訊號門檻的樣本數 / 組內總樣本數",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).grid(row=0, column=3, padx=(PADDING["medium"], PADDING["small"]), sticky="w")

        self.bg_enabled_var = tk.BooleanVar(value=True)
        self.bg_enabled_switch = self._create_threshold_switch(
            row=1,
            text="背景比例門檻",
            variable=self.bg_enabled_var,
        )
        self.bg_slider = self._create_threshold_slider(row=1, default_value=0.33, on_change=self._update_bg)
        self.bg_entry = self._create_threshold_entry(row=1, default_value=0.33, on_apply=self._apply_bg)
        self._threshold_controls["background"] = (
            self.bg_enabled_var,
            self.bg_slider,
            self.bg_entry,
        )

        ctk.CTkLabel(
            self.params_frame,
            text="啟用時：至少 2 組的 ratio >= 這個門檻才算穩定型",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).grid(row=1, column=3, padx=(PADDING["medium"], PADDING["small"]), sticky="w")

        self.skew_enabled_var = tk.BooleanVar(value=True)
        self.skew_enabled_switch = self._create_threshold_switch(
            row=2,
            text="偏斜比例門檻",
            variable=self.skew_enabled_var,
        )
        self.skew_slider = self._create_threshold_slider(row=2, default_value=0.66, on_change=self._update_skew)
        self.skew_entry = self._create_threshold_entry(row=2, default_value=0.66, on_apply=self._apply_skew)
        self._threshold_controls["skew"] = (
            self.skew_enabled_var,
            self.skew_slider,
            self.skew_entry,
        )

        ctk.CTkLabel(
            self.params_frame,
            text="啟用時：任一組 ratio >= 這個門檻就算偏斜型",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).grid(row=2, column=3, padx=(PADDING["medium"], PADDING["small"]), sticky="w")

        self.diff_enabled_var = tk.BooleanVar(value=True)
        self.diff_enabled_switch = self._create_threshold_switch(
            row=3,
            text="組間差異門檻",
            variable=self.diff_enabled_var,
        )
        self.diff_slider = self._create_threshold_slider(row=3, default_value=0.30, on_change=self._update_diff)
        self.diff_entry = self._create_threshold_entry(row=3, default_value=0.30, on_apply=self._apply_diff)
        self._threshold_controls["diff"] = (
            self.diff_enabled_var,
            self.diff_slider,
            self.diff_entry,
        )

        ctk.CTkLabel(
            self.params_frame,
            text="啟用時：最大 ratio - 最小 ratio >= 這個門檻才算差異型",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).grid(row=3, column=3, padx=(PADDING["medium"], PADDING["small"]), sticky="w")

        self.qc_ratio_enabled_var = tk.BooleanVar(value=True)
        self.qc_ratio_enabled_switch = self._create_threshold_switch(
            row=4,
            text="QC_ratio 門檻",
            variable=self.qc_ratio_enabled_var,
        )
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
        self._threshold_controls["qc_ratio"] = (
            self.qc_ratio_enabled_var,
            self.qc_ratio_slider,
            self.qc_ratio_entry,
        )

        ctk.CTkLabel(
            self.params_frame,
            text="啟用時：QC_ratio = 0 或低於輸入值的 feature 會被移除",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).grid(row=4, column=3, padx=(PADDING["medium"], PADDING["small"]), sticky="w")

        criteria_text = (
            "目前規則：\n"
            "  1. 背景比例門檻開啟時，至少 2 組 ratio >= 背景比例門檻\n"
            "  2. 偏斜比例門檻開啟時，任一組 ratio >= 偏斜比例門檻\n"
            "  3. 組間差異門檻開啟時，最大 ratio - 最小 ratio >= 組間差異門檻\n"
            "  4. QC_ratio 門檻開啟時，QC_ratio = 0 或低於設定值的 feature 會被移除"
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
            columnspan=4,
            padx=PADDING["small"],
            pady=PADDING["small"],
            sticky="w",
        )

        self._sync_threshold_control_states()

    def _create_threshold_switch(
        self,
        row: int,
        text: str,
        variable: tk.BooleanVar,
    ) -> ctk.CTkSwitch:
        switch = ctk.CTkSwitch(
            self.params_frame,
            text=text,
            variable=variable,
            onvalue=True,
            offvalue=False,
            command=self._sync_threshold_control_states,
            font=FONTS["body"],
        )
        switch.grid(row=row, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="w")
        return switch

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

    def _sync_threshold_control_states(self) -> None:
        """Enable or disable threshold inputs based on each switch state."""
        for variable, slider, entry in self._threshold_controls.values():
            state = "normal" if variable.get() else "disabled"
            slider.configure(state=state)
            entry.configure(state=state)

    def _sync_entry_from_slider(self, value: float, entry: ctk.CTkEntry) -> None:
        value = self._clamp_threshold(value)
        if self.focus_get() is entry:
            return
        entry.delete(0, "end")
        entry.insert(0, f"{value:.3f}")

    def _commit_entry_to_slider(self, entry: ctk.CTkEntry, slider: ctk.CTkSlider) -> float:
        current = float(slider.get())
        if entry.cget("state") == "disabled":
            return self._clamp_threshold(current)

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
            "enable_background_threshold": bool(self.bg_enabled_var.get()),
            "enable_skew_threshold": bool(self.skew_enabled_var.get()),
            "enable_diff_threshold": bool(self.diff_enabled_var.get()),
            "enable_qc_ratio_threshold": bool(self.qc_ratio_enabled_var.get()),
        }

    def run_processing(self, data: pd.DataFrame, **params) -> pd.DataFrame:
        """Run the feature filtering step."""
        result = feature_filter_adapter.run_from_df(
            data,
            background_threshold=params.get("background_threshold"),
            skew_threshold=params.get("skew_threshold"),
            diff_threshold=params.get("diff_threshold"),
            qc_ratio_threshold=params.get("qc_ratio_threshold"),
            enable_background_threshold=params.get("enable_background_threshold", True),
            enable_skew_threshold=params.get("enable_skew_threshold", True),
            enable_diff_threshold=params.get("enable_diff_threshold", True),
            enable_qc_ratio_threshold=params.get("enable_qc_ratio_threshold", True),
            signal_threshold=params.get("signal_threshold", 5000),
            protected_rows=set(
                self._context.get("protected_rows") or self._context.get("red_font_rows") or []
            ),
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
            "step_parameters": dict(params),
            "imputation_stats": {
                "cells_imputed": result.statistics.get("cells_imputed", 0),
                "cells_imputed_from_nan": result.statistics.get("cells_imputed_from_nan", 0),
                "cells_imputed_from_zero": result.statistics.get("cells_imputed_from_zero", 0),
            },
        }
        if result.data is None:
            raise Exception("Adapter returned no data")
        return result.data
