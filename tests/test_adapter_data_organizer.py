"""Unit tests for adapters.data_organizer."""

from __future__ import annotations

from ms_preprocessing.adapters import data_organizer
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult


class TestDataOrganizerAdapter:
    def test_missing_file_returns_failure(self, tmp_path) -> None:
        result = data_organizer.run(str(tmp_path / "nonexistent.xlsx"))

        assert isinstance(result, ProcessingResult)
        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error.lower()
        assert result.step == "data_organizer"

    def test_missing_file_metadata_is_empty(self, tmp_path) -> None:
        result = data_organizer.run(str(tmp_path / "nonexistent.xlsx"))

        assert isinstance(result.metadata, ProcessingMetadata)
        assert result.metadata.red_font_rows == set()
        assert result.metadata.protected_rows == set()

    def test_valid_input_returns_processing_result(self, sample_excel_file) -> None:
        result = data_organizer.run(str(sample_excel_file))

        assert isinstance(result, ProcessingResult)
        assert result.step == "data_organizer"
        assert isinstance(result.metadata, ProcessingMetadata)
        assert isinstance(result.metadata.red_font_rows, set)
        assert isinstance(result.metadata.protected_rows, set)
        assert isinstance(result.metadata.blue_font_cells, list)
