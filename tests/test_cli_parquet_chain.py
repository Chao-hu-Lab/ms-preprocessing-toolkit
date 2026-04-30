"""Tests for CLI parquet intermediate chaining behavior."""

from __future__ import annotations

import importlib
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
    xic_results_file = input_path.with_name("xic_results.xlsx")
    if step in {"istd", "all"} and not xic_results_file.exists():
        xic_results_file.write_text("placeholder", encoding="utf-8")

    return SimpleNamespace(
        input=str(input_path),
        output=str(output_path) if output_path else None,
        profile="default",
        method_file=None,
        step=step,
        mz_tol=None,
        xic_results_file=str(xic_results_file),
        rt_tol=None,
        merge_mode=None,
        enable_degeneracy_annotation=False,
        degeneracy_ppm_tol=None,
        degeneracy_rt_tol=None,
        degeneracy_corr_threshold=None,
        degeneracy_min_corr_points=None,
        degeneracy_adduct_table_file=None,
        bg_threshold=None,
        intensity_fc_threshold=None,
        high_det_thresh=None,
        low_det_thresh=None,
        qc_ratio_threshold=None,
        persist_intermediate=False,
        export_deleted_feature=False,
        no_gui=True,
        version=False,
    )


def _patch_cli_dependencies(monkeypatch, fake_handler: _FakeFileHandler) -> None:
    import ms_preprocessing.adapters.data_organizer as organizer_module
    import ms_preprocessing.adapters.duplicate_remover as duplicate_module
    import ms_preprocessing.adapters.feature_filter as filter_module
    import ms_preprocessing.adapters.istd_marker as istd_module
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


def test_cli_step2_requires_xic_results_file(monkeypatch, project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        df = pd.DataFrame(
            {
                "Mz/RT": ["Sample_Type", "100.1/1.0"],
                "Case1": ["case", 1000],
            }
        )
        input_path = base / "input.csv"
        df.to_csv(input_path, index=False)
        fake_handler = _FakeFileHandler(input_df=df)
        _patch_cli_dependencies(monkeypatch, fake_handler)

        args = _make_cli_args(input_path=input_path, output_path=None, step="istd")
        args.xic_results_file = None

        import ms_preprocessing.config.pipeline_defaults as defaults

        try:
            with monkeypatch.context() as isolated_env:
                isolated_env.setenv(
                    "MSPTK_LOCAL_REFERENCE_CONFIG",
                    str(base / "missing-local-reference-paths.json"),
                )
                importlib.reload(defaults)
                rc = run_cli(args)
        finally:
            importlib.reload(defaults)

        assert rc == 1
        assert not fake_handler.calls


def test_cli_step2_rejects_missing_xic_results_file_path(monkeypatch, project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        df = pd.DataFrame(
            {
                "Mz/RT": ["Sample_Type", "100.1/1.0"],
                "Case1": ["case", 1000],
            }
        )
        input_path = base / "input.csv"
        df.to_csv(input_path, index=False)
        fake_handler = _FakeFileHandler(input_df=df)
        _patch_cli_dependencies(monkeypatch, fake_handler)

        args = _make_cli_args(input_path=input_path, output_path=None, step="istd")
        args.xic_results_file = str(base / "missing_xic.xlsx")

        rc = run_cli(args)

        assert rc == 1
        assert not fake_handler.calls


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
        import ms_preprocessing.adapters.duplicate_remover as duplicate_module
        import ms_preprocessing.adapters.feature_filter as filter_module
        import ms_preprocessing.adapters.istd_marker as istd_module

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
        assert captured["step2"]["xic_results_file"] == input_path.with_name("xic_results.xlsx")
        assert "ppm_tolerance" not in captured["step2"]
        assert "rt_tolerance" not in captured["step2"]
        assert "istd_mz_list" not in captured["step2"]
        assert "istd_record_file" not in captured["step2"]
        assert "istd_record_date" not in captured["step2"]
        assert captured["step3"]["mz_tolerance_ppm"] == 20.0
        assert captured["step3"]["rt_tolerance"] == 0.1
        assert captured["step3"]["merge_mode"] == "per_sample_max"
        assert captured["step3"]["enable_degeneracy_annotation"] is False
        assert captured["step3"]["degeneracy_ppm_tolerance"] == 20.0
        assert captured["step3"]["degeneracy_rt_tolerance"] == 0.05
        assert captured["step3"]["degeneracy_correlation_threshold"] == 0.8
        assert captured["step3"]["degeneracy_min_correlation_points"] == 3
        assert captured["step3"]["degeneracy_adduct_table_file"] == ""
        assert captured["step4"]["background_threshold"] == 0.33
        assert captured["step4"]["high_det_thresh"] == 0.8
        assert captured["step4"]["low_det_thresh"] == 0.2
        assert captured["step4"]["qc_ratio_threshold"] == 0.25
        assert captured["step4"]["intensity_fc_threshold"] == 2.0
        assert captured["step4"]["ratio_rescue_threshold"] == 3.0
        assert captured["step4"]["enable_background_threshold"] is True
        assert captured["step4"]["enable_qc_ratio_threshold"] is True
        assert captured["step4"]["enable_intensity_fc_threshold"] is False
        assert captured["step4"]["enable_ratio_rescue"] is True


def test_cli_xic_results_file_override_reaches_step2(monkeypatch, project_temp_dir) -> None:
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
        xic_results_file = base / "xic_results.xlsx"
        xic_results_file.write_text("placeholder", encoding="utf-8")

        fake_handler = _FakeFileHandler(input_df=df)
        _patch_cli_dependencies(monkeypatch, fake_handler)

        import ms_preprocessing.adapters.istd_marker as istd_module

        captured: dict[str, dict] = {}
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

        args = _make_cli_args(input_path=input_path, output_path=output_path, step="istd")
        args.xic_results_file = str(xic_results_file)

        rc = run_cli(args)

        assert rc == 0
        assert captured["step2"]["xic_results_file"] == xic_results_file


def test_cli_merge_mode_override_reaches_step3(monkeypatch, project_temp_dir) -> None:
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

        import ms_preprocessing.adapters.duplicate_remover as duplicate_module

        captured: dict[str, dict] = {}
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

        args = _make_cli_args(input_path=input_path, output_path=output_path, step="duplicate-removal")
        args.merge_mode = "fill_gaps"
        rc = run_cli(args)

        assert rc == 0
        assert captured["step3"]["merge_mode"] == "fill_gaps"
