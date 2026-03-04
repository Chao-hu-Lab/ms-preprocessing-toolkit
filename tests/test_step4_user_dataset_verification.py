"""Tests for Step 4 benchmark helper utilities."""

from __future__ import annotations

import pandas as pd

from scripts.benchmark_step4_io import count_zero_and_nan, detect_imputation_target_columns


def test_detect_imputation_target_columns_returns_group_and_qc_columns() -> None:
    df = pd.DataFrame(
        {
            "Mz/RT": ["Sample_Type", "100.0/1.0"],
            "Tolerance": ["na", "na"],
            "Case1": ["case", 8000],
            "Control1": ["control", 0],
            "QC1": ["qc", 6000],
        }
    )

    cols = detect_imputation_target_columns(df)
    assert cols == ["Case1", "Control1", "QC1"]


def test_count_zero_and_nan_counts_only_data_rows() -> None:
    df = pd.DataFrame(
        {
            "Mz/RT": ["Sample_Type", "100.0/1.0"],
            "Case1": ["case", 0],
            "Control1": ["control", None],
            "QC1": ["qc", 6000],
        }
    )

    zero_count, nan_count = count_zero_and_nan(df, ["Case1", "Control1", "QC1"])
    assert zero_count == 1
    assert nan_count == 1
