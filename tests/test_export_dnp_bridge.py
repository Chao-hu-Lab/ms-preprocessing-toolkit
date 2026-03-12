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
    window._file_handler = Mock()
    window._log = lambda *_args, **_kwargs: None
    window.configure = lambda *_args, **_kwargs: None
    window.update_idletasks = lambda *_args, **_kwargs: None
    window._update_export_dnp_btn = lambda *_args, **_kwargs: None
    window._launch_dnp = lambda *_args, **_kwargs: None
    window.export_dnp_btn = _DummyButton()
    return window


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
        monkeypatch.setattr("ms_preprocessing.gui.main_window.filedialog.asksaveasfilename", lambda **_k: str(out_path))
        monkeypatch.setattr("ms_preprocessing.gui.main_window.messagebox.askyesno", lambda *_a, **_k: False)
        monkeypatch.setattr("ms_preprocessing.gui.main_window.messagebox.showerror", lambda *_a, **_k: None)
        monkeypatch.setattr("ms_preprocessing.gui.main_window.messagebox.showwarning", lambda *_a, **_k: None)

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
