"""Non-Excel output writers for toolkit data exports."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from ms_preprocessing.utils.intermediate_store import IntermediateStore
from ms_preprocessing.utils.parquet_cache_store import ParquetCacheStore
from ms_preprocessing.utils.parquet_compat import write_parquet_with_normalized_fallback

logger = logging.getLogger(__name__)


class OutputWriter:
    """Write delimited and parquet outputs."""

    @staticmethod
    def save_delimited(df: pd.DataFrame, path: Path, *, index: bool, sep: str) -> None:
        df.to_csv(path, sep=sep, index=index)

    @staticmethod
    def save_parquet(
        df: pd.DataFrame,
        path: Path,
        *,
        index: bool,
        highlight_rows: set | None = None,
        blue_font_cells: list | None = None,
        red_font_rows: set | None = None,
    ) -> None:
        parquet_meta = ParquetCacheStore.formatting_meta(
            highlight_rows=highlight_rows,
            blue_font_cells=blue_font_cells,
            red_font_rows=red_font_rows,
        )
        try:
            IntermediateStore.save(
                df=df,
                parquet_path=path,
                metadata=parquet_meta,
                index=index,
            )
        except Exception as exc:
            logger.warning(
                "Intermediate store save failed, falling back to raw parquet write: %s",
                exc,
            )
            write_parquet_with_normalized_fallback(df, path, index=index)
