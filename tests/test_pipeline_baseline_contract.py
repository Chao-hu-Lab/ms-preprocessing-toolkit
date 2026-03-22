"""Baseline contract tests for pipeline I/O benchmark."""

import importlib
from pathlib import Path


def test_baseline_contract_records_load_process_save_sections() -> None:
    from scripts.benchmark_pipeline_io import run_benchmark

    result = run_benchmark(input_path="dummy.xlsx", dry_run=True)
    assert {"load_s", "step_times", "save_s", "total_s"} <= set(result.keys())


def test_baseline_contract_uses_fixed_default_reference_files() -> None:
    from scripts.benchmark_pipeline_io import (
        DEFAULT_ISTD_RECORD_FILE,
        DEFAULT_METHOD_FILE,
        run_benchmark,
    )

    result = run_benchmark(input_path="dummy.xlsx", dry_run=True)

    assert result["method_file"] == str(DEFAULT_METHOD_FILE)
    assert result["istd_record_file"] == str(DEFAULT_ISTD_RECORD_FILE)


def test_cli_args_allow_overriding_fixed_reference_files(monkeypatch) -> None:
    from scripts.benchmark_pipeline_io import _parse_args

    monkeypatch.setattr(
        "sys.argv",
        [
            "benchmark_pipeline_io.py",
            "--input",
            "dummy.xlsx",
            "--method-file",
            "custom-method.docx",
            "--istd-record-file",
            "custom-istd.xlsx",
        ],
    )

    args = _parse_args()

    assert args.method_file == "custom-method.docx"
    assert args.istd_record_file == "custom-istd.xlsx"


def test_benchmark_defaults_follow_pipeline_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("MSPTK_METHOD_FILE", "env-method.docx")
    monkeypatch.setenv("MSPTK_ISTD_RECORD_FILE", "env-istd.xlsx")

    defaults = importlib.import_module("ms_preprocessing.config.pipeline_defaults")
    benchmark = importlib.import_module("scripts.benchmark_pipeline_io")

    try:
        defaults = importlib.reload(defaults)
        benchmark = importlib.reload(benchmark)
        result = benchmark.run_benchmark(input_path="dummy.xlsx", dry_run=True)

        assert defaults.DEFAULT_METHOD_FILE == Path("env-method.docx")
        assert defaults.DEFAULT_ISTD_RECORD_FILE == Path("env-istd.xlsx")
        assert result["method_file"] == "env-method.docx"
        assert result["istd_record_file"] == "env-istd.xlsx"
    finally:
        monkeypatch.delenv("MSPTK_METHOD_FILE", raising=False)
        monkeypatch.delenv("MSPTK_ISTD_RECORD_FILE", raising=False)
        importlib.reload(defaults)
        importlib.reload(benchmark)
