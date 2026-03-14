"""Tests for shared parquet normalization helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def test_normalize_dataframe_for_parquet_uses_positional_updates_with_duplicate_labels() -> None:
    from ms_preprocessing.utils.parquet_compat import normalize_dataframe_for_parquet

    df = pd.DataFrame(
        [
            [b"alpha", 1, ("x", 1)],
            [b"beta", 2, Path("nested/file.txt")],
        ],
        columns=["dup", "dup", "mixed"],
        dtype=object,
    )

    normalized = normalize_dataframe_for_parquet(df)
    nested_path = str(Path("nested/file.txt"))

    assert list(normalized.columns) == ["dup", "dup", "mixed"]
    assert normalized.iloc[:, 0].tolist() == ["alpha", "beta"]
    assert normalized.iloc[:, 1].tolist() == [1.0, 2.0]
    assert normalized.iloc[:, 2].tolist() == ["('x', 1)", nested_path]


def test_intermediate_store_save_retries_with_shared_normalizer(monkeypatch, project_temp_dir) -> None:
    from ms_preprocessing.utils.intermediate_store import IntermediateStore

    df = pd.DataFrame(
        {
            "bytes_col": [b"alpha", b"beta"],
            "mixed_col": [1, Path("nested/file.txt")],
        },
        dtype=object,
    )

    original_to_parquet = pd.DataFrame.to_parquet
    call_count = {"count": 0}

    def flaky_to_parquet(self, *args, **kwargs):
        call_count["count"] += 1
        if call_count["count"] == 1:
            raise TypeError("force normalization path")
        return original_to_parquet(self, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "to_parquet", flaky_to_parquet)

    with project_temp_dir() as temp_dir:
        parquet_path = Path(temp_dir) / "normalized.parquet"
        IntermediateStore.save(
            df=df,
            parquet_path=parquet_path,
            metadata={"red_font_rows": {1}},
            index=False,
        )

        loaded_df, loaded_meta = IntermediateStore.load(parquet_path)

    assert call_count["count"] == 2
    assert loaded_df["bytes_col"].tolist() == ["alpha", "beta"]
    assert loaded_df["mixed_col"].tolist() == ["1", str(Path("nested/file.txt"))]
    assert loaded_meta["red_font_rows"] == [1]
