"""Integration checks for unified parquet pipeline benchmark contract."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from ms_core.utils.file_handler import FileHandler


def test_parquet_pipeline_preserves_output_schema_and_key_metadata(monkeypatch, project_temp_dir) -> None:
    from scripts.benchmark_pipeline_io import run_benchmark

    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        cache_root = base / "internal-cache"
        monkeypatch.setenv("MSPTK_PARQUET_CACHE_ROOT", str(cache_root))
        input_path = base / "input.parquet"
        output_path = base / "BENCH_input.xlsx"
        df = pd.DataFrame(
            {
                "Mz/RT": ["Sample_Type", "100.1/1.0"],
                "Tolerance": ["na", "na"],
                "Case1": ["case", 1000],
                "Control1": ["control", 1200],
                "QC1": ["qc", 1100],
            }
        )
        handler = FileHandler()
        handler.save_data(
            df,
            input_path,
            red_font_rows={1},
            blue_font_cells=[(1, 1)],
        )

        result = run_benchmark(input_path=input_path, output_path=output_path, dry_run=False)

        assert result["schema_invariant_ok"] is True
        assert result["metadata_invariant_ok"] is True
        assert isinstance(result["cold_load_s"], float)
        assert isinstance(result["warm_load_s"], float)
        assert result["metadata_checked_keys"]
