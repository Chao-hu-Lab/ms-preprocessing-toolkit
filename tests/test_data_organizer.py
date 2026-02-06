"""Tests for DataOrganizer module."""

import pytest
import pandas as pd
import numpy as np

from ms_preprocessing.core.data_organizer import DataOrganizer


class TestDataOrganizer:
    """Test cases for DataOrganizer."""

    @pytest.fixture
    def organizer(self):
        """Create a DataOrganizer instance."""
        return DataOrganizer()

    @pytest.fixture
    def sample_data(self):
        """Create sample test data."""
        data = {
            "Mz": [100.123, 200.456, 300.789],
            "RT": [1.5, 2.5, 3.5],
            "Sample1": [1000, 2000, 3000],
            "Sample2": [1100, 2100, 3100],
            "QC1": [1050, 2050, 3050],
        }
        return pd.DataFrame(data)

    def test_validate_input_empty(self, organizer):
        """Test validation with empty DataFrame."""
        df = pd.DataFrame()
        is_valid, message = organizer.validate_input(df)
        assert not is_valid
        assert "empty" in message.lower()

    def test_validate_input_valid(self, organizer, sample_data):
        """Test validation with valid DataFrame."""
        is_valid, message = organizer.validate_input(sample_data)
        assert is_valid
        assert message == ""

    def test_auto_detect_sample_types(self, organizer):
        """Test auto detection of sample types."""
        columns = ["QC_1", "QC_2", "Blank_1", "Sample_A", "Sample_B"]
        mapping = organizer.auto_detect_sample_types(columns)

        assert mapping["QC_1"] == "QC"
        assert mapping["QC_2"] == "QC"
        assert mapping["Blank_1"] == "blank"
        assert mapping["Sample_A"] == "sample"
        assert mapping["Sample_B"] == "sample"

    def test_process_basic(self, organizer, sample_data):
        """Test basic processing."""
        result = organizer.process(sample_data)

        assert result.success
        assert result.data is not None
        assert len(result.data) > 0

    def test_process_with_sample_type_mapping(self, organizer, sample_data):
        """Test processing with custom sample type mapping."""
        mapping = {"Sample": "case", "QC": "qc"}
        result = organizer.process(sample_data, sample_type_mapping=mapping)

        assert result.success
