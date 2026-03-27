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
    """Widget for the Step 4 feature filter workflow."""

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
            title="Step 4: 特徵篩選 (Feature Filtering)",
            description="依訊號強度、背景比例、組間差異與 QC 表現篩選特徵。",
            step_index=step_index,
            on_load_file=on_load_file,
            on_complete=on_complete,
            on_log=on_log,
            on_progress=on_progress,
        )

    def _create_parameters(self) -> None:
        """Create parameter inputs."""
        self._configure_form_grid()

        signal_label = ctk.CTkLabel(self.params_frame, text="訊號門檻值", font=FONTS["body"])
        self._style_form_label(signal_label)
        signal_label.grid(row=0, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="e")

        self.signal_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="5000",
            font=FONTS["body"],
        )
        self._style_numeric_entry(self.signal_entry)
        self.signal_entry.insert(0, "5000")
        self.signal_entry.grid(row=0, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

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

        self.intensity_fc_enabled_var = tk.BooleanVar(value=True)
        self.intensity_fc_enabled_switch = self._create_threshold_switch(
            row=2,
            text="強度倍率門檻",
            variable=self.intensity_fc_enabled_var,
        )
        self.intensity_fc_slider = self._create_threshold_slider(
            row=2,
            default_value=2.0,
            on_change=self._update_intensity_fc,
            from_=1.0,
            to=10.0,
        )
        self.intensity_fc_entry = self._create_threshold_entry(
            row=2,
            default_value=2.0,
            on_apply=self._apply_intensity_fc,
        )
        self._threshold_controls["intensity_fc"] = (
            self.intensity_fc_enabled_var,
            self.intensity_fc_slider,
            self.intensity_fc_entry,
        )

        self.diff_enabled_var = tk.BooleanVar(value=True)
        self.diff_enabled_switch = self._create_threshold_switch(
            row=3,
            text="組間差異門檻",
            variable=self.diff_enabled_var,
        )
        self.diff_slider = self._create_threshold_slider(row=3, default_value=0.25, on_change=self._update_diff)
        self.diff_entry = self._create_threshold_entry(row=3, default_value=0.25, on_apply=self._apply_diff)
        self._threshold_controls["diff"] = (
            self.diff_enabled_var,
            self.diff_slider,
            self.diff_entry,
        )

        self.qc_ratio_enabled_var = tk.BooleanVar(value=True)
        self.qc_ratio_enabled_switch = self._create_threshold_switch(
            row=4,
            text="QC_ratio 門檻",
            variable=self.qc_ratio_enabled_var,
        )
        self.qc_ratio_slider = self._create_threshold_slider(
            row=4,
            default_value=0.25,
            on_change=self._update_qc_ratio,
        )
        self.qc_ratio_entry = self._create_threshold_entry(
            row=4,
            default_value=0.25,
            on_apply=self._apply_qc_ratio,
        )
        self._threshold_controls["qc_ratio"] = (
            self.qc_ratio_enabled_var,
            self.qc_ratio_slider,
            self.qc_ratio_entry,
        )

        self.criteria_textbox = ctk.CTkTextbox(
            self._content_frame,
            height=180,
            font=FONTS["small"],
            wrap="word",
        )
        self.criteria_textbox.pack(fill="x", padx=PADDING["large"], pady=(PADDING["small"], 0))
        self._populate_criteria_textbox()

        ctk.CTkFrame(
            self._content_frame,
            height=1,
            fg_color="#2a3f5a",
        ).pack(fill="x", padx=PADDING["large"], pady=(PADDING["medium"], 0))

        self._export_deleted_var = tk.BooleanVar(value=False)
        ctk.CTkSwitch(
            self._content_frame,
            text="匯出時包含已刪除特徵清單（deleted_feature 工作表）",
            variable=self._export_deleted_var,
            onvalue=True,
            offvalue=False,
            font=FONTS["body"],
        ).pack(anchor="w", padx=PADDING["large"], pady=(PADDING["small"], PADDING["medium"]))

        self._sync_threshold_control_states()

    def _populate_criteria_textbox(self) -> None:
        """Render the filtering rules in clearer lab-facing language."""
        content = (
            "篩選規則說明\n\n"
            "整體邏輯\n"
            "前 3 條是正向保留條件，採 OR 判斷；只要符合其中一條，feature 就可以先保留下來。\n"
            "QC_ratio 則是負向覆寫條件，用來排除在 QC 中完全不穩定或幾乎沒有檢出的 feature。\n\n"
            "1. 訊號門檻值\n"
            "   先確認這個 feature 本身有沒有足夠訊號。\n"
            "   後續的 ratio、diff ratio 與 QC_ratio，都是以高於訊號門檻的樣本數為基礎計算。\n\n"
            "2. 背景比例門檻（Stable gate）\n"
            "   ratio = 組內高於訊號門檻的樣本數 / 組內總樣本數\n"
            "   若至少 2 組的 ratio 都大於等於背景比例門檻，代表這個 feature 在多個實驗組都能穩定檢出，可先保留。\n\n"
            "3. 強度倍率門檻（Intensity FC gate）\n"
            "   這一條看的是不同組別之間的平均強度差異。\n"
            "   fold-change = 最大組平均強度 / 最小組平均強度\n"
            "   若 fold-change 大於等於強度倍率門檻，代表至少有一組顯著高於另一組，可視為具生物差異訊號。\n\n"
            "4. 組間差異門檻（Diff gate）\n"
            "   diff ratio = 最大 ratio - 最小 ratio\n"
            "   若 diff ratio 大於等於組間差異門檻，代表各組檢出比例差異夠大，可保留作後續分析。\n\n"
            "5. QC_ratio 門檻（QC gate）\n"
            "   QC_ratio = QC 中高於訊號門檻的樣本數 / QC 總樣本數\n"
            "   若 QC_ratio = 0，或低於你設定的 QC_ratio 門檻，代表這個 feature 在 QC 中表現不穩定，會被移除。"
        )
        self.criteria_textbox.insert("1.0", content)
        inner_text = getattr(self.criteria_textbox, "_textbox", None)
        if inner_text is not None:
            heading_font = (FONTS["small"][0], FONTS["small"][1], "bold")
            inner_text.tag_configure("heading", foreground=COLORS["text"], font=heading_font)
            for marker in [
                "篩選規則說明",
                "整體邏輯",
                "1. 訊號門檻值",
                "2. 背景比例門檻（Stable gate）",
                "3. 強度倍率門檻（Intensity FC gate）",
                "4. 組間差異門檻（Diff gate）",
                "5. QC_ratio 門檻（QC gate）",
            ]:
                start = "1.0"
                while True:
                    pos = inner_text.search(marker, start, stopindex="end")
                    if not pos:
                        break
                    end = f"{pos}+{len(marker)}c"
                    inner_text.tag_add("heading", pos, end)
                    start = end
        self.criteria_textbox.configure(state="disabled")

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
        self._style_form_switch(switch)
        switch.grid(row=row, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="e")
        return switch

    def _create_threshold_slider(
        self,
        row: int,
        default_value: float,
        on_change: Callable[[float], None],
        from_: float = 0,
        to: float = 1,
    ) -> ctk.CTkSlider:
        slider = ctk.CTkSlider(
            self.params_frame,
            from_=from_,
            to=to,
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
            font=FONTS["small"],
        )
        self._style_numeric_entry(entry)
        entry.insert(0, f"{default_value:.3f}")
        entry.grid(row=row, column=2, padx=PADDING["small"], pady=PADDING["small"], sticky="w")
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

    @staticmethod
    def _clamp_threshold(value: float) -> float:
        return max(0.0, float(value))

    def _sync_entry_from_slider(self, value: float, entry: ctk.CTkEntry) -> None:
        value = self._clamp_threshold(value)
        if self.focus_get() is entry:
            return
        entry.delete(0, "end")
        entry.insert(0, f"{value:.3f}")

    def _commit_entry_to_slider(self, entry: ctk.CTkEntry, slider: ctk.CTkSlider) -> float:
        current = float(slider.get())
        if entry.cget("state") == "disabled":
            return self._clamp_to_slider(current, slider)

        text = entry.get().strip()
        try:
            parsed = self._clamp_to_slider(float(text), slider)
        except ValueError:
            parsed = self._clamp_to_slider(current, slider)
        slider.set(parsed)
        entry.delete(0, "end")
        entry.insert(0, f"{parsed:.3f}")
        return parsed

    @staticmethod
    def _clamp_to_slider(value: float, slider: ctk.CTkSlider) -> float:
        lo = float(slider.cget("from_"))
        hi = float(slider.cget("to"))
        return max(lo, min(hi, value))

    def _update_bg(self, value: float) -> None:
        self._sync_entry_from_slider(float(value), self.bg_entry)

    def _update_intensity_fc(self, value: float) -> None:
        self._sync_entry_from_slider(float(value), self.intensity_fc_entry)

    def _update_diff(self, value: float) -> None:
        self._sync_entry_from_slider(float(value), self.diff_entry)

    def _update_qc_ratio(self, value: float) -> None:
        self._sync_entry_from_slider(float(value), self.qc_ratio_entry)

    def _apply_bg(self) -> float:
        return self._commit_entry_to_slider(self.bg_entry, self.bg_slider)

    def _apply_intensity_fc(self) -> float:
        return self._commit_entry_to_slider(self.intensity_fc_entry, self.intensity_fc_slider)

    def _apply_diff(self) -> float:
        return self._commit_entry_to_slider(self.diff_entry, self.diff_slider)

    def _apply_qc_ratio(self) -> float:
        return self._commit_entry_to_slider(self.qc_ratio_entry, self.qc_ratio_slider)

    def get_parameters(self) -> dict:
        """Get current parameter values."""
        return {
            "signal_threshold": float(self.signal_entry.get() or "5000"),
            "background_threshold": self._apply_bg(),
            "diff_threshold": self._apply_diff(),
            "qc_ratio_threshold": self._apply_qc_ratio(),
            "intensity_fc_threshold": self._apply_intensity_fc(),
            "enable_background_threshold": bool(self.bg_enabled_var.get()),
            "enable_diff_threshold": bool(self.diff_enabled_var.get()),
            "enable_qc_ratio_threshold": bool(self.qc_ratio_enabled_var.get()),
            "enable_intensity_fc_threshold": bool(self.intensity_fc_enabled_var.get()),
        }

    def apply_parameters(self, params: dict) -> None:
        """Apply a named Step 4 preset to the visible controls."""
        if "signal_threshold" in params:
            self.signal_entry.delete(0, "end")
            self.signal_entry.insert(0, str(params["signal_threshold"]))

        self._apply_threshold_value("background", params, "background_threshold", "enable_background_threshold")
        self._apply_threshold_value("diff", params, "diff_threshold", "enable_diff_threshold")
        self._apply_threshold_value("qc_ratio", params, "qc_ratio_threshold", "enable_qc_ratio_threshold")
        self._apply_threshold_value(
            "intensity_fc",
            params,
            "intensity_fc_threshold",
            "enable_intensity_fc_threshold",
        )
        self._sync_threshold_control_states()

    def _apply_threshold_value(
        self,
        control_key: str,
        params: dict,
        value_key: str,
        enabled_key: str,
    ) -> None:
        variable, slider, entry = self._threshold_controls[control_key]

        if enabled_key in params:
            variable.set(bool(params[enabled_key]))

        if value_key in params:
            parsed = self._clamp_to_slider(float(params[value_key]), slider)
            slider.set(parsed)
            entry.delete(0, "end")
            entry.insert(0, f"{parsed:.3f}")

    def run_processing(self, data: pd.DataFrame, **params) -> pd.DataFrame:
        """Run the feature filtering step."""
        result = feature_filter_adapter.run_from_df(
            data,
            background_threshold=params.get("background_threshold"),
            diff_threshold=params.get("diff_threshold"),
            qc_ratio_threshold=params.get("qc_ratio_threshold"),
            intensity_fc_threshold=params.get("intensity_fc_threshold"),
            enable_background_threshold=params.get("enable_background_threshold", True),
            enable_diff_threshold=params.get("enable_diff_threshold", True),
            enable_qc_ratio_threshold=params.get("enable_qc_ratio_threshold", True),
            enable_intensity_fc_threshold=params.get("enable_intensity_fc_threshold", True),
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
        }
        if result.data is None:
            raise Exception("Adapter returned no data")
        return result.data
