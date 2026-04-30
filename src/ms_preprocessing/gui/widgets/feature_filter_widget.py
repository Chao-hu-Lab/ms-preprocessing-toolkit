"""Feature Filter Widget - GUI for Step 4."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk
import pandas as pd

from ms_preprocessing.adapters import feature_filter as feature_filter_adapter
from ms_preprocessing.gui.styles import COLORS, FONTS, PADDING
from ms_preprocessing.gui.validation import ValidationWarning, validate_step4_params
from ms_preprocessing.gui.widgets.base_widget import BaseProcessingWidget


class FeatureFilterWidget(BaseProcessingWidget):
    """Widget for the Step 4 feature filter workflow."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        step_index: int,
        on_load_file: Callable[[int], None] | None = None,
        on_complete: Callable[[pd.DataFrame], None] | None = None,
        on_log: Callable[[str], None] | None = None,
        on_progress: Callable[[float, str], None] | None = None,
    ):
        self._threshold_controls: dict[str, tuple[tk.BooleanVar, ctk.CTkSlider, ctk.CTkEntry]] = {}
        self._allow_single_group_stable: bool = False
        super().__init__(
            parent,
            title="Step 4: 特徵篩選 (Feature Filtering)",
            description="依訊號強度、穩定檢出率、存在/缺失標記（MNAR）與 QC 檢出率篩選特徵。",
            step_index=step_index,
            on_load_file=on_load_file,
            on_complete=on_complete,
            on_log=on_log,
            on_progress=on_progress,
            scrollable_content=True,
        )

    def _create_parameters(self) -> None:
        """Create parameter inputs."""
        self.params_frame.grid_columnconfigure(0, minsize=44)
        self.params_frame.grid_columnconfigure(1, minsize=180)
        self.params_frame.grid_columnconfigure(2, minsize=160, weight=1)
        self.params_frame.grid_columnconfigure(3, minsize=110)

        signal_label = ctk.CTkLabel(self.params_frame, text="訊號強度門檻", font=FONTS["body"])
        self._style_form_label(signal_label)
        signal_label.grid(row=0, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="e")

        self.signal_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="5000",
            font=FONTS["body"],
        )
        self._style_numeric_entry(self.signal_entry)
        self.signal_entry.insert(0, "5000")
        self.signal_entry.grid(
            row=0, column=2, columnspan=2, padx=PADDING["small"], pady=PADDING["small"], sticky="w"
        )

        self.bg_enabled_var = tk.BooleanVar(value=True)
        self.bg_enabled_switch = self._create_threshold_switch(
            row=1,
            text="穩定檢出率門檻",
            variable=self.bg_enabled_var,
        )
        self.bg_slider = self._create_threshold_slider(
            row=1, default_value=0.33, on_change=self._update_bg
        )
        self.bg_entry = self._create_threshold_entry(
            row=1, default_value=0.33, on_apply=self._apply_bg
        )
        self._threshold_controls["background"] = (
            self.bg_enabled_var,
            self.bg_slider,
            self.bg_entry,
        )

        self.intensity_fc_enabled_var = tk.BooleanVar(value=False)
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

        self.mnar_enabled_var = tk.BooleanVar(value=True)
        self.mnar_enabled_switch = self._create_threshold_switch(
            row=3,
            text="出現組檢出率下限",
            variable=self.mnar_enabled_var,
        )
        self.high_det_slider = self._create_threshold_slider(
            row=3, default_value=0.8, on_change=self._update_high_det
        )
        self.high_det_entry = self._create_threshold_entry(
            row=3, default_value=0.8, on_apply=self._apply_high_det
        )
        self._threshold_controls["mnar_high"] = (
            self.mnar_enabled_var,
            self.high_det_slider,
            self.high_det_entry,
        )

        low_det_label = ctk.CTkLabel(self.params_frame, text="缺失組檢出率上限", font=FONTS["body"])
        self._style_form_label(low_det_label)
        low_det_label.grid(
            row=4, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="e"
        )
        self.low_det_slider = self._create_threshold_slider(
            row=4, default_value=0.2, on_change=self._update_low_det
        )
        self.low_det_entry = self._create_threshold_entry(
            row=4, default_value=0.2, on_apply=self._apply_low_det
        )
        self._threshold_controls["mnar_low"] = (
            self.mnar_enabled_var,
            self.low_det_slider,
            self.low_det_entry,
        )

        self.qc_ratio_enabled_var = tk.BooleanVar(value=True)
        self.qc_ratio_enabled_switch = self._create_threshold_switch(
            row=5,
            text="QC 檢出率門檻",
            variable=self.qc_ratio_enabled_var,
        )
        self.qc_ratio_slider = self._create_threshold_slider(
            row=5,
            default_value=0.25,
            on_change=self._update_qc_ratio,
        )
        self.qc_ratio_entry = self._create_threshold_entry(
            row=5,
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
            height=84,
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
            "穩定檢出、強度倍率、存在/缺失標記是正向保留條件，採 OR 判斷；只要符合其中一條，feature 就可以先保留下來。\n"
            "QC 檢出率是負向覆寫條件，用來排除在 QC 中完全不穩定或幾乎沒有檢出的 feature。\n\n"
            "1. 訊號強度門檻\n"
            "   先確認這個 feature 本身有沒有足夠訊號。\n"
            "   後續的檢出率與 QC 檢出率，都是以高於訊號強度門檻的樣本數為基礎計算。\n\n"
            "2. 穩定檢出率門檻（Stable detection gate）\n"
            "   檢出率 = 組內高於訊號強度門檻的樣本數 / 組內總樣本數\n"
            "   若至少 2 個實驗組的檢出率都大於等於此門檻，代表這個 feature 在多個組別穩定出現，可先保留。\n\n"
            "3. 強度倍率門檻（Intensity FC gate）\n"
            "   這一條看的是不同組別之間的平均強度差異。\n"
            "   fold-change = 最大組平均強度 / 最小組平均強度\n"
            "   若 fold-change 大於等於強度倍率門檻，代表至少有一組顯著高於另一組，可視為具生物差異訊號。\n\n"
            "4. 存在/缺失標記（MNAR presence/absence gate）\n"
            "   檢出率 = 組內高於訊號強度門檻的樣本數 / 組內總樣本數\n"
            "   若至少一組檢出率 ≥ 出現組檢出率下限，且至少另一組檢出率 ≤ 缺失組檢出率上限，\n"
            "   代表此 feature 在某組中高頻率出現、在另一組中接近缺失（MNAR 特徵），予以保留並標記。\n"
            "   輸出欄位 is_Presence_Absence_Marker = True 的特徵即屬此類。\n\n"
            "5. QC 檢出率門檻（QC gate）\n"
            "   QC 檢出率 = QC 中高於訊號強度門檻的樣本數 / QC 總樣本數\n"
            "   若 QC 檢出率 = 0，或低於你設定的 QC 檢出率門檻，代表這個 feature 在 QC 中表現不穩定，會被移除。"
        )
        self.criteria_textbox.insert("1.0", content)
        inner_text = getattr(self.criteria_textbox, "_textbox", None)
        if inner_text is not None:
            heading_font = (FONTS["small"][0], FONTS["small"][1], "bold")
            inner_text.tag_configure("heading", foreground=COLORS["text"], font=heading_font)
            for marker in [
                "篩選規則說明",
                "整體邏輯",
                "1. 訊號強度門檻",
                "2. 穩定檢出率門檻（Stable detection gate）",
                "3. 強度倍率門檻（Intensity FC gate）",
                "4. 存在/缺失標記（MNAR presence/absence gate）",
                "5. QC 檢出率門檻（QC gate）",
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
            text="",
            variable=variable,
            onvalue=True,
            offvalue=False,
            command=self._sync_threshold_control_states,
            font=FONTS["body"],
        )
        switch.configure(width=44)
        switch.grid(
            row=row, column=0, padx=(PADDING["small"], 0), pady=PADDING["small"], sticky="w"
        )

        label = ctk.CTkLabel(self.params_frame, text=text, font=FONTS["body"])
        self._style_form_label(label)
        label.grid(row=row, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="e")
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
        slider.grid(row=row, column=2, padx=PADDING["small"], pady=PADDING["small"], sticky="ew")
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
        entry.grid(row=row, column=3, padx=PADDING["small"], pady=PADDING["small"], sticky="w")
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

    def _update_high_det(self, value: float) -> None:
        self._sync_entry_from_slider(float(value), self.high_det_entry)

    def _update_low_det(self, value: float) -> None:
        self._sync_entry_from_slider(float(value), self.low_det_entry)

    def _update_qc_ratio(self, value: float) -> None:
        self._sync_entry_from_slider(float(value), self.qc_ratio_entry)

    def _apply_bg(self) -> float:
        return self._commit_entry_to_slider(self.bg_entry, self.bg_slider)

    def _apply_intensity_fc(self) -> float:
        return self._commit_entry_to_slider(self.intensity_fc_entry, self.intensity_fc_slider)

    def _apply_high_det(self) -> float:
        return self._commit_entry_to_slider(self.high_det_entry, self.high_det_slider)

    def _apply_low_det(self) -> float:
        return self._commit_entry_to_slider(self.low_det_entry, self.low_det_slider)

    def _apply_qc_ratio(self) -> float:
        return self._commit_entry_to_slider(self.qc_ratio_entry, self.qc_ratio_slider)

    def get_parameters(self) -> dict:
        """Get current parameter values."""
        return {
            "signal_threshold": float(self.signal_entry.get() or "5000"),
            "background_threshold": self._apply_bg(),
            "high_det_thresh": self._apply_high_det(),
            "low_det_thresh": self._apply_low_det(),
            "qc_ratio_threshold": self._apply_qc_ratio(),
            "intensity_fc_threshold": self._apply_intensity_fc(),
            "enable_background_threshold": bool(self.bg_enabled_var.get()),
            "enable_qc_ratio_threshold": bool(self.qc_ratio_enabled_var.get()),
            "enable_intensity_fc_threshold": bool(self.intensity_fc_enabled_var.get()),
            "enable_mnar_gate": bool(self.mnar_enabled_var.get()),
            "allow_single_group_stable": self._allow_single_group_stable,
        }

    def apply_parameters(self, params: dict) -> None:
        """Apply a named Step 4 preset to the visible controls."""
        if "signal_threshold" in params:
            self.signal_entry.delete(0, "end")
            self.signal_entry.insert(0, str(params["signal_threshold"]))

        self._apply_threshold_value(
            "background", params, "background_threshold", "enable_background_threshold"
        )
        self._apply_threshold_value(
            "qc_ratio", params, "qc_ratio_threshold", "enable_qc_ratio_threshold"
        )
        self._apply_threshold_value(
            "intensity_fc",
            params,
            "intensity_fc_threshold",
            "enable_intensity_fc_threshold",
        )
        if "enable_mnar_gate" in params:
            self.mnar_enabled_var.set(bool(params["enable_mnar_gate"]))
        if "high_det_thresh" in params:
            parsed = self._clamp_to_slider(float(params["high_det_thresh"]), self.high_det_slider)
            self.high_det_slider.set(parsed)
            self.high_det_entry.delete(0, "end")
            self.high_det_entry.insert(0, f"{parsed:.3f}")
        if "low_det_thresh" in params:
            parsed = self._clamp_to_slider(float(params["low_det_thresh"]), self.low_det_slider)
            self.low_det_slider.set(parsed)
            self.low_det_entry.delete(0, "end")
            self.low_det_entry.insert(0, f"{parsed:.3f}")
        self._sync_threshold_control_states()

    def validate_parameters(self, params: dict) -> list[ValidationWarning]:
        return validate_step4_params(params)

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

    def _count_analysis_groups(self) -> int:
        """Count non-QC analysis groups in the loaded data."""
        if self._data is None:
            return 0
        from ms_preprocessing.adapters import feature_filter as _ff_adapter

        return _ff_adapter.count_analysis_groups(self._data)

    def _confirm_single_group_run(self) -> bool:
        """Show a confirmation dialog for single-group degraded stable gate.

        Extracted as a separate method so tests can monkeypatch it without
        needing a real Tk dialog.
        """
        import tkinter.messagebox

        return bool(
            tkinter.messagebox.askokcancel(
                "單一組別警告",
                "偵測到資料只有 1 個分析組別（非 QC）。\n\n"
                "「穩定檢出率門檻」正常需要至少 2 個實驗組，\n"
                "繼續執行將退化為：只要該組檢出率 ≥ 設定門檻即保留特徵。\n\n"
                "確認要以單組降級模式繼續嗎？",
                parent=self,
            )
        )

    def _detect_small_biological_groups(self) -> dict[str, int]:
        """Return {group_name: n} for biological groups with N < 10."""
        if self._data is None:
            return {}
        summary = feature_filter_adapter.get_group_summary(self._data)
        return {
            name: info["sample_count"]
            for name, info in summary.get("groups", {}).items()
            if info["sample_count"] < 10
        }

    def _confirm_small_group_run(self, small_groups: dict[str, int]) -> bool:
        """Show Wilson CI warning for small biological groups.

        Extracted as a separate method so tests can monkeypatch it without
        needing a real Tk dialog.
        """
        import tkinter.messagebox

        group_lines = "\n".join(
            f"  {name}：N={n}（每缺失 1 筆影響 {100 / n:.1f}%）" for name, n in small_groups.items()
        )
        return bool(
            tkinter.messagebox.askokcancel(
                "小樣本警告",
                f"偵測到以下組別樣本數不足（建議 N≥10）：\n{group_lines}\n\n"
                "系統將自動套用 Wilson CI 校正，小 N 組別需更高比例才能通過門檻。\n"
                "例：N=5 時，80% 門檻實際需要近 100% 檢出。\n\n"
                "確認要繼續嗎？",
                parent=self,
            )
        )

    def _on_run_clicked(self) -> None:
        """Override to check for single-group and small-N conditions before starting worker."""
        if self._is_processing:
            self.log("Processing is already in progress")
            return
        if self._data is None:
            self.log("No input data loaded")
            return

        self._allow_single_group_stable = False
        params = self.get_parameters()
        self._last_parameters = dict(params)
        if not self._validate_parameters_before_run(params):
            return

        if self._data is not None and self.bg_enabled_var.get():
            if self._count_analysis_groups() == 1:
                if not self._confirm_single_group_run():
                    return
                self._allow_single_group_stable = True
                params["allow_single_group_stable"] = True

        if self._data is not None:
            small_groups = self._detect_small_biological_groups()
            if small_groups and not self._confirm_small_group_run(small_groups):
                return

        self._last_parameters = dict(params)
        self._start_processing(params)

    def run_processing(self, data: pd.DataFrame, **params) -> pd.DataFrame:
        """Run the feature filtering step."""
        result = feature_filter_adapter.run_from_df(
            data,
            background_threshold=params.get("background_threshold"),
            high_det_thresh=params.get("high_det_thresh"),
            low_det_thresh=params.get("low_det_thresh"),
            qc_ratio_threshold=params.get("qc_ratio_threshold"),
            intensity_fc_threshold=params.get("intensity_fc_threshold"),
            enable_background_threshold=params.get("enable_background_threshold", True),
            enable_qc_ratio_threshold=params.get("enable_qc_ratio_threshold", True),
            enable_intensity_fc_threshold=params.get("enable_intensity_fc_threshold", False),
            enable_mnar_gate=params.get("enable_mnar_gate", True),
            allow_single_group_stable=params.get("allow_single_group_stable", False),
            signal_threshold=params.get("signal_threshold", 5000),
            protected_rows=set(self.metadata.protected_rows or self.metadata.red_font_rows),
            progress_callback=self.update_progress,
        )

        if not result.success:
            raise Exception(result.error or "Processing failed")

        self._processing_result = result
        if result.statistics:
            self.log(f"Statistics: {result.statistics}")
            qc_n = result.statistics.get("qc_count", 0)
            if 0 < qc_n < 10:
                step_pct = round(100 / qc_n, 1)
                self.log(
                    f"[QC 提示] QC N={qc_n}（建議 ≥10）："
                    f"每缺失 1 筆 QC 樣本，ratio 下降 {step_pct}%"
                )
        self._last_metadata = {
            **result.metadata.as_context_dict(),
            "statistics": dict(result.statistics),
            "step_parameters": dict(params),
        }
        if result.data is None:
            raise Exception("Adapter returned no data")
        return result.data
