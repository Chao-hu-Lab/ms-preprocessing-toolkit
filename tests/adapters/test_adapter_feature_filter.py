"""Unit tests for adapters.feature_filter."""

from __future__ import annotations

import pandas as pd
import pytest

from ms_preprocessing.adapters import deleted_features_to_dataframe
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


def _three_group_detection_input(
    detections: tuple[float, float, float],
) -> pd.DataFrame:
    data: dict[str, list[object]] = {
        "Mz/RT": ["Sample_Type", "100.000/1.0"],
        "Tolerance": ["na", "na"],
    }
    for group_name, ratio in zip(("GroupA", "GroupB", "GroupC"), detections):
        detected = int(round(ratio * 100))
        for index in range(1, 101):
            data[f"{group_name}{index:03d}"] = [
                group_name,
                8000 if index <= detected else 0,
            ]
    return pd.DataFrame(data)


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

    def test_adapter_preserves_imputation_metadata_column_order(self) -> None:
        result = feature_filter.run_from_df(
            _three_group_detection_input((0.42, 0.35, 0.20)),
            **get_step4_preset("loose"),
        )

        assert result.success is True
        assert result.data is not None
        marker_index = result.data.columns.get_loc("is_Presence_Absence_Marker")
        assert list(result.data.columns[marker_index + 1 : marker_index + 3]) == [
            "Feature_Filter_Keep_Reasons",
            "Imputation_Tag_Reasons",
        ]
        assert "Detection_Profile" not in result.data.columns

    @pytest.mark.parametrize(
        ("detections", "expected_tag"),
        [
            ((0.42, 0.35, 0.20), False),
            ((0.25, 0.22, 0.18), True),
        ],
    )
    def test_loose_preset_propagates_imputation_tag_flip_cases(
        self,
        detections: tuple[float, float, float],
        expected_tag: bool,
    ) -> None:
        result = feature_filter.run_from_df(
            _three_group_detection_input(detections),
            **get_step4_preset("loose"),
        )

        assert result.success is True
        assert result.data is not None
        feature_row = result.data[result.data["Mz/RT"] == "100.000/1.0"]
        assert len(feature_row) == 1
        assert bool(feature_row["is_Presence_Absence_Marker"].iloc[0]) is expected_tag

    def test_deleted_features_to_dataframe_preserves_step4_diagnostics(self) -> None:
        deleted_row = pd.Series(
            {
                "Mz/RT": "200.000/2.0",
                "Tolerance": "na",
                "exposure_ratio": 0.0,
                "normal_ratio": 0.05,
                "control_ratio": 0.0,
                "QC_ratio": 1.0,
                "Feature_Filter_Delete_Reasons": "no_keep_rule",
            }
        )

        deleted_df = deleted_features_to_dataframe({"deleted_features": [deleted_row]})

        assert deleted_df is not None
        assert list(deleted_df.columns) == [
            "Mz/RT",
            "Tolerance",
            "exposure_ratio",
            "normal_ratio",
            "control_ratio",
            "QC_ratio",
            "Feature_Filter_Delete_Reasons",
        ]
        assert "Feature_Filter_Keep_Reasons" not in deleted_df.columns
        assert "Imputation_Tag_Reasons" not in deleted_df.columns
        assert "Detection_Profile" not in deleted_df.columns
