"""Tests for CLI parquet intermediate chaining behavior."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from ms_preprocessing.config.pipeline_profiles import get_pipeline_profile
from ms_preprocessing.main import run_cli
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult


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
        profile="default",
        method_file=None,
        step=step,
        mz_tol=None,
        istd_mz=None,
        istd_record_file=None,
        istd_record_date=None,
        rt_tol=None,
        bg_threshold=None,
        intensity_fc_threshold=None,
        diff_threshold=None,
        qc_ratio_threshold=None,
        persist_intermediate=False,
        no_gui=True,
        version=False,
    )


def _patch_cli_dependencies(monkeypatch, fake_handler: _FakeFileHandler) -> None:
    import ms_preprocessing.adapters.data_organizer as organizer_module
    import ms_preprocessing.adapters.istd_marker as istd_module
    import ms_preprocessing.adapters.duplicate_remover as duplicate_module
    import ms_preprocessing.adapters.feature_filter as filter_module
    import ms_preprocessing.utils.file_handler as file_handler_module

    monkeypatch.setattr(file_handler_module, "FileHandler", lambda: fake_handler)
    monkeypatch.setattr(
        organizer_module,
        "run_from_df",
        lambda data, **kwargs: ProcessingResult(
            success=True,
            step="data_organizer",
            output_path=None,
            data=data.copy(),
            metadata=ProcessingMetadata(sample_info=None),
        ),
    )
    monkeypatch.setattr(
        istd_module,
        "run_from_df",
        lambda data, **kwargs: ProcessingResult(
            success=True,
            step="istd_marker",
            output_path=None,
            data=data.copy(),
            metadata=ProcessingMetadata(red_font_rows=set(), protected_rows=set()),
        ),
    )
    monkeypatch.setattr(
        duplicate_module,
        "run_from_df",
        lambda data, **kwargs: ProcessingResult(
            success=True,
            step="duplicate_remover",
            output_path=None,
            data=data.copy(),
            metadata=ProcessingMetadata(red_font_rows=set(), protected_rows=set()),
        ),
    )
    monkeypatch.setattr(
        filter_module,
        "run_from_df",
        lambda data, **kwargs: ProcessingResult(
            success=True,
            step="feature_filter",
            output_path=None,
            data=data.copy(),
            metadata=ProcessingMetadata(
                red_font_rows=set(),
                protected_rows=set(),
                blue_font_cells=[],
                deleted_feature_df=None,
            ),
        ),
    )


def test_cli_step_all_default_does_not_write_step_parquet_intermediates(monkeypatch, project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
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

        assert ".parquet" not in save_suffixes
        assert ".parquet" not in load_suffixes
        assert save_suffixes[-1] == ".xlsx"


def test_cli_persist_intermediate_writes_parquet_to_internal_cache_not_output(monkeypatch, project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        cache_root = base / "internal-cache"
        monkeypatch.setenv("MSPTK_PARQUET_CACHE_ROOT", str(cache_root))
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

        args = _make_cli_args(input_path=input_path, output_path=output_path, step="all")
        args.persist_intermediate = True
        rc = run_cli(args)
        assert rc == 0

        parquet_saves = [path for op, suffix, path in fake_handler.calls if op == "save" and suffix == ".parquet"]
        assert parquet_saves
        assert all(cache_root in path.parents for path in parquet_saves)
        assert all("OUTPUT" not in str(path) for path in parquet_saves)


def test_cli_single_step_filter_accepts_parquet_input(monkeypatch, project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
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


def test_cli_default_profile_uses_integrated_step_parameters(monkeypatch, project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
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

        import ms_preprocessing.adapters.data_organizer as organizer_module
        import ms_preprocessing.adapters.istd_marker as istd_module
        import ms_preprocessing.adapters.duplicate_remover as duplicate_module
        import ms_preprocessing.adapters.feature_filter as filter_module

        captured: dict[str, dict] = {}

        monkeypatch.setattr(
            organizer_module,
            "run_from_df",
            lambda data, **kwargs: (
                captured.setdefault("step1", dict(kwargs)),
                ProcessingResult(
                    success=True,
                    step="data_organizer",
                    output_path=None,
                    data=data.copy(),
                    metadata=ProcessingMetadata(sample_info=None),
                ),
            )[1],
        )
        monkeypatch.setattr(
            istd_module,
            "run_from_df",
            lambda data, **kwargs: (
                captured.setdefault("step2", dict(kwargs)),
                ProcessingResult(
                    success=True,
                    step="istd_marker",
                    output_path=None,
                    data=data.copy(),
                    metadata=ProcessingMetadata(red_font_rows=set(), protected_rows=set()),
                ),
            )[1],
        )
        monkeypatch.setattr(
            duplicate_module,
            "run_from_df",
            lambda data, **kwargs: (
                captured.setdefault("step3", dict(kwargs)),
                ProcessingResult(
                    success=True,
                    step="duplicate_remover",
                    output_path=None,
                    data=data.copy(),
                    metadata=ProcessingMetadata(red_font_rows=set(), protected_rows=set()),
                ),
            )[1],
        )
        monkeypatch.setattr(
            filter_module,
            "run_from_df",
            lambda data, **kwargs: (
                captured.setdefault("step4", dict(kwargs)),
                ProcessingResult(
                    success=True,
                    step="feature_filter",
                    output_path=None,
                    data=data.copy(),
                    metadata=ProcessingMetadata(
                        red_font_rows=set(),
                        protected_rows=set(),
                        blue_font_cells=[],
                        deleted_feature_df=None,
                    ),
                ),
            )[1],
        )

        rc = run_cli(_make_cli_args(input_path=input_path, output_path=output_path, step="all"))
        profile = get_pipeline_profile("default")

        assert rc == 0
        assert captured["step1"]["method_file"] == profile["step1"]["method_file"]
        assert captured["step2"]["ppm_tolerance"] == 20.0
        assert captured["step2"]["rt_tolerance"] == 1.5
        assert (
            str(captured["step2"]["istd_record_file"])
            if captured["step2"]["istd_record_file"]
            else ""
        ) == profile["step2"]["istd_record_file"]
        assert captured["step2"]["istd_record_date"] == "20260106"
        assert captured["step3"]["mz_tolerance_ppm"] == 20.0
        assert captured["step3"]["rt_tolerance"] == 1.0
        assert captured["step4"]["background_threshold"] == 0.33
        assert captured["step4"]["diff_threshold"] == 0.25
        assert captured["step4"]["qc_ratio_threshold"] == 0.25
        assert captured["step4"]["intensity_fc_threshold"] == 2.0
        assert captured["step4"]["enable_background_threshold"] is True
        assert captured["step4"]["enable_diff_threshold"] is True
        assert captured["step4"]["enable_qc_ratio_threshold"] is True
        assert captured["step4"]["enable_intensity_fc_threshold"] is True
