"""Baseline contract tests for pipeline I/O benchmark."""


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
