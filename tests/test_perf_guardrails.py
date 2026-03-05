"""Performance guardrail contract tests."""

from __future__ import annotations


def test_perf_contract_contains_io_breakdown_and_gate_fields() -> None:
    from scripts.benchmark_pipeline_io import run_benchmark

    result = run_benchmark(input_path="dummy.xlsx", dry_run=True)

    assert {"load_s", "save_s", "total_s", "warm_faster_than_cold"} <= set(result.keys())
    assert "gate_a_seconds" in result
    assert "gate_b_seconds" in result
    assert "meets_gate_a" in result
    assert "meets_gate_b" in result
