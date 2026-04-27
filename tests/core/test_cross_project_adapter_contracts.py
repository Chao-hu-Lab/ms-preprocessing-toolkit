from __future__ import annotations

import pandas as pd
from ms_core.preprocessing.data_organizer import DataOrganizer as CoreDataOrganizer
from ms_core.preprocessing.duplicate_remover import DuplicateRemover as CoreDuplicateRemover
from ms_core.preprocessing.istd_marker import ISTDMarker as CoreISTDMarker
from ms_core.preprocessing.ms_quality_filter import FeatureFilter as CoreFeatureFilter

from ms_preprocessing.adapters import data_organizer, duplicate_remover, feature_filter, istd_marker


def _organizer_input() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Mz": [100.1234, 200.5678],
            "RT": [1.5, 2.5],
            "Sample1": [1000, 1100],
            "Sample2": [1200, 1300],
            "QC1": [1050, 1150],
        }
    )


def _feature_matrix_input() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Mz/RT": ["Sample_Type", "100.123/1.5", "100.123/1.5", "200.456/2.5"],
            "Tolerance": ["na", "20/0.5", "20/0.5", "20/0.5"],
            "Sample1": ["case", 5000, 5001, 6000],
            "Sample2": ["case", 5500, 5501, 6500],
            "QC1": ["qc", 5200, 5201, 6200],
        }
    )


def test_data_organizer_adapter_preserves_current_ms_core_sample_info_contract() -> None:
    core_result = CoreDataOrganizer().process(_organizer_input())
    adapter_result = data_organizer.run_from_df(_organizer_input())

    assert core_result.success is True
    assert adapter_result.success is True
    assert isinstance(core_result.metadata.get("sample_info"), pd.DataFrame)
    assert isinstance(adapter_result.metadata.sample_info, pd.DataFrame)

    core_sample_info = core_result.metadata["sample_info"]
    adapter_sample_info = adapter_result.metadata.sample_info
    assert adapter_sample_info is not None
    assert list(adapter_sample_info.columns) == list(core_sample_info.columns)
    assert list(adapter_sample_info["Sample_Name"]) == list(core_sample_info["Sample_Name"])


def test_duplicate_remover_adapter_matches_current_ms_core_row_marking_contract() -> None:
    core_result = CoreDuplicateRemover().process(_feature_matrix_input())
    adapter_result = duplicate_remover.run_from_df(_feature_matrix_input())

    assert core_result.success is True
    assert adapter_result.success is True
    assert adapter_result.metadata.red_font_rows == set(core_result.metadata.get("red_font_rows", []))
    assert adapter_result.metadata.protected_rows == set(core_result.metadata.get("protected_rows", []))


def test_feature_filter_adapter_normalizes_current_ms_core_deleted_features_contract() -> None:
    core_result = CoreFeatureFilter().process(_feature_matrix_input())
    adapter_result = feature_filter.run_from_df(_feature_matrix_input())

    assert core_result.success is True
    assert adapter_result.success is True
    assert isinstance(core_result.metadata.get("deleted_features"), list)
    assert adapter_result.metadata.red_font_rows == set(core_result.metadata.get("red_font_rows", []))
    assert adapter_result.metadata.protected_rows == set(core_result.metadata.get("protected_rows", []))
    assert adapter_result.metadata.deleted_feature_df is None or isinstance(
        adapter_result.metadata.deleted_feature_df,
        pd.DataFrame,
    )


def test_istd_marker_adapter_matches_current_ms_core_row_marking_contract() -> None:
    core_result = CoreISTDMarker().process(_feature_matrix_input())
    adapter_result = istd_marker.run_from_df(_feature_matrix_input())

    assert core_result.success is True
    assert adapter_result.success is True
    assert adapter_result.metadata.red_font_rows == set(core_result.metadata.get("red_font_rows", []))
    assert adapter_result.metadata.protected_rows == set(core_result.metadata.get("protected_rows", []))
