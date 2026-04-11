"""Regression tests for GUI workflow labels."""

from ms_preprocessing.config.settings import Settings


def test_workflow_steps_use_expected_sidebar_labels() -> None:
    assert Settings.WORKFLOW_STEPS == [
        ("data_organizer", "資料整理", "Data Organization"),
        ("istd_marker", "ISTD 標記", "ISTD Marking"),
        ("duplicate_remover", "重複訊號刪除", "Duplicate Removal"),
        ("feature_filter", "特徵篩選", "Feature Filtering"),
    ]
