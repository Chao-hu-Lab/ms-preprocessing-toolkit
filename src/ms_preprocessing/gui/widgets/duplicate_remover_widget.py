"""Duplicate Remover Widget - GUI for Step 3."""

from __future__ import annotations

from typing import Callable, Optional
from tkinter import filedialog
import tkinter as tk

import customtkinter as ctk
import pandas as pd

from ms_preprocessing.adapters import duplicate_remover as duplicate_remover_adapter
from ms_preprocessing.gui.styles import FONTS, PADDING
from ms_preprocessing.gui.widgets.base_widget import BaseProcessingWidget


class DuplicateRemoverWidget(BaseProcessingWidget):
    """Widget for the Step 3 duplicate-removal and degeneracy-annotation step."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        step_index: int,
        on_load_file: Optional[Callable[[int], None]] = None,
        on_complete: Optional[Callable[[pd.DataFrame], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[float, str], None]] = None,
    ):
        self.enable_degeneracy_var = tk.BooleanVar(value=False)
        super().__init__(
            parent,
            title="Step 3: 重複訊號刪除與去冗餘標記 (Duplicate Removal & Degeneracy Annotation)",
            description=(
                "先依 m/z 與 RT 容差移除重複訊號，再可選擇依 adduct/isotope 規則標記可能來自同一代謝物的關聯特徵。"
            ),
            step_index=step_index,
            on_load_file=on_load_file,
            on_complete=on_complete,
            on_log=on_log,
            on_progress=on_progress,
        )

    def _browse_adduct_table(self) -> None:
        """Open a file dialog to select a custom adduct table."""
        filepath = filedialog.askopenfilename(
            title="選擇 adduct 規則表",
            filetypes=[
                ("Table files", "*.xlsx *.xls *.csv *.tsv *.txt"),
                ("Excel files", "*.xlsx *.xls"),
                ("CSV files", "*.csv"),
                ("All files", "*.*"),
            ],
        )
        if filepath:
            self.adduct_table_entry.delete(0, "end")
            self.adduct_table_entry.insert(0, filepath)

    def _create_parameters(self) -> None:
        """Create parameter inputs."""
        self._configure_form_grid()

        mz_label = ctk.CTkLabel(self.params_frame, text="m/z 容差 (ppm)", font=FONTS["body"])
        self._style_form_label(mz_label)
        mz_label.grid(row=0, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="e")

        self.mz_entry = ctk.CTkEntry(self.params_frame, placeholder_text="20", font=FONTS["body"])
        self._style_numeric_entry(self.mz_entry)
        self.mz_entry.insert(0, "20")
        self.mz_entry.grid(row=0, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        rt_label = ctk.CTkLabel(self.params_frame, text="RT 容差 (min)", font=FONTS["body"])
        self._style_form_label(rt_label)
        rt_label.grid(row=1, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="e")

        self.rt_entry = ctk.CTkEntry(self.params_frame, placeholder_text="1.0", font=FONTS["body"])
        self._style_numeric_entry(self.rt_entry)
        self.rt_entry.insert(0, "1.0")
        self.rt_entry.grid(row=1, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        topn_label = ctk.CTkLabel(self.params_frame, text="限制輸出 Top N", font=FONTS["body"])
        self._style_form_label(topn_label)
        topn_label.grid(row=2, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="e")

        self.topn_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="留空則不限制",
            font=FONTS["body"],
        )
        self._style_numeric_entry(self.topn_entry)
        self.topn_entry.grid(row=2, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        self.degeneracy_switch = ctk.CTkSwitch(
            self.params_frame,
            text="啟用去冗餘標記",
            variable=self.enable_degeneracy_var,
            onvalue=True,
            offvalue=False,
            font=FONTS["body"],
        )
        self._style_form_switch(self.degeneracy_switch)
        self.degeneracy_switch.grid(row=3, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        degeneracy_hint = ctk.CTkLabel(
            self.params_frame,
            text="只標記 adduct/isotope 關聯，不自動刪除",
            font=FONTS["small"],
            text_color="#a0a0a0",
        )
        degeneracy_hint.grid(row=3, column=1, columnspan=3, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        degeneracy_ppm_label = ctk.CTkLabel(
            self.params_frame,
            text="去冗餘 m/z 容差 (ppm)",
            font=FONTS["body"],
        )
        self._style_form_label(degeneracy_ppm_label)
        degeneracy_ppm_label.grid(row=4, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="e")

        self.degeneracy_ppm_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="20",
            font=FONTS["body"],
        )
        self._style_numeric_entry(self.degeneracy_ppm_entry)
        self.degeneracy_ppm_entry.insert(0, "20")
        self.degeneracy_ppm_entry.grid(row=4, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        degeneracy_rt_label = ctk.CTkLabel(
            self.params_frame,
            text="去冗餘 RT 容差 (min)",
            font=FONTS["body"],
        )
        self._style_form_label(degeneracy_rt_label)
        degeneracy_rt_label.grid(row=5, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="e")

        self.degeneracy_rt_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="0.05",
            font=FONTS["body"],
        )
        self._style_numeric_entry(self.degeneracy_rt_entry)
        self.degeneracy_rt_entry.insert(0, "0.05")
        self.degeneracy_rt_entry.grid(row=5, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        degeneracy_corr_label = ctk.CTkLabel(
            self.params_frame,
            text="Pearson r 門檻",
            font=FONTS["body"],
        )
        self._style_form_label(degeneracy_corr_label)
        degeneracy_corr_label.grid(row=6, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="e")

        self.degeneracy_corr_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="0.80",
            font=FONTS["body"],
        )
        self._style_numeric_entry(self.degeneracy_corr_entry)
        self.degeneracy_corr_entry.insert(0, "0.80")
        self.degeneracy_corr_entry.grid(row=6, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        degeneracy_min_points_label = ctk.CTkLabel(
            self.params_frame,
            text="最少共同樣本數",
            font=FONTS["body"],
        )
        self._style_form_label(degeneracy_min_points_label)
        degeneracy_min_points_label.grid(row=7, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="e")

        self.degeneracy_min_points_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="3",
            font=FONTS["body"],
        )
        self._style_numeric_entry(self.degeneracy_min_points_entry)
        self.degeneracy_min_points_entry.insert(0, "3")
        self.degeneracy_min_points_entry.grid(row=7, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        adduct_table_label = ctk.CTkLabel(
            self.params_frame,
            text="自訂 adduct 規則表",
            font=FONTS["body"],
        )
        self._style_form_label(adduct_table_label)
        adduct_table_label.grid(row=8, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="e")

        self.adduct_table_entry = ctk.CTkEntry(
            self.params_frame,
            placeholder_text="留空則使用內建規則表",
            font=FONTS["body"],
        )
        self.adduct_table_entry.grid(row=8, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="ew")

        self.adduct_table_button = ctk.CTkButton(
            self.params_frame,
            text="瀏覽",
            command=self._browse_adduct_table,
            width=120,
            font=FONTS["body"],
        )
        self.adduct_table_button.grid(row=8, column=2, padx=PADDING["small"], pady=PADDING["small"])

    def get_parameters(self) -> dict:
        """Get current parameter values."""
        params = {
            "mz_tolerance_ppm": float(self.mz_entry.get() or "20"),
            "rt_tolerance": float(self.rt_entry.get() or "1.0"),
            "preserve_red_font": True,
            "enable_degeneracy_annotation": bool(self.enable_degeneracy_var.get()),
            "degeneracy_ppm_tolerance": float(self.degeneracy_ppm_entry.get() or self.mz_entry.get() or "20"),
            "degeneracy_rt_tolerance": float(self.degeneracy_rt_entry.get() or "0.05"),
            "degeneracy_correlation_threshold": float(self.degeneracy_corr_entry.get() or "0.80"),
            "degeneracy_min_correlation_points": int(self.degeneracy_min_points_entry.get() or "3"),
        }

        topn_text = self.topn_entry.get().strip()
        if topn_text:
            try:
                params["top_n"] = int(topn_text)
            except ValueError:
                pass

        adduct_table_file = self.adduct_table_entry.get().strip()
        if adduct_table_file:
            params["degeneracy_adduct_table_file"] = adduct_table_file

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

        self.enable_degeneracy_var.set(bool(params.get("enable_degeneracy_annotation", False)))

        degeneracy_ppm = params.get("degeneracy_ppm_tolerance", params.get("mz_tolerance_ppm", 20.0))
        self.degeneracy_ppm_entry.delete(0, "end")
        self.degeneracy_ppm_entry.insert(0, str(degeneracy_ppm))

        degeneracy_rt = params.get("degeneracy_rt_tolerance", 0.05)
        self.degeneracy_rt_entry.delete(0, "end")
        self.degeneracy_rt_entry.insert(0, str(degeneracy_rt))

        degeneracy_corr = params.get("degeneracy_correlation_threshold", 0.8)
        self.degeneracy_corr_entry.delete(0, "end")
        self.degeneracy_corr_entry.insert(0, str(degeneracy_corr))

        degeneracy_min_points = params.get("degeneracy_min_correlation_points", 3)
        self.degeneracy_min_points_entry.delete(0, "end")
        self.degeneracy_min_points_entry.insert(0, str(degeneracy_min_points))

        adduct_table_file = params.get("degeneracy_adduct_table_file", "")
        self.adduct_table_entry.delete(0, "end")
        if adduct_table_file:
            self.adduct_table_entry.insert(0, str(adduct_table_file))

    def run_processing(self, data: pd.DataFrame, **params) -> pd.DataFrame:
        """Run the Step 3 duplicate-removal step."""
        protected_rows = set(
            self._context.get("protected_rows") or self._context.get("red_font_rows") or []
        )

        result = duplicate_remover_adapter.run_from_df(
            data,
            mz_tolerance_ppm=params.get("mz_tolerance_ppm"),
            rt_tolerance=params.get("rt_tolerance"),
            top_n=params.get("top_n"),
            protected_rows=protected_rows,
            enable_degeneracy_annotation=params.get("enable_degeneracy_annotation", False),
            degeneracy_ppm_tolerance=params.get("degeneracy_ppm_tolerance"),
            degeneracy_rt_tolerance=params.get("degeneracy_rt_tolerance"),
            degeneracy_correlation_threshold=params.get("degeneracy_correlation_threshold"),
            degeneracy_min_correlation_points=params.get("degeneracy_min_correlation_points"),
            degeneracy_adduct_table_file=params.get("degeneracy_adduct_table_file"),
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
