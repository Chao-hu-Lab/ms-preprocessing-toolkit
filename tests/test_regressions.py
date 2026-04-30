"""Regression tests for issues found during project review."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
from ms_core.preprocessing.duplicate_remover import DuplicateRemover

from ms_preprocessing.gui.main_window import MainWindow
from ms_preprocessing.gui.pipeline_session import PipelineSession
from ms_preprocessing.utils.file_handler import FileHandler


def test_duplicate_remover_handles_cross_rt_bin_duplicates() -> None:
    """Rows within RT tolerance must be deduplicated across RT bin boundaries."""
    df = pd.DataFrame(
        {
            "Mz/RT": ["Sample_Type", "100.0000/1.99", "100.0005/2.02"],
            "S1": ["case", 10000, 9000],
            "S2": ["case", 11000, 8000],
        }
    )

    remover = DuplicateRemover()
    result = remover.process(df, mz_tolerance_ppm=20.0, rt_tolerance=1.0)

    assert result.success
    assert result.data is not None
    assert len(result.data) - 1 == 1


def test_save_data_with_parquet_cache_does_not_break_excel_export() -> None:
    """Parquet cache failures should not abort the primary save flow."""
    df = pd.DataFrame(
        {
            "Mz/RT": ["Sample_Type", "100.0/1.0"],
            "S1": ["case", 123],  # mixed object dtype column
        }
    )
    out_path = Path("cache_test.xlsx")

    handler = FileHandler()
    with (
        patch.object(handler, "_save_excel", return_value=None),
        patch.object(handler, "_save_parquet_cache", side_effect=RuntimeError("parquet failed")),
    ):
        result_path = handler.save_data(
            df,
            out_path,
            sheet_name="RawIntensity",
            red_font_rows={1},
            save_parquet_cache=True,
        )

    assert result_path == out_path


def test_load_data_preserves_red_font_rows_from_cache_or_excel() -> None:
    """Red font metadata should survive load path regardless of cache usage."""
    handler = FileHandler()
    fake_df = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.0/1.0"], "S1": ["case", "123"]})
    fake_meta = {"red_font_rows": [1], "blue_font_cells": [], "highlight_rows": []}

    with (
        patch("ms_preprocessing.utils.file_handler.Settings.SAVE_PARQUET_CACHE", True),
        patch.object(handler, "_resolve_parquet_cache", return_value=Path("cache.parquet")),
        patch("pathlib.Path.exists", return_value=True),
        patch("pandas.read_parquet", return_value=fake_df),
        patch.object(handler, "_load_parquet_meta", return_value=fake_meta),
    ):
        _, metadata = handler.load_data("input.xlsx")

    assert metadata.get("format") == "parquet"
    assert metadata.get("red_font_rows") == [1]


def test_intermediate_steps_autosave_as_parquet(project_temp_dir) -> None:
    with project_temp_dir(prefix="regression-autosave-") as temp_dir:
        with patch.dict("os.environ", {"MSPTK_PARQUET_CACHE_ROOT": str(temp_dir / "cache")}):
            window = MainWindow.__new__(MainWindow)
            window._output_dir = Path("OUTPUT") / "autosave-test"
            window._source_file = Path("input.xlsx")
            window._pipeline_session = PipelineSession(
                output_dir=window._output_dir,
                source_file=window._source_file,
            )
            window._step_output_paths = window._pipeline_session.step_output_paths
            window._context = {
                "sample_info": None,
                "deleted_feature_df": None,
                "highlight_rows": set(),
                "blue_font_cells": [],
                "red_font_rows": set(),
            }
            window._file_handler = Mock()
            window._log = lambda _: None

            data = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.0/1.0"], "S1": ["case", 123]})
            output_path = window._save_step_output(0, data)

            assert output_path is not None
            assert output_path.suffix == ".parquet"
            assert window._output_dir not in output_path.parents


def test_step4_autosave_uses_parquet_intermediate(project_temp_dir) -> None:
    with project_temp_dir(prefix="regression-step4-") as temp_dir:
        with patch.dict("os.environ", {"MSPTK_PARQUET_CACHE_ROOT": str(temp_dir / "cache")}):
            window = MainWindow.__new__(MainWindow)
            window._output_dir = Path("OUTPUT") / "autosave-test"
            window._source_file = Path("input.xlsx")
            window._pipeline_session = PipelineSession(
                output_dir=window._output_dir,
                source_file=window._source_file,
            )
            window._step_output_paths = window._pipeline_session.step_output_paths
            window._context = {
                "sample_info": None,
                "deleted_feature_df": None,
                "highlight_rows": set(),
                "blue_font_cells": [],
                "red_font_rows": set(),
            }
            window._file_handler = Mock()
            window._log = lambda _: None

            data = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.0/1.0"], "S1": ["case", 123]})
            output_path = window._save_step_output(3, data)

            assert output_path is not None
            assert output_path.suffix == ".parquet"
            assert window._output_dir not in output_path.parents


def test_output_directory_contains_only_user_deliverables_after_step_autosave(project_temp_dir) -> None:
    with project_temp_dir(prefix="regression-deliverables-") as temp_dir:
        with patch.dict("os.environ", {"MSPTK_PARQUET_CACHE_ROOT": str(temp_dir / "cache")}):
            window = MainWindow.__new__(MainWindow)
            window._output_dir = Path("OUTPUT") / "autosave-test"
            window._source_file = Path("input.xlsx")
            window._pipeline_session = PipelineSession(
                output_dir=window._output_dir,
                source_file=window._source_file,
            )
            window._step_output_paths = window._pipeline_session.step_output_paths
            window._context = {
                "sample_info": None,
                "deleted_feature_df": None,
                "highlight_rows": set(),
                "blue_font_cells": [],
                "red_font_rows": set(),
            }
            window._file_handler = Mock()
            window._log = lambda _: None

            data = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.0/1.0"], "S1": ["case", 123]})
            step_output = window._save_step_output(1, data)

            assert step_output is not None
            assert window._output_dir not in step_output.parents


def _legacy_removed_tests_kept_for_context() -> None:
    """No-op placeholder to preserve line mapping after regression updates."""
    return
