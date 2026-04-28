"""Baseline contract tests for pipeline I/O and Step 2 reference defaults."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

REFERENCE_ENV_VARS = (
    "MSPTK_METHOD_FILE",
    "MSPTK_XIC_RESULTS_FILE",
    "MSPTK_LOCAL_REFERENCE_CONFIG",
    "MSPTK_ISTD_RECORD_FILE",
    "MSPTK_ISTD_RECORD_DATE",
)


def _base_cli_args(**overrides):
    values = {
        "profile": "default",
        "method_file": None,
        "xic_results_file": None,
        "mz_tol": None,
        "rt_tol": None,
        "merge_mode": None,
        "enable_degeneracy_annotation": False,
        "degeneracy_ppm_tol": None,
        "degeneracy_rt_tol": None,
        "degeneracy_corr_threshold": None,
        "degeneracy_min_corr_points": None,
        "degeneracy_adduct_table_file": None,
        "bg_threshold": None,
        "intensity_fc_threshold": None,
        "high_det_thresh": None,
        "low_det_thresh": None,
        "qc_ratio_threshold": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _reload_reference_modules():
    defaults = importlib.import_module("ms_preprocessing.config.pipeline_defaults")
    benchmark = importlib.import_module("scripts.benchmark_pipeline_io")
    return importlib.reload(defaults), importlib.reload(benchmark)


def _clear_reference_env(monkeypatch_ctx) -> None:
    for env_var in REFERENCE_ENV_VARS:
        monkeypatch_ctx.delenv(env_var, raising=False)


def test_baseline_contract_records_load_process_save_sections() -> None:
    from scripts.benchmark_pipeline_io import run_benchmark

    result = run_benchmark(input_path="dummy.xlsx", dry_run=True)
    assert {"load_s", "step_times", "save_s", "total_s"} <= set(result.keys())


def test_baseline_contract_uses_xic_default_reference_file() -> None:
    from ms_preprocessing.config.pipeline_defaults import (
        DEFAULT_METHOD_FILE,
        DEFAULT_XIC_RESULTS_FILE,
    )
    from scripts.benchmark_pipeline_io import run_benchmark

    result = run_benchmark(input_path="dummy.xlsx", dry_run=True)

    assert result["method_file"] == (str(DEFAULT_METHOD_FILE) if DEFAULT_METHOD_FILE else "")
    assert result["xic_results_file"] == (
        str(DEFAULT_XIC_RESULTS_FILE) if DEFAULT_XIC_RESULTS_FILE else ""
    )


def test_cli_step_parameters_allow_overriding_xic_reference_file() -> None:
    from ms_preprocessing.main import _resolve_cli_step_parameters

    resolved = _resolve_cli_step_parameters(
        _base_cli_args(
            method_file="custom-method.docx",
            xic_results_file="custom-xic.xlsx",
        )
    )

    assert resolved["step1"]["method_file"] == "custom-method.docx"
    assert resolved["step2"]["xic_results_file"] == "custom-xic.xlsx"
    assert "istd_record_file" not in resolved["step2"]
    assert "istd_record_date" not in resolved["step2"]
    assert "istd_mz_list" not in resolved["step2"]


def test_benchmark_defaults_follow_pipeline_env_overrides(monkeypatch) -> None:
    try:
        with monkeypatch.context() as env:
            _clear_reference_env(env)
            env.setenv("MSPTK_METHOD_FILE", "env-method.docx")
            env.setenv("MSPTK_XIC_RESULTS_FILE", "env-xic.xlsx")
            defaults, benchmark = _reload_reference_modules()
            result = benchmark.run_benchmark(input_path="dummy.xlsx", dry_run=True)

            assert defaults.DEFAULT_METHOD_FILE == Path("env-method.docx")
            assert defaults.DEFAULT_XIC_RESULTS_FILE == Path("env-xic.xlsx")
            assert defaults.STEP2_PARAMS["xic_results_file"] == "env-xic.xlsx"
            assert result["method_file"] == "env-method.docx"
            assert result["xic_results_file"] == "env-xic.xlsx"
    finally:
        _reload_reference_modules()


def test_pipeline_defaults_follow_local_reference_config(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "local_reference_paths.json"
    config_path.write_text(
        json.dumps(
            {
                "method_file": "local-method.docx",
                "xic_results_file": "local-xic.xlsx",
            }
        ),
        encoding="utf-8",
    )

    try:
        with monkeypatch.context() as env:
            _clear_reference_env(env)
            env.setenv("MSPTK_LOCAL_REFERENCE_CONFIG", str(config_path))
            defaults, benchmark = _reload_reference_modules()
            result = benchmark.run_benchmark(input_path="dummy.xlsx", dry_run=True)

            assert defaults.DEFAULT_METHOD_FILE == Path("local-method.docx")
            assert defaults.DEFAULT_XIC_RESULTS_FILE == Path("local-xic.xlsx")
            assert defaults.STEP2_PARAMS["xic_results_file"] == "local-xic.xlsx"
            assert result["method_file"] == "local-method.docx"
            assert result["xic_results_file"] == "local-xic.xlsx"
    finally:
        _reload_reference_modules()


def test_pipeline_defaults_are_empty_without_local_or_env_overrides(tmp_path, monkeypatch) -> None:
    missing_config_path = tmp_path / "missing-local-reference-paths.json"

    try:
        with monkeypatch.context() as env:
            _clear_reference_env(env)
            env.setenv("MSPTK_LOCAL_REFERENCE_CONFIG", str(missing_config_path))
            defaults, benchmark = _reload_reference_modules()
            result = benchmark.run_benchmark(input_path="dummy.xlsx", dry_run=True)

            assert defaults.DEFAULT_METHOD_FILE is None
            assert defaults.DEFAULT_XIC_RESULTS_FILE is None
            assert defaults.STEP2_PARAMS["xic_results_file"] == ""
            assert result["method_file"] == ""
            assert result["xic_results_file"] == ""
    finally:
        _reload_reference_modules()


def test_pipeline_defaults_import_allows_legacy_step2_env_for_non_step2_paths(
    tmp_path,
    monkeypatch,
) -> None:
    try:
        with monkeypatch.context() as env:
            _clear_reference_env(env)
            env.setenv("MSPTK_ISTD_RECORD_FILE", "legacy-istd.xlsx")
            env.setenv("MSPTK_LOCAL_REFERENCE_CONFIG", str(tmp_path / "missing-config.json"))
            defaults, _ = _reload_reference_modules()

            assert defaults.STEP2_PARAMS["xic_results_file"] == ""
    finally:
        _reload_reference_modules()


def test_pipeline_defaults_import_allows_legacy_step2_local_config(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "local_reference_paths.json"
    config_path.write_text(
        json.dumps({"istd_record_file": "legacy-istd.xlsx"}),
        encoding="utf-8",
    )

    try:
        with monkeypatch.context() as env:
            _clear_reference_env(env)
            env.setenv("MSPTK_LOCAL_REFERENCE_CONFIG", str(config_path))
            defaults, _ = _reload_reference_modules()

            assert defaults.STEP2_PARAMS["xic_results_file"] == ""
    finally:
        _reload_reference_modules()


def test_local_reference_paths_example_uses_xic_source_key_only() -> None:
    config = json.loads(Path("config/local_reference_paths.example.json").read_text(encoding="utf-8"))

    assert "method_file" in config
    assert "xic_results_file" in config
    assert "istd_record_file" not in config
    assert "istd_record_date" not in config
    assert "istd_mz_list" not in config
