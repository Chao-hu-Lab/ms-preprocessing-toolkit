"""Parquet cache metadata and fallback helpers."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from ms_preprocessing.utils.intermediate_store import IntermediateStore

logger = logging.getLogger(__name__)


class ParquetCacheStore:
    """Manage parquet cache paths and formatting metadata sidecars."""

    @staticmethod
    def meta_path(parquet_path: Path) -> Path:
        return parquet_path.with_suffix(parquet_path.suffix + ".meta.json")

    def save_cache(
        self,
        df: pd.DataFrame,
        parquet_path: Path,
        *,
        highlight_rows: set | None = None,
        blue_font_cells: list | None = None,
        red_font_rows: set | None = None,
    ) -> None:
        meta = self.formatting_meta(
            highlight_rows=highlight_rows,
            blue_font_cells=blue_font_cells,
            red_font_rows=red_font_rows,
        )

        try:
            IntermediateStore.save(
                df=df,
                parquet_path=parquet_path,
                metadata=meta,
                index=False,
            )
        except Exception as exc:
            logger.warning("Parquet cache save failed (non-fatal): %s", exc)

    def load_meta(self, parquet_path: Path) -> dict | None:
        meta_path = self.meta_path(parquet_path)
        if not meta_path.exists():
            return None
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            return {
                "red_font_rows": data.get("red_font_rows", []),
                "blue_font_cells": data.get("blue_font_cells", []),
                "highlight_rows": data.get("highlight_rows", []),
            }
        except Exception as exc:
            logger.warning("Failed to load parquet meta: %s", exc)
            return None

    def resolve_cache(self, excel_path: Path) -> Path | None:
        parquet_path = excel_path.with_suffix(".parquet")
        meta_path = self.meta_path(parquet_path)
        if not parquet_path.exists() or not meta_path.exists():
            return None
        try:
            if parquet_path.stat().st_mtime >= excel_path.stat().st_mtime:
                return parquet_path
        except Exception as exc:
            logger.debug("Parquet cache resolution failed: %s", exc)
            return None
        return None

    @staticmethod
    def formatting_meta(
        *,
        highlight_rows: set | None = None,
        blue_font_cells: list | None = None,
        red_font_rows: set | None = None,
    ) -> dict:
        return {
            "red_font_rows": sorted(red_font_rows) if red_font_rows else [],
            "blue_font_cells": blue_font_cells or [],
            "highlight_rows": sorted(highlight_rows) if highlight_rows else [],
        }
