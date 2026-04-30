"""Unit tests for adapters.feature_filter."""

from __future__ import annotations

import pandas as pd

from ms_preprocessing.adapters import feature_filter
from ms_preprocessing.config.feature_filter_presets import get_step4_preset
from ms_preprocessing.utils.results import ProcessingMetadata


def _ratio_rescue_32_16_input() -> pd.DataFrame:
    case_values = [8000] * 8 + [0] * 17
    control_values = [8000] * 4 + [0] * 21
    return pd.DataFrame(
        {
            "Mz/RT": ["Sample_Type", "100.000/1.0"],
            "Tolerance": ["na", "na"],
            **{f"Case{i}": ["case", case_values[i - 1]] for i in range(1, 26)},
            **{f"Control{i}": ["control", control_values[i - 1]] for i in range(1, 26)},
            "QC1": ["qc", 8000],
        }
    )


class TestFeatureFilterAdapter:
    def test_missing_file_returns_failure(self, tmp_path) -> None:
        result = feature_filter.run(str(tmp_path / "nonexistent.xlsx"))

        assert result.success is False
        assert result.step == "feature_filter"
        assert result.error is not None

    def test_valid_input_metadata_types(self, sample_excel_file) -> None:
        result = feature_filter.run(str(sample_excel_file))

        assert result.success is True
        assert isinstance(result.metadata, ProcessingMetadata)
        assert isinstance(result.metadata.red_font_rows, set)

    def test_deleted_feature_df_is_none_or_dataframe(self, sample_excel_file) -> None:
        result = feature_filter.run(str(sample_excel_file))

        assert result.metadata.deleted_feature_df is None or isinstance(
            result.metadata.deleted_feature_df,
            pd.DataFrame,
        )

    def test_loose_preset_rescues_32_16_detection_ratio_feature(self) -> None:
        result = feature_filter.run_from_df(
            _ratio_rescue_32_16_input(),
            **get_step4_preset("loose"),
        )

        assert result.success is True
        assert result.data is not None
        feature_row = result.data[result.data["Mz/RT"] == "100.000/1.0"]
        assert len(feature_row) == 1
        assert bool(feature_row["is_Presence_Absence_Marker"].iloc[0]) is True
        assert result.statistics["ratio_rescue_kept"] == 1
