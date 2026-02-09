"""Tests for FeatureFilter module."""

import pytest
import pandas as pd
import numpy as np

from ms_preprocessing.core.feature_filter import FeatureFilter


class TestFeatureFilter:
    """Test cases for FeatureFilter."""

    @pytest.fixture
    def filter_proc(self):
        """Create a FeatureFilter instance."""
        return FeatureFilter()

    @pytest.fixture
    def sample_data(self):
        """Create sample test data with proper structure."""
        data = {
            "FeatureID": ["Sample_Type", "100.123/1.5", "200.456/2.5", "300.789/3.5"],
            "Tolerance": ["na", "na", "na", "na"],
            "Case1": ["case", 10000, 8000, 100],  # Signal above threshold
            "Case2": ["case", 9000, 7500, 200],
            "Control1": ["control", 500, 8500, 9000],
            "Control2": ["control", 400, 8000, 9500],
            "QC1": ["qc", 9500, 8200, 5000],
        }
        return pd.DataFrame(data)

    def test_validate_input_empty(self, filter_proc):
        """Test validation with empty DataFrame."""
        df = pd.DataFrame()
        is_valid, message = filter_proc.validate_input(df)
        assert not is_valid

    def test_validate_input_valid(self, filter_proc, sample_data):
        """Test validation with valid DataFrame."""
        is_valid, message = filter_proc.validate_input(sample_data)
        assert is_valid

    def test_detect_sample_types(self, filter_proc, sample_data):
        """Test sample type detection."""
        group_info = filter_proc._detect_sample_types(sample_data)

        assert "case" in group_info["groups"]
        assert "control" in group_info["groups"]
        assert group_info["has_qc"] is True
        assert len(group_info["qc_cols"]) == 1

    def test_get_group_summary(self, filter_proc, sample_data):
        """Test getting group summary."""
        summary = filter_proc.get_group_summary(sample_data)

        assert "groups" in summary
        assert summary["has_qc"] is True
        assert summary["qc_count"] == 1

    def test_process_filters_features(self, filter_proc, sample_data):
        """Test that processing filters features correctly."""
        result = filter_proc.process(
            sample_data,
            background_threshold=0.33,
            skew_threshold=0.66,
            diff_threshold=0.30,
        )

        assert result.success
        assert result.data is not None

    def test_max_ratio_diff_calculation(self, filter_proc):
        """Test max ratio difference calculation."""
        ratios = [0.1, 0.5, 0.9]
        max_diff = filter_proc._get_max_ratio_diff(ratios)

        # Max diff should be 0.9 - 0.1 = 0.8
        assert abs(max_diff - 0.8) < 0.001

    def test_imputation(self, filter_proc, sample_data):
        """Test missing value imputation."""
        # Add some missing values
        sample_data_with_na = sample_data.copy()
        sample_data_with_na.at[2, "Case1"] = np.nan
        sample_data_with_na.at[3, "Control1"] = ""

        result = filter_proc.process(sample_data_with_na)

        assert result.success
        # Check that no NaN values remain in data columns
        if result.data is not None:
            data_rows = result.data.iloc[1:]
            for col in result.data.columns[2:]:
                if str(col).endswith("_ratio") or str(col) == "QC_ratio":
                    continue
                assert data_rows[col].isna().sum() == 0
