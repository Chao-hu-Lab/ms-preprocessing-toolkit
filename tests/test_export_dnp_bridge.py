"""Tests for xlsx materialization and DNP bridge integration."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType
from unittest.mock import Mock
import sys

import pandas as pd

from ms_preprocessing.gui.main_window import MainWindow


class _FakePipelineSession:
    def __init__(self, output_path: Path) -> None:
        self._output_path = output_path
        self.context = {
            "red_font_rows": set(),
            "protected_rows": set(),
            "blue_font_cells": [],
            "highlight_rows": set(),
            "sample_info": None,
            "deleted_feature_df": None,
            "metadata_refs": {
                "sample_info_ref": None,
                "deleted_feature_ref": None,
            },
        }

    def set_source_file(self, source_file: Path | None) -> None:
        _ = source_file

    def build_final_export_path(self, last_completed_step: int | None, last_run_all: bool, suffix: str = ".xlsx") -> Path:
        _ = (last_completed_step, last_run_all, suffix)
        return self._output_path

    def update_context_from_metadata(self, metadata: dict | None) -> None:
        _ = metadata


class _DummyButton:
    def __init__(self) -> None:
        self._text = "Export DNP"

    def cget(self, key: str):
        if key == "text":
            return self._text
        return None

    def configure(self, **kwargs) -> None:
        if "text" in kwargs:
            self._text = kwargs["text"]


def _make_window_for_export(tmp_dir: Path) -> MainWindow:
    window = MainWindow.__new__(MainWindow)
    window._output_dir = tmp_dir
    window._project_root = tmp_dir
    window._source_file = tmp_dir / "input.xlsx"
    window._last_completed_step = 3
    window._last_run_all = True
    window._current_step = 3
    window._current_data = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.0/1.0"], "S1": ["case", 123]})
    window._context = {
        "sample_info": None,
        "deleted_feature_df": None,
        "highlight_rows": set(),
        "blue_font_cells": [],
        "red_font_rows": set(),
    }
    step4_widget = Mock()
    step4_widget._export_deleted_var = Mock()
    step4_widget._export_deleted_var.get.return_value = False
    window.step_widgets = [Mock(), Mock(), Mock(), step4_widget]
    window._file_handler = Mock()
    window._log = lambda *_args, **_kwargs: None
    window.configure = lambda *_args, **_kwargs: None
    window.update_idletasks = lambda *_args, **_kwargs: None
    window._update_export_dnp_btn = lambda *_args, **_kwargs: None
    window._launch_dnp = lambda *_args, **_kwargs: None
    window.export_dnp_btn = _DummyButton()
    return window


def _clear_metabolomics_modules() -> None:
    for name in list(sys.modules):
        if name == "metabolomics" or name.startswith("metabolomics."):
            sys.modules.pop(name, None)


def test_dnp_bridge_always_receives_xlsx_even_when_intermediates_are_parquet(monkeypatch, project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        window = _make_window_for_export(base)
        parquet_step4 = base / "STEP4_input.parquet"
        parquet_step4.write_text("placeholder", encoding="utf-8")
        window._step_output_paths = {3: parquet_step4}
        window._pipeline_session = _FakePipelineSession(output_path=base / "ALL_input.xlsx")
        window._file_handler.save_data.return_value = base / "ALL_input.xlsx"

        captured: dict[str, str] = {}

        def _fake_convert(source: str, target: str) -> str:
            captured["source"] = source
            captured["target"] = target
            return target

        pkg_metabolomics = ModuleType("metabolomics")
        pkg_adapters = ModuleType("metabolomics.adapters")
        mod_bridge = ModuleType("metabolomics.adapters.preprocessing_to_dnp")
        mod_bridge.convert_preprocessing_to_dnp = _fake_convert
        monkeypatch.setitem(sys.modules, "metabolomics", pkg_metabolomics)
        monkeypatch.setitem(sys.modules, "metabolomics.adapters", pkg_adapters)
        monkeypatch.setitem(sys.modules, "metabolomics.adapters.preprocessing_to_dnp", mod_bridge)

        out_path = base / "dnp.xlsx"
        monkeypatch.setattr("ms_preprocessing.gui.event_handlers.filedialog.asksaveasfilename", lambda **_k: str(out_path))
        monkeypatch.setattr("ms_preprocessing.gui.event_handlers.messagebox.showinfo", lambda *_a, **_k: None)
        monkeypatch.setattr("ms_preprocessing.gui.event_handlers.messagebox.showerror", lambda *_a, **_k: None)
        monkeypatch.setattr("ms_preprocessing.gui.event_handlers.messagebox.showwarning", lambda *_a, **_k: None)
        monkeypatch.setattr(
            "ms_preprocessing.gui.event_handlers.MainWindowEventHandlersMixin._open_file_in_system_app",
            lambda *_a, **_k: None,
        )
        monkeypatch.setattr(
            "ms_preprocessing.gui.event_handlers.ensure_dnp_bridge_on_path",
            lambda *_a, **_k: base / "fake-dnp" / "src",
        )

        window._export_to_dnp()

        assert captured["source"].endswith(".xlsx")


def test_final_export_materializes_xlsx_from_parquet_intermediate(project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        window = _make_window_for_export(base)
        window._current_data = None
        parquet_step4 = base / "STEP4_input.parquet"
        parquet_step4.write_text("placeholder", encoding="utf-8")
        window._step_output_paths = {3: parquet_step4}
        window._pipeline_session = _FakePipelineSession(output_path=base / "ALL_input.xlsx")

        df_from_parquet = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.0/1.0"], "S1": ["case", 999]})
        window._file_handler.load_data.return_value = (df_from_parquet, {"format": "parquet"})

        saved: dict[str, Path] = {}
        saved_kwargs: dict = {}

        def _save_data(df, file_path, **kwargs):
            _ = df
            saved["path"] = Path(file_path)
            saved_kwargs.update(kwargs)
            return Path(file_path)

        window._file_handler.save_data.side_effect = _save_data

        window._export_results()

        assert saved["path"].suffix == ".xlsx"
        assert saved_kwargs.get("save_parquet_cache") is False


def test_sample_info_requires_user_completion_detects_missing_batch_and_dna(tmp_path) -> None:
    bridge_path = tmp_path / "bridge.xlsx"

    # Missing values → needs completion
    with pd.ExcelWriter(bridge_path) as writer:
        pd.DataFrame({
            "Sample_Name": ["S1", "S2"],
            "Sample_Type": ["Exposure", "Control"],
            "Batch": [None, "B1"],
            "DNA_mg/20uL": [None, None],
        }).to_excel(writer, sheet_name="SampleInfo", index=False)

    window = MainWindow.__new__(MainWindow)
    assert window._sample_info_requires_user_completion(bridge_path) is True

    # All filled → no completion needed
    with pd.ExcelWriter(bridge_path) as writer:
        pd.DataFrame({
            "Sample_Name": ["S1", "S2"],
            "Sample_Type": ["Exposure", "Control"],
            "Batch": ["B1", "B1"],
            "DNA_mg/20uL": [1.25, 0.98],
        }).to_excel(writer, sheet_name="SampleInfo", index=False)

    assert window._sample_info_requires_user_completion(bridge_path) is False


def test_sample_info_requires_completion_when_column_missing(tmp_path) -> None:
    bridge_path = tmp_path / "bridge.xlsx"
    with pd.ExcelWriter(bridge_path) as writer:
        pd.DataFrame({
            "Sample_Name": ["S1"],
            "Sample_Type": ["Exposure"],
            # No Batch, no DNA_mg/20uL columns
        }).to_excel(writer, sheet_name="SampleInfo", index=False)

    window = MainWindow.__new__(MainWindow)
    assert window._sample_info_requires_user_completion(bridge_path) is True


def test_sample_info_requires_completion_when_file_unreadable(tmp_path) -> None:
    window = MainWindow.__new__(MainWindow)
    assert window._sample_info_requires_user_completion(tmp_path / "nonexistent.xlsx") is True


def test_export_to_dnp_shows_completion_warning_when_sample_info_incomplete(
    monkeypatch, project_temp_dir
) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        window = _make_window_for_export(base)
        step4_xlsx = base / "STEP4_input.xlsx"
        step4_xlsx.write_text("placeholder", encoding="utf-8")
        window._step_output_paths = {3: step4_xlsx}
        window._pipeline_session = _FakePipelineSession(output_path=base / "ALL_input.xlsx")
        window._file_handler.save_data.return_value = base / "ALL_input.xlsx"

        # Bridge file has incomplete SampleInfo (no Batch/DNA columns)
        out_path = base / "dnp.xlsx"
        with pd.ExcelWriter(out_path) as writer:
            pd.DataFrame({"Sample_Name": ["S1"]}).to_excel(
                writer, sheet_name="SampleInfo", index=False
            )

        monkeypatch.setattr(
            "ms_preprocessing.gui.event_handlers.filedialog.asksaveasfilename",
            lambda **_k: str(out_path),
        )
        shown_messages: list[str] = []
        monkeypatch.setattr(
            "ms_preprocessing.gui.event_handlers.messagebox.showinfo",
            lambda title, msg, **_k: shown_messages.append(msg),
        )
        monkeypatch.setattr("ms_preprocessing.gui.event_handlers.messagebox.showerror", lambda *_a, **_k: None)
        monkeypatch.setattr("ms_preprocessing.gui.event_handlers.messagebox.showwarning", lambda *_a, **_k: None)
        monkeypatch.setattr(
            "ms_preprocessing.gui.event_handlers.MainWindowEventHandlersMixin._open_file_in_system_app",
            lambda *_a, **_k: None,
        )
        monkeypatch.setattr(
            "ms_preprocessing.gui.event_handlers.ensure_dnp_bridge_on_path",
            lambda *_a, **_k: base / "fake-dnp" / "src",
        )

        mod_bridge = ModuleType("metabolomics.adapters.preprocessing_to_dnp")
        mod_bridge.convert_preprocessing_to_dnp = lambda source, target: str(out_path)
        monkeypatch.setitem(sys.modules, "metabolomics", ModuleType("metabolomics"))
        monkeypatch.setitem(sys.modules, "metabolomics.adapters", ModuleType("metabolomics.adapters"))
        monkeypatch.setitem(sys.modules, "metabolomics.adapters.preprocessing_to_dnp", mod_bridge)

        window._export_to_dnp()

        assert any("Batch" in msg and "DNA_mg/20uL" in msg for msg in shown_messages)


def test_export_to_dnp_uses_dnp_src_override(monkeypatch, project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        window = _make_window_for_export(base)
        step4_xlsx = base / "STEP4_input.xlsx"
        step4_xlsx.write_text("placeholder", encoding="utf-8")
        window._step_output_paths = {3: step4_xlsx}
        window._pipeline_session = _FakePipelineSession(output_path=base / "ALL_input.xlsx")
        window._file_handler.save_data.return_value = base / "ALL_input.xlsx"

        dnp_src = base / "external-dnp" / "src"
        bridge_module = dnp_src / "metabolomics" / "adapters" / "preprocessing_to_dnp.py"
        bridge_module.parent.mkdir(parents=True, exist_ok=True)
        (dnp_src / "metabolomics" / "__init__.py").write_text("", encoding="utf-8")
        (dnp_src / "metabolomics" / "adapters" / "__init__.py").write_text("", encoding="utf-8")
        bridge_module.write_text(
            "def convert_preprocessing_to_dnp(source, target):\n"
            "    return target\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("MSPTK_DNP_SRC", str(dnp_src))
        monkeypatch.setattr(sys, "path", list(sys.path))
        _clear_metabolomics_modules()

        out_path = base / "dnp.xlsx"
        monkeypatch.setattr("ms_preprocessing.gui.event_handlers.filedialog.asksaveasfilename", lambda **_k: str(out_path))
        monkeypatch.setattr("ms_preprocessing.gui.event_handlers.messagebox.showinfo", lambda *_a, **_k: None)
        monkeypatch.setattr("ms_preprocessing.gui.event_handlers.messagebox.showerror", lambda *_a, **_k: None)
        monkeypatch.setattr("ms_preprocessing.gui.event_handlers.messagebox.showwarning", lambda *_a, **_k: None)
        monkeypatch.setattr(
            "ms_preprocessing.gui.event_handlers.MainWindowEventHandlersMixin._open_file_in_system_app",
            lambda *_a, **_k: None,
        )

        window._export_to_dnp()

        assert str(dnp_src) in sys.path


def test_export_to_dnp_shows_error_when_dnp_project_not_found(monkeypatch, project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        window = _make_window_for_export(base)
        step4_xlsx = base / "STEP4_input.xlsx"
        step4_xlsx.write_text("placeholder", encoding="utf-8")
        window._step_output_paths = {3: step4_xlsx}
        window._pipeline_session = _FakePipelineSession(output_path=base / "ALL_input.xlsx")

        monkeypatch.setattr("ms_preprocessing.gui.event_handlers.ensure_dnp_bridge_on_path", lambda *_a, **_k: None)
        monkeypatch.setattr(
            "ms_preprocessing.gui.event_handlers.filedialog.asksaveasfilename",
            lambda **_k: str(base / "dnp.xlsx"),
        )
        shown_errors: list[str] = []
        monkeypatch.setattr(
            "ms_preprocessing.gui.event_handlers.messagebox.showerror",
            lambda title, msg, **_k: shown_errors.append(msg),
        )
        monkeypatch.setattr("ms_preprocessing.gui.event_handlers.messagebox.showinfo", lambda *_a, **_k: None)
        monkeypatch.setattr("ms_preprocessing.gui.event_handlers.messagebox.showwarning", lambda *_a, **_k: None)

        _clear_metabolomics_modules()
        window._export_to_dnp()

        assert any("Could not find the DNP adapter module." in msg for msg in shown_errors)


def test_export_to_dnp_shows_error_when_bridge_module_missing(monkeypatch, project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        window = _make_window_for_export(base)
        step4_xlsx = base / "STEP4_input.xlsx"
        step4_xlsx.write_text("placeholder", encoding="utf-8")
        window._step_output_paths = {3: step4_xlsx}
        window._pipeline_session = _FakePipelineSession(output_path=base / "ALL_input.xlsx")

        dnp_src = base / "external-dnp" / "src"
        (dnp_src / "metabolomics").mkdir(parents=True, exist_ok=True)
        (dnp_src / "metabolomics" / "__init__.py").write_text("", encoding="utf-8")
        monkeypatch.setenv("MSPTK_DNP_SRC", str(dnp_src))
        _clear_metabolomics_modules()

        shown_errors: list[str] = []
        monkeypatch.setattr(
            "ms_preprocessing.gui.event_handlers.filedialog.asksaveasfilename",
            lambda **_k: str(base / "dnp.xlsx"),
        )
        monkeypatch.setattr(
            "ms_preprocessing.gui.event_handlers.messagebox.showerror",
            lambda title, msg, **_k: shown_errors.append(msg),
        )
        monkeypatch.setattr("ms_preprocessing.gui.event_handlers.messagebox.showinfo", lambda *_a, **_k: None)
        monkeypatch.setattr("ms_preprocessing.gui.event_handlers.messagebox.showwarning", lambda *_a, **_k: None)

        window._export_to_dnp()

        assert any("Could not find the DNP adapter module." in msg for msg in shown_errors)


def test_launch_dnp_uses_discovered_main_module(monkeypatch, project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        window = _make_window_for_export(base)
        window._launch_dnp = MainWindow._launch_dnp.__get__(window, MainWindow)
        main_py = base / "external-dnp" / "src" / "metabolomics" / "__main__.py"
        main_py.parent.mkdir(parents=True, exist_ok=True)
        main_py.write_text("print('ok')", encoding="utf-8")

        launched: dict[str, object] = {}

        monkeypatch.setattr("ms_preprocessing.gui.event_handlers.find_dnp_main_module", lambda *_a, **_k: main_py)
        monkeypatch.setattr(
            "ms_preprocessing.gui.event_handlers.subprocess.Popen",
            lambda cmd, cwd: launched.update({"cmd": cmd, "cwd": cwd}),
        )

        window._launch_dnp()

        assert launched["cmd"] == [sys.executable, "-m", "metabolomics"]
        assert launched["cwd"] == str(main_py.parent.parent)

