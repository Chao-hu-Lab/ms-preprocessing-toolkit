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


class _ContentAreaHarness(MainWindowLayoutMixin, ctk.CTkFrame):
    def __init__(self, master) -> None:
        super().__init__(master)
        self._current_step = 0
        self._completed_steps = set()
        self._step_output_paths = {}
        self._context = {}
        self._create_content_area()

    def _load_file_for_step(self, step_index: int) -> None:
        self._current_step = step_index

    def _on_step_complete(self, *_args, **_kwargs) -> None:
        return None

    def _log(self, _message: str) -> None:
        return None

    def _update_action_bar_progress(self, _value: float, _status: str = "") -> None:
        return None

    def _run_current_step(self) -> None:
        return None

    def _reset_current_step(self) -> None:
        return None

    def _clear_log(self) -> None:
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
            "4. 特徵篩選",
        ]
    finally:
        app.destroy()


def test_main_window_sidebar_exposes_run_all_profile_selector(ctk_root) -> None:
    app = _SidebarHarness(ctk_root)
    app.pack()
    ctk_root.update_idletasks()
    try:
        assert app.sidebar_title_label.cget("text") == "MS Preprocessing Toolkit"
        assert "\n" not in app.sidebar_title_label.cget("text")
        assert app.sidebar.cget("fg_color") == "#1E1E1E"
        assert app.pipeline_preset_label.cget("text") == "Run All Preset"
        assert app.run_all_profile_var.get() == "default"
        assert app.run_all_profile_menu.cget("values") == ["loose", "default", "strict"]
        assert app.run_all_btn.cget("text") == "Run All"
        assert app.run_all_btn.cget("fg_color") == "#2E8B57"
        assert app.export_results_btn.cget("text") == "Export Results"
        assert app.open_output_folder_btn.cget("text") == "Open Output Folder"
        assert app.open_output_folder_btn.cget("fg_color") == "#333333"
        assert app.open_output_folder_btn.cget("border_width") == 1
        assert app.export_dnp_btn.cget("state") == "disabled"
        assert app.export_dnp_btn.cget("fg_color") == "transparent"
    finally:
        app.destroy()


def test_content_area_prioritizes_step_panel_height_over_bottom_log(ctk_root) -> None:
    app = _ContentAreaHarness(ctk_root)
    app.pack(fill="both", expand=True)
    ctk_root.update_idletasks()
    try:
        assert app.content_frame.grid_rowconfigure(0)["weight"] == 1
        assert app.content_frame.grid_rowconfigure(1)["weight"] == 0
        assert app.main_frame.grid_info()["sticky"] == "nesw"
    finally:
        app.destroy()


def test_action_button_theme_restores_hover_after_disabled_state(ctk_root) -> None:
    app = _SidebarHarness(ctk_root)
    app.pack()
    ctk_root.update_idletasks()
    try:
        app._apply_action_button_theme(app.export_dnp_btn, "disabled")
        assert app.export_dnp_btn.cget("hover") is False

        app._apply_action_button_theme(app.export_dnp_btn, "secondary")
        assert app.export_dnp_btn.cget("hover") is True
    finally:
        app.destroy()
