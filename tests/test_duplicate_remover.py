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

    def test_degeneracy_annotation_is_disabled_by_default(self, remover):
        df = pd.DataFrame(
            {
                "Mz/RT": ["Sample_Type", "242.1191/10.99", "264.1010/10.99"],
                "Sample1": ["case", 50000, 38000],
                "QC1": ["qc", 49000, 37000],
            }
        )

        result = remover.process(df, mz_tolerance_ppm=20, rt_tolerance=0.1)

        assert result.success
        assert "Degeneracy_Type" not in result.data.columns
        assert result.statistics["degeneracy_annotation_enabled"] is False
        assert result.statistics["degeneracy_adduct_count"] == 0

    def test_degeneracy_annotation_marks_base_and_adduct(self, remover):
        df = pd.DataFrame(
            {
                "Mz/RT": ["Sample_Type", "242.1191/10.99", "264.1010/11.00", "300.0000/20.00"],
                "Case1": ["case", 100, 50, 20],
                "Case2": ["case", 200, 100, 25],
                "Case3": ["case", 400, 200, 22],
                "Case4": ["case", 800, 400, 19],
                "QC1": ["qc", 51000, 38500, 11500],
            }
        )

        result = remover.process(
            df,
            mz_tolerance_ppm=5,
            rt_tolerance=0.1,
            enable_degeneracy_annotation=True,
            degeneracy_ppm_tolerance=20,
            degeneracy_rt_tolerance=0.05,
        )

        assert result.success
        assert "Degeneracy_Type" in result.data.columns
        assert result.statistics["degeneracy_annotation_enabled"] is True
        assert result.statistics["degeneracy_adduct_count"] == 1
        assert result.statistics["degeneracy_base_count"] == 1
        assert result.statistics["degeneracy_corr_rejected"] == 0

        base_row = result.data[result.data["Mz/RT"] == "242.1191/10.99"].iloc[0]
        adduct_row = result.data[result.data["Mz/RT"] == "264.1010/11.00"].iloc[0]
        singleton_row = result.data[result.data["Mz/RT"] == "300.0000/20.00"].iloc[0]

        assert base_row["Degeneracy_Group_Role"] == "base"
        assert base_row["Degeneracy_Type"] == "[M+H]+"
        assert base_row["Degeneracy_Group_ID"] == "DG0001"
        assert adduct_row["Degeneracy_Group_Role"] == "adduct"
        assert adduct_row["Degeneracy_Type"] == "[M+Na]+"
        assert adduct_row["Degeneracy_Base_mz"] == "242.1191"
        assert float(adduct_row["Degeneracy_Pearson_R"]) >= 0.99
        assert singleton_row["Degeneracy_Group_Role"] == "singleton"

    def test_degeneracy_annotation_rejects_low_correlation_pairs(self, remover):
        df = pd.DataFrame(
            {
                "Mz/RT": ["Sample_Type", "242.1191/10.99", "264.1010/11.00"],
                "Case1": ["case", 100, 400],
                "Case2": ["case", 200, 300],
                "Case3": ["case", 300, 200],
                "Case4": ["case", 400, 100],
            }
        )

        result = remover.process(
            df,
            enable_degeneracy_annotation=True,
            degeneracy_ppm_tolerance=20,
            degeneracy_rt_tolerance=0.05,
            degeneracy_correlation_threshold=0.8,
            degeneracy_min_correlation_points=3,
        )

        assert result.success
        assert result.statistics["degeneracy_adduct_count"] == 0
        assert result.statistics["degeneracy_corr_rejected"] >= 1
        pair_row = result.data[result.data["Mz/RT"] == "264.1010/11.00"].iloc[0]
        assert pair_row["Degeneracy_Group_Role"] == "singleton"
