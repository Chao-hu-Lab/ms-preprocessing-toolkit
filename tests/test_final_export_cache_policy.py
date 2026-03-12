"""Tests for final export parquet-cache policy."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd

from ms_preprocessing.gui.main_window import MainWindow
from ms_preprocessing.main import run_cli


class _FakeResult:
    def __init__(self, data: pd.DataFrame, metadata: dict | None = None) -> None:
        self.success = True
        self.data = data
        self.message = ""
        self.statistics = {}
        self.metadata = metadata or {}


class _DummyDataOrganizer:
    def process(self, data: pd.DataFrame, **kwargs) -> _FakeResult:
        _ = kwargs
        return _FakeResult(data.copy(), metadata={"sample_info": None})


class _DummyISTDMarker:
    def __init__(self) -> None:
        self.config = SimpleNamespace(default_ppm_tolerance=20.0, default_rt_tolerance=1.0)

    def process(self, data: pd.DataFrame, **kwargs) -> _FakeResult:
        _ = kwargs
        return _FakeResult(data.copy(), metadata={"red_font_rows": [], "protected_rows": []})


class _DummyDuplicateRemover:
    def process(self, data: pd.DataFrame, **kwargs) -> _FakeResult:
        _ = kwargs
        return _FakeResult(data.copy(), metadata={"red_font_rows": [], "protected_rows": []})


class _DummyFeatureFilter:
    def process(self, data: pd.DataFrame, **kwargs) -> _FakeResult:
        _ = kwargs
        return _FakeResult(
            data.copy(),
            metadata={
                "red_font_rows": [],
                "protected_rows": [],
                "blue_font_cells": [],
                "deleted_features": [],
            },
        )


class _FakeFileHandler:
    def __init__(self, input_df: pd.DataFrame) -> None:
        self._input_df = input_df
        self.calls: list[tuple[str, Path, dict]] = []

    def load_data(self, file_path, sheet_name=0, header_row=0):
        _ = (sheet_name, header_row)
        return self._input_df.copy(), {"format": "csv", "red_font_rows": []}

    def save_data(self, df, file_path, **kwargs):
        _ = df
        path = Path(file_path)
        self.calls.append(("save", path, kwargs))
        return path


def _make_cli_args(input_path: Path, output_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        input=str(input_path),
        output=str(output_path),
        method_file=None,
        step="all",
        mz_tol=20.0,
        istd_mz=None,
        istd_record_file=None,
        istd_record_date=None,
        rt_tol=1.0,
        bg_threshold=0.33,
        skew_threshold=0.66,
        diff_threshold=0.30,
        qc_ratio_threshold=0.0,
        persist_intermediate=False,
        no_gui=True,
        version=False,
    )


def _patch_cli_dependencies(monkeypatch, fake_handler: _FakeFileHandler) -> None:
    import ms_core.utils.file_handler as file_handler_module
    import ms_core.preprocessing.data_organizer as organizer_module
    import ms_core.preprocessing.istd_marker as istd_module
    import ms_core.preprocessing.duplicate_remover as duplicate_module
    import ms_core.preprocessing.ms_quality_filter as filter_module

    monkeypatch.setattr(file_handler_module, "FileHandler", lambda: fake_handler)
    monkeypatch.setattr(organizer_module, "DataOrganizer", _DummyDataOrganizer)
    monkeypatch.setattr(istd_module, "ISTDMarker", _DummyISTDMarker)
    monkeypatch.setattr(duplicate_module, "DuplicateRemover", _DummyDuplicateRemover)
    monkeypatch.setattr(filter_module, "FeatureFilter", _DummyFeatureFilter)


def test_cli_final_xlsx_save_does_not_request_parquet_cache_by_default(monkeypatch, project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        df = pd.DataFrame(
            {
                "Mz/RT": ["Sample_Type", "100.1/1.0"],
                "Tolerance": ["na", "na"],
                "Case1": ["case", 1000],
                "Control1": ["control", 1200],
                "QC1": ["qc", 1100],
            }
        )
        input_path = base / "input.csv"
        df.to_csv(input_path, index=False)
        output_path = base / "final.xlsx"
        fake_handler = _FakeFileHandler(input_df=df)
        _patch_cli_dependencies(monkeypatch, fake_handler)

        rc = run_cli(_make_cli_args(input_path=input_path, output_path=output_path))
        assert rc == 0
        last_save = [call for call in fake_handler.calls if call[1].suffix.lower() == ".xlsx"][-1]
        assert last_save[2].get("save_parquet_cache") is False


def test_gui_final_export_does_not_request_parquet_cache_by_default(project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        window = MainWindow.__new__(MainWindow)
        window._output_dir = base
        window._project_root = base
        window._source_file = base / "input.xlsx"
        window._last_completed_step = 3
        window._last_run_all = True
        window._current_data = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.0/1.0"], "S1": ["case", 123]})
        window._context = {
            "sample_info": None,
            "deleted_feature_df": None,
            "highlight_rows": set(),
            "blue_font_cells": [],
            "red_font_rows": set(),
        }
        window._pipeline_session = Mock()
        window._pipeline_session.build_final_export_path.return_value = base / "ALL_input.xlsx"
        window._pipeline_session.set_source_file.return_value = None
        window._file_handler = Mock()
        window._log = lambda *_args, **_kwargs: None

        out = window._export_results()
        assert out is not None
        kwargs = window._file_handler.save_data.call_args.kwargs
        assert kwargs.get("save_parquet_cache") is False
