"""Regression tests for GUI sidebar workflow labels."""

from __future__ import annotations

import customtkinter as ctk

from ms_preprocessing.gui.layout import MainWindowLayoutMixin


class _SidebarHarness(MainWindowLayoutMixin, ctk.CTkFrame):
    def __init__(self, master) -> None:
        super().__init__(master)
        self._current_step = 0
        self._completed_steps = set()
        self._step_output_paths = {}
        self._context = {}
        self._create_sidebar()

    def _switch_step(self, step_index: int) -> None:
        self._current_step = step_index

    def _export_results(self):
        return None

    def _open_output_folder(self) -> None:
        return None

    def _run_all_steps(self) -> None:
        return None

    def _export_to_dnp(self) -> None:
        return None


def test_main_window_sidebar_uses_expected_workflow_labels(ctk_root) -> None:
    app = _SidebarHarness(ctk_root)
    app.pack()
    ctk_root.update_idletasks()
    try:
        assert [btn.cget("text") for btn in app.step_buttons] == [
            "1. 資料整理",
            "2. ISTD 標記",
            "3. 重複訊號刪除",
            "4. 篩選與缺失值填補",
        ]
    finally:
        app.destroy()


def test_main_window_sidebar_exposes_run_all_profile_selector(ctk_root) -> None:
    app = _SidebarHarness(ctk_root)
    app.pack()
    ctk_root.update_idletasks()
    try:
        assert app.pipeline_preset_label.cget("text") == "Run All Preset"
        assert app.run_all_profile_var.get() == "default"
        assert app.run_all_profile_menu.cget("values") == ["loose", "default", "strict"]
        assert app.run_all_btn.cget("text") == "Run All"
        assert app.open_output_folder_btn.cget("fg_color") == "#16213e"
        assert app.open_output_folder_btn.cget("border_width") == 1
    finally:
        app.destroy()
