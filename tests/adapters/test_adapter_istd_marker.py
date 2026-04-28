"""Unit tests for adapters.istd_marker."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

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

    def test_missing_xic_source_returns_failure_without_core_call(self, monkeypatch) -> None:
        class UnexpectedProcessor:
            def __init__(self) -> None:
                raise AssertionError("core processor should not run without XIC source")

        monkeypatch.setattr(istd_marker, "_ISTDMarker", UnexpectedProcessor)
        df = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.0/1.0"], "S1": ["case", 1]})

        result = istd_marker.run_from_df(df)

        assert result.success is False
        assert result.data is None
        assert result.error is not None
        assert "XIC Extractor results workbook" in result.error

    def test_valid_input_returns_processing_result(self, sample_excel_file, monkeypatch) -> None:
        calls: dict[str, object] = {}

        class FakeProcessor:
            def set_progress_callback(self, callback) -> None:
                calls["progress_callback"] = callback

            def process(self, input_df, **kwargs):
                calls["kwargs"] = kwargs
                return SimpleNamespace(
                    success=True,
                    data=input_df.copy(),
                    metadata={"red_font_rows": {2}, "protected_rows": {2}},
                    statistics={},
                )

        monkeypatch.setattr(istd_marker, "_ISTDMarker", FakeProcessor)
        monkeypatch.setattr(istd_marker, "_save_output", lambda _df: "istd.parquet")

        result = istd_marker.run(str(sample_excel_file), xic_results_file="xic_results.xlsx")

        assert isinstance(result, ProcessingResult)
        assert result.success is True
        assert result.step == "istd_marker"
        assert isinstance(result.metadata, ProcessingMetadata)
        assert isinstance(result.metadata.red_font_rows, set)
        assert calls["kwargs"]["xic_results_file"] == Path("xic_results.xlsx")
