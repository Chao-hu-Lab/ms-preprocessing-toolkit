"""Unit tests for adapters.feature_filter."""

from __future__ import annotations

import pandas as pd

from ms_preprocessing.adapters import feature_filter
from ms_preprocessing.utils.results import ProcessingMetadata


class TestFeatureFilterAdapter:
    def test_missing_file_returns_failure(self, tmp_path) -> None:
        result = feature_filter.run(str(tmp_path / "nonexistent.xlsx"))

        assert result.success is False
        assert result.step == "feature_filter"
        assert result.error is not None

    def test_valid_input_metadata_types(self, sample_excel_file) -> None:
        result = feature_filter.run(str(sample_excel_file))

        assert isinstance(result.metadata, ProcessingMetadata)
        assert isinstance(result.metadata.red_font_rows, set)

    def test_deleted_feature_df_is_none_or_dataframe(self, sample_excel_file) -> None:
        result = feature_filter.run(str(sample_excel_file))

        assert result.metadata.deleted_feature_df is None or isinstance(
            result.metadata.deleted_feature_df,
            pd.DataFrame,
        )
