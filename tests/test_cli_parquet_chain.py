"""Tests for CLI parquet intermediate chaining behavior."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import pandas as pd

from ms_preprocessing.main import run_cli


class _FakeResult:
    def __init__(self, data: pd.DataFrame, metadata: dict | None = None) -> None:
        self.success = True
        self.data = data
        self.message = ""
        self.statistics = {}
        self.metadata = metadata or {}


class _DummyDataOrganizer:
    def process(self, data: pd.DataFrame, **kwargs) -> _FakeResult:
        return _FakeResult(data.copy(), metadata={"sample_info": None})


class _DummyISTDMarker:
    def __init__(self) -> None:
        self.config = SimpleNamespace(default_ppm_tolerance=20.0, default_rt_tolerance=1.0)

    def process(self, data: pd.DataFrame, **kwargs) -> _FakeResult:
        return _FakeResult(data.copy(), metadata={"red_font_rows": [], "protected_rows": []})


class _DummyDuplicateRemover:
    def process(self, data: pd.DataFrame, **kwargs) -> _FakeResult:
        return _FakeResult(data.copy(), metadata={"red_font_rows": [], "protected_rows": []})


class _DummyFeatureFilter:
    def process(self, data: pd.DataFrame, **kwargs) -> _FakeResult:
        return _FakeResult(
            data.copy(),
            metadata={
                "red_font_rows": [],
                "protected_rows": [],
                "blue_font_cells": [],
                "deleted_features": [],
            },
        )


class _FakeFileHandler:
    def __init__(self, input_df: pd.DataFrame) -> None:
        self._input_df = input_df
        self.calls: list[tuple[str, str, Path]] = []
        self.saved_data: dict[Path, pd.DataFrame] = {}

    def load_data(self, file_path, sheet_name=0, header_row=0):
        path = Path(file_path)
        self.calls.append(("load", path.suffix.lower(), path))
        if path in self.saved_data:
            fmt = "parquet" if path.suffix.lower() == ".parquet" else "excel"
            return self.saved_data[path].copy(), {"format": fmt, "red_font_rows": []}
        fmt = "parquet" if path.suffix.lower() == ".parquet" else "excel"
        return self._input_df.copy(), {"format": fmt, "red_font_rows": []}

    def save_data(self, df, file_path, **kwargs):
        path = Path(file_path)
        self.calls.append(("save", path.suffix.lower(), path))
        self.saved_data[path] = df.copy()
        return path


def _make_cli_args(input_path: Path, output_path: Path | None, step: str) -> SimpleNamespace:
    return SimpleNamespace(
        input=str(input_path),
        output=str(output_path) if output_path else None,
        method_file=None,
        step=step,
        mz_tol=20.0,
        istd_mz=None,
        istd_record_file=None,
        istd_record_date=None,
        rt_tol=1.0,
        bg_threshold=0.33,
        skew_threshold=0.66,
        diff_threshold=0.30,
        qc_ratio_threshold=0.0,
        no_gui=True,
        version=False,
    )


def _patch_cli_dependencies(monkeypatch, fake_handler: _FakeFileHandler) -> None:
    import ms_core.utils.file_handler as file_handler_module
    import ms_core.preprocessing.data_organizer as organizer_module
    import ms_core.preprocessing.istd_marker as istd_module
    import ms_core.preprocessing.duplicate_remover as duplicate_module
    import ms_core.preprocessing.ms_quality_filter as filter_module

    monkeypatch.setattr(file_handler_module, "FileHandler", lambda: fake_handler)
    monkeypatch.setattr(organizer_module, "DataOrganizer", _DummyDataOrganizer)
    monkeypatch.setattr(istd_module, "ISTDMarker", _DummyISTDMarker)
    monkeypatch.setattr(duplicate_module, "DuplicateRemover", _DummyDuplicateRemover)
    monkeypatch.setattr(filter_module, "FeatureFilter", _DummyFeatureFilter)


def test_cli_step_all_uses_parquet_intermediates_and_final_xlsx(monkeypatch) -> None:
    with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
        base = Path(temp_dir)
        df = pd.DataFrame(
            {
                "Mz/RT": ["Sample_Type", "100.1/1.0"],
                "Tolerance": ["na", "na"],
                "Case1": ["case", 1000],
                "Control1": ["control", 1200],
                "QC1": ["qc", 1100],
            }
        )
        input_path = base / "input.csv"
        df.to_csv(input_path, index=False)
        output_path = base / "final.xlsx"

        fake_handler = _FakeFileHandler(input_df=df)
        _patch_cli_dependencies(monkeypatch, fake_handler)

        rc = run_cli(_make_cli_args(input_path=input_path, output_path=output_path, step="all"))
        assert rc == 0

        save_suffixes = [suffix for op, suffix, _ in fake_handler.calls if op == "save"]
        load_suffixes = [suffix for op, suffix, _ in fake_handler.calls if op == "load"]

        assert ".parquet" in save_suffixes
        assert ".parquet" in load_suffixes
        assert save_suffixes[-1] == ".xlsx"


def test_cli_single_step_filter_accepts_parquet_input(monkeypatch) -> None:
    with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
        base = Path(temp_dir)
        df = pd.DataFrame(
            {
                "Mz/RT": ["Sample_Type", "100.1/1.0"],
                "Tolerance": ["na", "na"],
                "Case1": ["case", 1000],
                "Control1": ["control", 1200],
                "QC1": ["qc", 1100],
            }
        )
        input_path = base / "input.parquet"
        input_path.write_text("fake parquet placeholder", encoding="utf-8")

        fake_handler = _FakeFileHandler(input_df=df)
        _patch_cli_dependencies(monkeypatch, fake_handler)

        rc = run_cli(_make_cli_args(input_path=input_path, output_path=None, step="filter"))
        assert rc == 0

        load_suffixes = [suffix for op, suffix, _ in fake_handler.calls if op == "load"]
        save_suffixes = [suffix for op, suffix, _ in fake_handler.calls if op == "save"]
        assert load_suffixes[0] == ".parquet"
        assert save_suffixes[-1] == ".xlsx"
