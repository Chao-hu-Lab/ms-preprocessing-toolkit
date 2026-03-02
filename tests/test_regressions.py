"""Regression tests for issues found during project review."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd

from ms_core.preprocessing.duplicate_remover import DuplicateRemover
from ms_core.utils.file_handler import FileHandler


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
        patch.object(handler, "_resolve_parquet_cache", return_value=Path("cache.parquet")),
        patch("pathlib.Path.exists", return_value=True),
        patch("pandas.read_parquet", return_value=fake_df),
        patch.object(handler, "_load_parquet_meta", return_value=fake_meta),
    ):
        _, metadata = handler.load_data("input.xlsx")

    assert metadata.get("format") == "parquet"
    assert metadata.get("red_font_rows") == [1]
