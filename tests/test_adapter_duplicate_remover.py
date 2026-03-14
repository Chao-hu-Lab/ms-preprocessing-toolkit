"""Unit tests for adapters.duplicate_remover."""

from __future__ import annotations

from ms_preprocessing.adapters import duplicate_remover
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult


class TestDuplicateRemoverAdapter:
    def test_missing_file_returns_failure(self, tmp_path) -> None:
        result = duplicate_remover.run(str(tmp_path / "nonexistent.xlsx"))

        assert result.success is False
        assert result.step == "duplicate_remover"
        assert result.error is not None

    def test_protected_rows_forwarded(self, tmp_path) -> None:
        result = duplicate_remover.run(
            str(tmp_path / "nonexistent.xlsx"),
            protected_rows={1, 2, 3},
        )

        assert result.success is False

    def test_valid_input_metadata_types(self, sample_excel_file) -> None:
        result = duplicate_remover.run(str(sample_excel_file))

        assert isinstance(result, ProcessingResult)
        assert isinstance(result.metadata, ProcessingMetadata)
        assert isinstance(result.metadata.red_font_rows, set)
        assert isinstance(result.metadata.protected_rows, set)
