"""Baseline contract tests for pipeline I/O benchmark."""


def test_baseline_contract_records_load_process_save_sections() -> None:
    from scripts.benchmark_pipeline_io import run_benchmark

    result = run_benchmark(input_path="dummy.xlsx", dry_run=True)
    assert {"load_s", "step_times", "save_s", "total_s"} <= set(result.keys())
