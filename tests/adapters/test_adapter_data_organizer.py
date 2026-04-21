"""Unit tests for adapters.data_organizer."""

from __future__ import annotations

import pandas as pd

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

    def test_valid_input_returns_processing_result(self) -> None:
        df = pd.DataFrame(
            {
                "Mz": [100.1234, 200.5678],
                "RT": [1.5, 2.5],
                "Sample1": [1000, 1100],
                "Sample2": [1200, 1300],
                "QC1": [1050, 1150],
            }
        )
        result = data_organizer.run_from_df(df)

        assert isinstance(result, ProcessingResult)
        assert result.success is True
        assert result.step == "data_organizer"
        assert isinstance(result.metadata, ProcessingMetadata)
        assert isinstance(result.metadata.red_font_rows, set)
        assert isinstance(result.metadata.protected_rows, set)
        assert isinstance(result.metadata.blue_font_cells, list)


def test_run_combined_fix_uses_combined_fix_mode(monkeypatch, tmp_path) -> None:
    input_path = tmp_path / "raw.tsv"
    pd.DataFrame({"Mz": [1], "RT": [2], "MZmine ID": ["id"]}).to_csv(
        input_path,
        sep="\t",
        index=False,
    )
    captured: dict[str, object] = {}

    def fake_run_processor(df, **kwargs):
        captured.update(kwargs)
        return ProcessingResult(
            success=True,
            step="data_organizer",
            output_path=None,
            data=df.copy(),
            metadata=ProcessingMetadata(),
            statistics={"mode": "combined_fix"},
        )

    monkeypatch.setattr(data_organizer, "_run_processor", fake_run_processor)

    result = data_organizer.run_combined_fix(str(input_path), method_file="method.docx")

    assert result.success is True
    assert result.output_path is None
    assert captured["mode"] == "combined_fix"
    assert captured["method_file"] == "method.docx"
    assert captured["persist_output"] is False
