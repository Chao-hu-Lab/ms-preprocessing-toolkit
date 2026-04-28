"""Tests for combined TSV preprocessing workflow service."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult
from ms_preprocessing.workflow.combined_tsv_service import CombinedTsvService


class _FakeFileHandler:
    def __init__(self) -> None:
        self.calls: list[tuple[pd.DataFrame, Path, dict]] = []

    def save_data(self, df, file_path, **kwargs):
        path = Path(file_path)
        self.calls.append((df, path, kwargs))
        return path


def test_combined_tsv_service_generates_output_under_combined_fix_and_saves_without_cache(
    monkeypatch,
    tmp_path,
) -> None:
    raw_path = tmp_path / "raw.tsv"
    raw_path.write_text("Mz\tRT\n1\t2\n", encoding="utf-8")
    method_file = tmp_path / "method.docx"
    method_file.write_text("placeholder", encoding="utf-8")
    handler = _FakeFileHandler()
    captured: dict[str, object] = {}

    def fake_run_combined_fix(input_path, **kwargs):
        captured["input_path"] = input_path
        captured.update(kwargs)
        return ProcessingResult(
            success=True,
            step="data_organizer",
            output_path=None,
            data=pd.DataFrame({"Mz": [1.0], "RT": [2.0]}),
            metadata=ProcessingMetadata(),
        )

    import ms_preprocessing.workflow.combined_tsv_service as service_module

    monkeypatch.setattr(service_module.data_organizer_adapter, "run_combined_fix", fake_run_combined_fix)

    out = CombinedTsvService(file_handler=handler).create_combined_fix(
        raw_path=raw_path,
        method_file=method_file,
        output_dir=tmp_path / "OUTPUT",
    )

    assert out.parent == tmp_path / "OUTPUT" / "combined_fix"
    assert out.name.startswith("raw_combined_fix_")
    assert out.suffix == ".xlsx"
    assert captured["input_path"] == str(raw_path)
    assert captured["method_file"] == str(method_file)
    assert handler.calls[-1][1] == out
    assert handler.calls[-1][2]["save_parquet_cache"] is False


def test_combined_tsv_service_returns_generated_path_for_step1_loading(monkeypatch, tmp_path) -> None:
    raw_path = tmp_path / "raw.tsv"
    raw_path.write_text("Mz\tRT\n1\t2\n", encoding="utf-8")
    handler = _FakeFileHandler()

    import ms_preprocessing.workflow.combined_tsv_service as service_module

    monkeypatch.setattr(
        service_module.data_organizer_adapter,
        "run_combined_fix",
        lambda *_args, **_kwargs: ProcessingResult(
            success=True,
            step="data_organizer",
            output_path=None,
            data=pd.DataFrame({"Mz": [1.0]}),
            metadata=ProcessingMetadata(),
        ),
    )

    returned = CombinedTsvService(file_handler=handler).create_combined_fix(
        raw_path=raw_path,
        method_file=None,
        output_dir=tmp_path / "OUTPUT",
    )

    assert returned == handler.calls[-1][1]
