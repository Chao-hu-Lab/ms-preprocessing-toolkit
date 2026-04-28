"""Tests for compact GUI step result summaries."""

from __future__ import annotations

from pathlib import PurePosixPath

import ms_preprocessing.gui.path_display as path_display_module
from ms_preprocessing.gui.step_summary import summarize_step_result


def test_step1_summary_reports_data_shape_and_method_file() -> None:
    lines = summarize_step_result(
        "data_organizer",
        statistics={"features": 120, "samples": 18},
        metadata={"sample_info": object()},
        parameters={"method_file": r"C:\data\method.docx"},
    )

    assert any("Features: 120" in line for line in lines)
    assert any("Samples: 18" in line for line in lines)
    assert any("SampleInfo: available" in line for line in lines)
    assert any("Method: method.docx" in line for line in lines)


def test_step_summary_shortens_windows_paths_when_running_on_posix(monkeypatch) -> None:
    monkeypatch.setattr(path_display_module, "PurePath", PurePosixPath)

    lines = summarize_step_result(
        "data_organizer",
        statistics={},
        metadata={},
        parameters={"method_file": r"C:\data\method.docx"},
    )

    assert "Method: method.docx" in lines
    assert all(r"C:\data\method.docx" not in line for line in lines)


def test_step2_summary_reports_xic_metadata() -> None:
    lines = summarize_step_result(
        "istd_marker",
        statistics={"istd_marked": 7},
        metadata={
            "xic_source_path": "xic_results.xlsx",
            "xic_target_count": 14,
            "xic_skipped_targets": [{"label": "bad", "reason": "missing ppm tol"}],
            "istd_warning_count": 12,
            "unexpected_future_key": "safe",
        },
    )

    assert any("XIC: xic_results.xlsx" in line for line in lines)
    assert any("Targets: 14" in line for line in lines)
    assert any("Marked: 7" in line for line in lines)
    assert any("Skipped targets: 1" in line for line in lines)
    assert any("Warnings: 12" in line for line in lines)


def test_step3_summary_reports_merge_and_recovery_counts() -> None:
    lines = summarize_step_result(
        "duplicate_remover",
        statistics={
            "merge_mode": "sum",
            "removed_duplicates": 5,
            "merged_groups": 3,
            "recovered_data_points": 22,
        },
        metadata={},
    )

    assert any("Merge mode: sum" in line for line in lines)
    assert any("Duplicates removed: 5" in line for line in lines)
    assert any("Groups merged: 3" in line for line in lines)
    assert any("Recovered points: 22" in line for line in lines)


def test_step4_summary_reports_feature_filter_outcome_and_deleted_sheet_setting() -> None:
    lines = summarize_step_result(
        "feature_filter",
        statistics={
            "kept_features": 80,
            "deleted_features": 20,
            "qc_deleted_count": 4,
            "mnar_kept_count": 9,
        },
        metadata={},
        parameters={"export_deleted_feature_sheet": True},
    )

    assert any("Kept: 80" in line for line in lines)
    assert any("Deleted: 20" in line for line in lines)
    assert any("QC deleted: 4" in line for line in lines)
    assert any("MNAR kept: 9" in line for line in lines)
    assert any("deleted_feature sheet: enabled" in line for line in lines)
