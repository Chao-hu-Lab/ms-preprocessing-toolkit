"""Tests for final export parquet-cache policy."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd

from ms_preprocessing.gui.main_window import MainWindow
from ms_preprocessing.main import run_cli
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult


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
        profile="default",
        method_file=None,
        step="all",
        mz_tol=None,
        istd_mz=None,
        istd_record_file=None,
        istd_record_date=None,
        rt_tol=None,
        bg_threshold=None,
        intensity_fc_threshold=None,
        diff_threshold=None,
        qc_ratio_threshold=None,
        persist_intermediate=False,
        no_gui=True,
        version=False,
    )


def _patch_cli_dependencies(monkeypatch, fake_handler: _FakeFileHandler) -> None:
    import ms_preprocessing.adapters.data_organizer as organizer_module
    import ms_preprocessing.adapters.istd_marker as istd_module
    import ms_preprocessing.adapters.duplicate_remover as duplicate_module
    import ms_preprocessing.adapters.feature_filter as filter_module
    import ms_preprocessing.utils.file_handler as file_handler_module

    monkeypatch.setattr(file_handler_module, "FileHandler", lambda: fake_handler)
    monkeypatch.setattr(
        organizer_module,
        "run_from_df",
        lambda data, **kwargs: ProcessingResult(
            success=True,
            step="data_organizer",
            output_path=None,
            data=data.copy(),
            metadata=ProcessingMetadata(sample_info=None),
        ),
    )
    monkeypatch.setattr(
        istd_module,
        "run_from_df",
        lambda data, **kwargs: ProcessingResult(
            success=True,
            step="istd_marker",
            output_path=None,
            data=data.copy(),
            metadata=ProcessingMetadata(red_font_rows=set(), protected_rows=set()),
        ),
    )
    monkeypatch.setattr(
        duplicate_module,
        "run_from_df",
        lambda data, **kwargs: ProcessingResult(
            success=True,
            step="duplicate_remover",
            output_path=None,
            data=data.copy(),
            metadata=ProcessingMetadata(red_font_rows=set(), protected_rows=set()),
        ),
    )
    monkeypatch.setattr(
        filter_module,
        "run_from_df",
        lambda data, **kwargs: ProcessingResult(
            success=True,
            step="feature_filter",
            output_path=None,
            data=data.copy(),
            metadata=ProcessingMetadata(
                red_font_rows=set(),
                protected_rows=set(),
                blue_font_cells=[],
                deleted_feature_df=None,
            ),
        ),
    )


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
        step4_widget = Mock()
        step4_widget._export_deleted_var = Mock()
        step4_widget._export_deleted_var.get.return_value = False
        window.step_widgets = [Mock(), Mock(), Mock(), step4_widget]
        window._file_handler = Mock()
        window._log = lambda *_args, **_kwargs: None

        out = window._export_results()
        assert out is not None
        kwargs = window._file_handler.save_data.call_args.kwargs
        assert kwargs.get("save_parquet_cache") is False


def test_gui_final_export_uses_live_pipeline_session_context_when_window_alias_is_stale(project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        sample_info = pd.DataFrame({"Sample_Name": ["S1"]})
        deleted_feature = pd.DataFrame({"Feature": ["F1"]})

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
        window._pipeline_session.context = {
            "sample_info": sample_info,
            "deleted_feature_df": deleted_feature,
            "highlight_rows": {7},
            "blue_font_cells": ["C3"],
            "red_font_rows": {5},
        }
        step4_widget = Mock()
        step4_widget._export_deleted_var = Mock()
        step4_widget._export_deleted_var.get.return_value = True
        window.step_widgets = [Mock(), Mock(), Mock(), step4_widget]
        window._file_handler = Mock()
        window._log = lambda *_args, **_kwargs: None

        out = window._export_results()

        assert out is not None
        kwargs = window._file_handler.save_data.call_args.kwargs
        assert kwargs["highlight_rows"] == {7}
        assert kwargs["blue_font_cells"] == ["C3"]
        assert kwargs["red_font_rows"] == {5}
        assert kwargs["extra_sheets"]["SampleInfo"] is sample_info
        assert kwargs["extra_sheets"]["deleted_feature"] is deleted_feature
