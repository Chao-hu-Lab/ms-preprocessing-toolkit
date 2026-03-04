"""Benchmark utilities for end-to-end pipeline I/O timing."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any


def _empty_step_times() -> dict[str, float]:
    return {"step1": 0.0, "step2": 0.0, "step3": 0.0, "step4": 0.0}


def run_benchmark(input_path: str | Path, dry_run: bool = False) -> dict[str, Any]:
    """Return a stable, JSON-serializable benchmark contract."""
    start = perf_counter()
    input_path = Path(input_path)

    if dry_run:
        return {
            "input_path": str(input_path),
            "load_s": 0.0,
            "step_times": _empty_step_times(),
            "save_s": 0.0,
            "total_s": 0.0,
            "dry_run": True,
        }

    load_start = perf_counter()
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    load_s = perf_counter() - load_start

    step_times = _empty_step_times()

    save_start = perf_counter()
    save_s = perf_counter() - save_start

    total_s = perf_counter() - start
    return {
        "input_path": str(input_path),
        "load_s": float(load_s),
        "step_times": step_times,
        "save_s": float(save_s),
        "total_s": float(total_s),
        "dry_run": False,
    }
