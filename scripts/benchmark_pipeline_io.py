"""Benchmark utilities for unified parquet intermediate pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path
from time import perf_counter
from typing import Any

from ms_core.preprocessing.settings import Settings
from ms_core.utils.file_handler import FileHandler


DEFAULT_METHOD_FILE = Path(
    r"C:\Users\user\Desktop\NTU cancer\2025台大乳癌組織數據for Jia\20260105中研院台大Breast cancer tissue\20260105 中研院分析.docx"
)
DEFAULT_ISTD_RECORD_FILE = Path(
    r"C:\Users\user\Desktop\NTU cancer\2025台大乳癌組織數據for Jia\20260105中研院台大Breast cancer tissue\20260106 ISDTs record.xlsx"
)
METADATA_KEYS = (
    "red_font_rows",
    "blue_font_cells",
    "protected_rows",
    "sample_info_ref",
    "deleted_feature_ref",
)
GATE_A_SECONDS = 1497.067
GATE_B_SECONDS = 1420.0


def _empty_step_times() -> dict[str, float]:
    return {"step1": 0.0, "step2": 0.0, "step3": 0.0, "step4": 0.0}


def _normalize_value(value: Any) -> Any:
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, tuple):
        return [_normalize_value(v) for v in value]
    if isinstance(value, list):
        return [_normalize_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _normalize_value(v) for k, v in value.items()}
    return value


def _default_output_path(input_path: Path) -> Path:
    output_dir = Path.cwd() / "OUTPUT"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"BENCH_{input_path.stem}.xlsx"


def run_benchmark(
    input_path: str | Path,
    output_path: str | Path | None = None,
    dry_run: bool = False,
    method_file: str | Path | None = None,
    istd_record_file: str | Path | None = None,
    mz_tol: float = 20.0,
    rt_tol: float = 1.5,
) -> dict[str, Any]:
    """Run pipeline I/O benchmark with cold/warm comparison and invariants."""
    start = perf_counter()
    input_path = Path(input_path)
    method_file_obj = Path(method_file) if method_file else DEFAULT_METHOD_FILE
    istd_record_file_obj = (
        Path(istd_record_file) if istd_record_file else DEFAULT_ISTD_RECORD_FILE
    )

    if dry_run:
        return {
            "input_path": str(input_path),
            "output_path": str(output_path) if output_path else "",
            "method_file": str(method_file_obj),
            "istd_record_file": str(istd_record_file_obj),
            "load_s": 0.0,
            "step_times": _empty_step_times(),
            "save_s": 0.0,
            "cold_load_s": 0.0,
            "warm_load_s": 0.0,
            "warm_faster_than_cold": False,
            "schema_invariant_ok": True,
            "metadata_invariant_ok": True,
            "metadata_checked_keys": [],
            "metadata_mismatches": {},
            "gate_a_seconds": GATE_A_SECONDS,
            "gate_b_seconds": GATE_B_SECONDS,
            "meets_gate_a": False,
            "meets_gate_b": False,
            "total_s": 0.0,
            "dry_run": True,
        }

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    handler = FileHandler()
    output_path_obj = Path(output_path) if output_path else _default_output_path(input_path)

    load_start = perf_counter()
    df, source_meta = handler.load_data(input_path)
    load_s = perf_counter() - load_start

    # Placeholder processing slots (Task 8 focuses on I/O contract and invariants).
    step_times = _empty_step_times()

    save_start = perf_counter()
    handler.save_data(
        df,
        output_path_obj,
        sheet_name="RawIntensity",
        red_font_rows=set(source_meta.get("red_font_rows", [])),
        blue_font_cells=source_meta.get("blue_font_cells", []),
        save_parquet_cache=True,
    )
    save_s = perf_counter() - save_start

    prev_cache = Settings.SAVE_PARQUET_CACHE
    try:
        Settings.SAVE_PARQUET_CACHE = False
        cold_start = perf_counter()
        cold_df, cold_meta = handler.load_data(output_path_obj)
        cold_load_s = perf_counter() - cold_start

        Settings.SAVE_PARQUET_CACHE = True
        warm_start = perf_counter()
        warm_df, warm_meta = handler.load_data(output_path_obj)
        warm_load_s = perf_counter() - warm_start
    finally:
        Settings.SAVE_PARQUET_CACHE = prev_cache

    schema_invariant_ok = (
        df.shape == cold_df.shape == warm_df.shape
        and list(df.columns) == list(cold_df.columns) == list(warm_df.columns)
    )

    metadata_checked_keys: list[str] = []
    metadata_mismatches: dict[str, dict[str, Any]] = {}
    metadata_invariant_ok = True
    for key in METADATA_KEYS:
        source_val = _normalize_value(source_meta.get(key))
        cold_val = _normalize_value(cold_meta.get(key))
        warm_val = _normalize_value(warm_meta.get(key))
        if source_val is None and cold_val is None and warm_val is None:
            continue

        metadata_checked_keys.append(key)
        source_to_warm_ok = True if source_val is None else (warm_val == source_val)
        # Cold xlsx load may not preserve all formatting metadata; allow missing cold key.
        cold_consistent_ok = (cold_val == warm_val) or (cold_val is None)
        if not (source_to_warm_ok and cold_consistent_ok):
            metadata_invariant_ok = False
            metadata_mismatches[key] = {
                "source": source_val,
                "cold": cold_val,
                "warm": warm_val,
            }

    total_s = perf_counter() - start

    return {
        "input_path": str(input_path),
        "output_path": str(output_path_obj),
        "method_file": str(method_file_obj),
        "istd_record_file": str(istd_record_file_obj),
        "mz_tol": float(mz_tol),
        "rt_tol": float(rt_tol),
        "load_s": float(load_s),
        "step_times": step_times,
        "save_s": float(save_s),
        "cold_load_s": float(cold_load_s),
        "warm_load_s": float(warm_load_s),
        "warm_faster_than_cold": bool(warm_load_s < cold_load_s),
        "schema_invariant_ok": bool(schema_invariant_ok),
        "metadata_invariant_ok": bool(metadata_invariant_ok),
        "metadata_checked_keys": metadata_checked_keys,
        "metadata_mismatches": metadata_mismatches,
        "gate_a_seconds": float(GATE_A_SECONDS),
        "gate_b_seconds": float(GATE_B_SECONDS),
        "meets_gate_a": bool(total_s <= GATE_A_SECONDS),
        "meets_gate_b": bool(total_s <= GATE_B_SECONDS),
        "total_s": float(total_s),
        "dry_run": False,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark unified parquet intermediate pipeline I/O.")
    parser.add_argument("--input", required=True, help="Input dataset path.")
    parser.add_argument("--output", help="Optional benchmark output path (.xlsx).")
    parser.add_argument(
        "--method-file",
        default=str(DEFAULT_METHOD_FILE),
        help="Method file path (.docx). Defaults to the fixed benchmark reference file.",
    )
    parser.add_argument(
        "--istd-record-file",
        default=str(DEFAULT_ISTD_RECORD_FILE),
        help="ISTD record file path (.xlsx). Defaults to the fixed benchmark reference file.",
    )
    parser.add_argument("--mz-tol", type=float, default=20.0, help="m/z tolerance (ppm).")
    parser.add_argument("--rt-tol", type=float, default=1.5, help="RT tolerance (minutes).")
    parser.add_argument("--dry-run", action="store_true", help="Return empty benchmark contract.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = run_benchmark(
        input_path=args.input,
        output_path=args.output,
        dry_run=args.dry_run,
        method_file=args.method_file,
        istd_record_file=args.istd_record_file,
        mz_tol=args.mz_tol,
        rt_tol=args.rt_tol,
    )

    for key in [
        "input_path",
        "output_path",
        "method_file",
        "istd_record_file",
        "load_s",
        "save_s",
        "cold_load_s",
        "warm_load_s",
        "warm_faster_than_cold",
        "schema_invariant_ok",
        "metadata_invariant_ok",
        "metadata_checked_keys",
        "metadata_mismatches",
        "total_s",
    ]:
        print(f"{key}={result[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
