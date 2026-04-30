"""Tests for final xlsx materialization and downstream handoff reminders."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pandas as pd

from ms_preprocessing.gui.main_window import MainWindow
from ms_preprocessing.utils.results import ProcessingMetadata


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
        self.metadata = ProcessingMetadata()

    def set_source_file(self, source_file: Path | None) -> None:
        _ = source_file

    def build_final_export_path(
        self,
        last_completed_step: int | None,
        last_run_all: bool,
        suffix: str = ".xlsx",
    ) -> Path:
        _ = (last_completed_step, last_run_all, suffix)
        return self._output_path

    def update_context_from_metadata(self, metadata: dict | None) -> None:
        _ = metadata


def _make_window_for_export(tmp_dir: Path) -> tuple[MainWindow, list[str]]:
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
    window.configure = lambda *_args, **_kwargs: None
    window._update_run_context_summary = lambda *_args, **_kwargs: None
    logs: list[str] = []
    window._log = logs.append
    return window, logs


def test_final_export_materializes_xlsx_from_parquet_intermediate(project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        window, _logs = _make_window_for_export(base)
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


def test_final_export_logs_downstream_handoff_reminder_after_step4(project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        window, logs = _make_window_for_export(base)
        window._step_output_paths = {}
        window._pipeline_session = _FakePipelineSession(output_path=base / "ALL_input.xlsx")

        saved: dict[str, Path] = {}

        def _save_data(df, file_path, **kwargs):
            _ = (df, kwargs)
            saved["path"] = Path(file_path)
            return Path(file_path)

        window._file_handler.save_data.side_effect = _save_data

        result = window._export_results()

        assert result == saved["path"]
        assert any("Step 4 final xlsx 已完成" in message for message in logs)
        assert any("不會再另外產生 DNP bridge 檔或啟動 DNP" in message for message in logs)
        assert any("SampleInfo" in message and "Batch" in message for message in logs)
        assert all("DNA_mg/20uL" not in message for message in logs)


def test_final_export_does_not_log_downstream_reminder_before_step4(project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        window, logs = _make_window_for_export(base)
        window._last_completed_step = 1
        window._step_output_paths = {}
        window._pipeline_session = _FakePipelineSession(output_path=base / "STEP2_input.xlsx")

        window._file_handler.save_data.side_effect = lambda df, file_path, **_kwargs: Path(file_path)

        window._export_results()

        assert not any("Step 4 final xlsx 已完成" in message for message in logs)
