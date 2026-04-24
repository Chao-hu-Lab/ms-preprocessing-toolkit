"""Baseline contract tests for pipeline I/O benchmark."""

import importlib
import json
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

    assert result["method_file"] == (str(DEFAULT_METHOD_FILE) if DEFAULT_METHOD_FILE else "")
    assert result["istd_record_file"] == (str(DEFAULT_ISTD_RECORD_FILE) if DEFAULT_ISTD_RECORD_FILE else "")


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
    monkeypatch.setenv("MSPTK_ISTD_RECORD_DATE", "20260111")

    defaults = importlib.import_module("ms_preprocessing.config.pipeline_defaults")
    benchmark = importlib.import_module("scripts.benchmark_pipeline_io")

    try:
        defaults = importlib.reload(defaults)
        benchmark = importlib.reload(benchmark)
        result = benchmark.run_benchmark(input_path="dummy.xlsx", dry_run=True)

        assert defaults.DEFAULT_METHOD_FILE == Path("env-method.docx")
        assert defaults.DEFAULT_ISTD_RECORD_FILE == Path("env-istd.xlsx")
        assert defaults.DEFAULT_ISTD_RECORD_DATE == "20260111"
        assert defaults.STEP2_PARAMS["istd_record_date"] == "20260111"
        assert result["method_file"] == "env-method.docx"
        assert result["istd_record_file"] == "env-istd.xlsx"
    finally:
        monkeypatch.delenv("MSPTK_METHOD_FILE", raising=False)
        monkeypatch.delenv("MSPTK_ISTD_RECORD_FILE", raising=False)
        monkeypatch.delenv("MSPTK_ISTD_RECORD_DATE", raising=False)
        importlib.reload(defaults)
        importlib.reload(benchmark)


def test_pipeline_defaults_follow_local_reference_config(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "local_reference_paths.json"
    config_path.write_text(
        json.dumps(
            {
                "method_file": "local-method.docx",
                "istd_record_file": "local-istd.xlsx",
                "istd_record_date": "20260111",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("MSPTK_LOCAL_REFERENCE_CONFIG", str(config_path))
    defaults = importlib.import_module("ms_preprocessing.config.pipeline_defaults")
    benchmark = importlib.import_module("scripts.benchmark_pipeline_io")

    try:
        defaults = importlib.reload(defaults)
        benchmark = importlib.reload(benchmark)
        result = benchmark.run_benchmark(input_path="dummy.xlsx", dry_run=True)

        assert defaults.DEFAULT_METHOD_FILE == Path("local-method.docx")
        assert defaults.DEFAULT_ISTD_RECORD_FILE == Path("local-istd.xlsx")
        assert defaults.DEFAULT_ISTD_RECORD_DATE == "20260111"
        assert defaults.STEP2_PARAMS["istd_record_date"] == "20260111"
        assert result["method_file"] == "local-method.docx"
        assert result["istd_record_file"] == "local-istd.xlsx"
    finally:
        monkeypatch.delenv("MSPTK_LOCAL_REFERENCE_CONFIG", raising=False)
        importlib.reload(defaults)
        importlib.reload(benchmark)


def test_pipeline_defaults_are_empty_without_local_or_env_overrides(tmp_path, monkeypatch) -> None:
    missing_config_path = tmp_path / "missing-local-reference-paths.json"

    monkeypatch.setenv("MSPTK_LOCAL_REFERENCE_CONFIG", str(missing_config_path))
    monkeypatch.delenv("MSPTK_METHOD_FILE", raising=False)
    monkeypatch.delenv("MSPTK_ISTD_RECORD_FILE", raising=False)

    defaults = importlib.import_module("ms_preprocessing.config.pipeline_defaults")
    benchmark = importlib.import_module("scripts.benchmark_pipeline_io")

    try:
        defaults = importlib.reload(defaults)
        benchmark = importlib.reload(benchmark)
        result = benchmark.run_benchmark(input_path="dummy.xlsx", dry_run=True)

        assert defaults.DEFAULT_METHOD_FILE is None
        assert defaults.DEFAULT_ISTD_RECORD_FILE is None
        assert defaults.DEFAULT_ISTD_RECORD_DATE == "20260106"
        assert defaults.STEP2_PARAMS["istd_record_date"] == "20260106"
        assert result["method_file"] == ""
        assert result["istd_record_file"] == ""
    finally:
        monkeypatch.delenv("MSPTK_LOCAL_REFERENCE_CONFIG", raising=False)
        importlib.reload(defaults)
        importlib.reload(benchmark)
