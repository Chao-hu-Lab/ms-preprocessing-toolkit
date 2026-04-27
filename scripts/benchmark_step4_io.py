"""Benchmark Step 4 I/O path and validate zero-as-missing behavior."""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

import pandas as pd
from ms_core.preprocessing.ms_quality_filter import FeatureFilter
from ms_core.preprocessing.settings import Settings
from ms_core.utils.file_handler import FileHandler


def detect_imputation_target_columns(df: pd.DataFrame) -> list[str]:
    """Return sample columns (groups + QC) that are imputation targets."""
    proc = FeatureFilter()
    group_info = proc._detect_sample_types(df)

    target_indices: set[int] = set()
    for cols in group_info.get("groups", {}).values():
        target_indices.update(cols)
    target_indices.update(group_info.get("qc_cols", []))

    return [str(df.columns[idx]) for idx in sorted(target_indices)]


def count_zero_and_nan(df: pd.DataFrame, target_columns: list[str]) -> tuple[int, int]:
    """Count zero and NaN cells in data rows for the given target columns."""
    if not target_columns or len(df) <= 1:
        return 0, 0

    block = df.loc[1:, target_columns].apply(pd.to_numeric, errors="coerce")
    zero_count = int((block == 0).sum().sum())
    nan_count = int(block.isna().sum().sum())
    return zero_count, nan_count


def run_benchmark(
    input_path: Path,
    output_path: Path,
    bg_threshold: float,
    diff_threshold: float,
    intensity_fc_threshold: float,
    qc_threshold: float,
) -> dict[str, Any]:
    """Execute load/process/save benchmark and return summary metrics."""
    handler = FileHandler()
    filter_proc = FeatureFilter()

    t0 = time.perf_counter()
    input_df, _ = handler.load_data(input_path)
    load_seconds = time.perf_counter() - t0

    pre_targets = detect_imputation_target_columns(input_df)
    pre_zero_count, pre_nan_count = count_zero_and_nan(input_df, pre_targets)

    t1 = time.perf_counter()
    result = filter_proc.process(
        input_df,
        background_threshold=bg_threshold,
        diff_threshold=diff_threshold,
        intensity_fc_threshold=intensity_fc_threshold,
        qc_ratio_threshold=qc_threshold,
    )
    process_seconds = time.perf_counter() - t1

    if not result.success or result.data is None:
        raise RuntimeError(f"Step 4 processing failed: {result.message}")

    post_targets = detect_imputation_target_columns(result.data)
    post_zero_count, post_nan_count = count_zero_and_nan(result.data, post_targets)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    t2 = time.perf_counter()
    handler.save_data(
        result.data,
        output_path,
        sheet_name="RawIntensity",
        save_parquet_cache=Settings.SAVE_PARQUET_CACHE,
    )
    save_seconds = time.perf_counter() - t2

    previous_cache_setting = Settings.SAVE_PARQUET_CACHE
    try:
        Settings.SAVE_PARQUET_CACHE = False
        t3 = time.perf_counter()
        handler.load_data(output_path)
        cold_load_seconds = time.perf_counter() - t3

        Settings.SAVE_PARQUET_CACHE = True
        t4 = time.perf_counter()
        _, warm_meta = handler.load_data(output_path)
        warm_load_seconds = time.perf_counter() - t4
    finally:
        Settings.SAVE_PARQUET_CACHE = previous_cache_setting

    warm_cache_speedup = (
        cold_load_seconds / warm_load_seconds if warm_load_seconds > 0 else None
    )

    stats = result.statistics or {}
    summary = {
        "input_path": str(input_path),
        "output_path": str(output_path),
        "load_seconds": load_seconds,
        "process_seconds": process_seconds,
        "save_seconds": save_seconds,
        "cold_load_seconds": cold_load_seconds,
        "warm_load_seconds": warm_load_seconds,
        "warm_cache_speedup": warm_cache_speedup,
        "pre_zero_count": pre_zero_count,
        "pre_nan_count": pre_nan_count,
        "post_zero_count": post_zero_count,
        "post_nan_count": post_nan_count,
        "cells_imputed": int(stats.get("cells_imputed", 0)),
        "cells_imputed_from_nan": int(stats.get("cells_imputed_from_nan", 0)),
        "cells_imputed_from_zero": int(stats.get("cells_imputed_from_zero", 0)),
        "warm_load_format": warm_meta.get("format", "unknown"),
    }
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark Step 4 I/O and zero-as-missing behavior.")
    parser.add_argument("--input", required=True, help="Input dataset path (typically STEP3 output xlsx).")
    parser.add_argument("--output", help="Optional benchmark output path (xlsx).")
    parser.add_argument("--bg", type=float, default=0.5, help="Background threshold.")
    parser.add_argument("--intensity-fc", type=float, default=2.0, help="Intensity fold-change threshold.")
    parser.add_argument("--diff", type=float, default=0.5, help="Diff threshold.")
    parser.add_argument("--qc", type=float, default=0.4, help="QC ratio threshold.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
    else:
        output_path = (
            Path.cwd()
            / "OUTPUT"
            / f"STEP4_BENCH_{input_path.stem}.xlsx"
        )

    summary = run_benchmark(
        input_path=input_path,
        output_path=output_path,
        bg_threshold=args.bg,
        intensity_fc_threshold=args.intensity_fc,
        diff_threshold=args.diff,
        qc_threshold=args.qc,
    )

    print("=== Step4 Benchmark Summary ===")
    for key in [
        "input_path",
        "output_path",
        "load_seconds",
        "process_seconds",
        "save_seconds",
        "cold_load_seconds",
        "warm_load_seconds",
        "warm_cache_speedup",
        "pre_zero_count",
        "pre_nan_count",
        "post_zero_count",
        "post_nan_count",
        "cells_imputed",
        "cells_imputed_from_nan",
        "cells_imputed_from_zero",
        "warm_load_format",
    ]:
        value = summary[key]
        if isinstance(value, float):
            print(f"{key}={value:.6f}")
        else:
            print(f"{key}={value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
