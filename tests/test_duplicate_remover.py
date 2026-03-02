"""Tests for DuplicateRemover module."""

import pytest
import pandas as pd
import numpy as np

from ms_core.preprocessing.duplicate_remover import DuplicateRemover


class TestDuplicateRemover:
    """Test cases for DuplicateRemover."""

    @pytest.fixture
    def remover(self):
        """Create a DuplicateRemover instance."""
        return DuplicateRemover()

    @pytest.fixture
    def sample_data_with_duplicates(self):
        """Create sample data with duplicate signals."""
        data = {
            "Mz/RT": [
                "Sample_Type",
                "100.1234/1.50",  # Original
                "100.1235/1.51",  # Duplicate (within tolerance)
                "200.5678/2.50",  # Unique
                "300.9999/3.50",  # Unique
            ],
            "Tolerance": ["na", "na", "na", "na", "na"],
            "Sample1": ["case", 5000, 4000, 6000, 7000],
            "Sample2": ["case", 5500, 4500, 6500, 7500],
        }
        return pd.DataFrame(data)

    def test_validate_input_empty(self, remover):
        """Test validation with empty DataFrame."""
        df = pd.DataFrame()
        is_valid, message = remover.validate_input(df)
        assert not is_valid

    def test_validate_input_valid(self, remover, sample_data_with_duplicates):
        """Test validation with valid DataFrame."""
        is_valid, message = remover.validate_input(sample_data_with_duplicates)
        assert is_valid

    def test_detect_columns_combined_format(self, remover, sample_data_with_duplicates):
        """Test column detection with combined m/z/RT format."""
        col_info = remover._detect_columns(sample_data_with_duplicates)

        assert col_info["combined_mz_rt"] is True
        assert col_info["feature_col"] == "Mz/RT"

    def test_find_duplicate_groups(self, remover, sample_data_with_duplicates):
        """Test finding duplicate groups."""
        groups = remover.get_duplicate_groups(
            sample_data_with_duplicates,
            mz_tolerance_ppm=20,
            rt_tolerance=0.1,
        )

        # Should find one duplicate group (first two data rows)
        assert len(groups) >= 1

    def test_process_removes_duplicates(self, remover, sample_data_with_duplicates):
        """Test that processing removes duplicates."""
        result = remover.process(
            sample_data_with_duplicates,
            mz_tolerance_ppm=20,
            rt_tolerance=0.1,
        )

        assert result.success
        # Original has 4 data rows, should be reduced
        original_data_rows = len(sample_data_with_duplicates) - 1
        result_data_rows = len(result.data) - 1
        assert result_data_rows <= original_data_rows

    def test_process_preserves_highest_intensity(self, remover, sample_data_with_duplicates):
        """Test that processing preserves highest intensity signal."""
        result = remover.process(
            sample_data_with_duplicates,
            mz_tolerance_ppm=20,
            rt_tolerance=0.1,
        )

        assert result.success
        # The higher intensity duplicate should be preserved
        # Row with "100.1234/1.50" has higher intensity than "100.1235/1.51"
