"""Unit tests for adapters.istd_marker."""

from __future__ import annotations

from ms_preprocessing.adapters import istd_marker
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult


class TestISTDMarkerAdapter:
    def test_missing_file_returns_failure(self, tmp_path) -> None:
        result = istd_marker.run(str(tmp_path / "nonexistent.xlsx"))

        assert result.success is False
        assert result.step == "istd_marker"
        assert result.error is not None
        assert "not found" in result.error.lower()

    def test_missing_file_metadata_is_empty(self, tmp_path) -> None:
        result = istd_marker.run(str(tmp_path / "nonexistent.xlsx"))

        assert isinstance(result.metadata, ProcessingMetadata)
        assert result.metadata.red_font_rows == set()

    def test_valid_input_returns_processing_result(self, sample_excel_file) -> None:
        result = istd_marker.run(str(sample_excel_file))

        assert isinstance(result, ProcessingResult)
        assert result.step == "istd_marker"
        assert isinstance(result.metadata, ProcessingMetadata)
        assert isinstance(result.metadata.red_font_rows, set)
