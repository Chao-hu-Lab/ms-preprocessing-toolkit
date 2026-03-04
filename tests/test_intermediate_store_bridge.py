"""Bridge tests for toolkit FileHandler and ms-core IntermediateStore."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd


def test_toolkit_file_handler_uses_intermediate_store_for_parquet_paths() -> None:
    from ms_preprocessing.utils.file_handler import FileHandler

    df = pd.DataFrame(
        {
            "Mz/RT": ["100.1/1.0", "200.2/2.0"],
            "Sample1": [10.0, 20.0],
        }
    )
    handler = FileHandler()

    with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
        parquet_path = Path(temp_dir) / "step2.parquet"
        handler.save_data(
            df=df,
            file_path=parquet_path,
            red_font_rows={1},
            blue_font_cells=[(1, 1)],
        )

        meta_path = parquet_path.with_suffix(parquet_path.suffix + ".meta.json")
        assert meta_path.exists()

        loaded_df, loaded_meta = handler.load_data(parquet_path)
        pd.testing.assert_frame_equal(loaded_df, df)
        assert loaded_meta.get("red_font_rows") == [1]
        assert loaded_meta.get("blue_font_cells") == [[1, 1]]
