"""Local parquet intermediate storage contract for ms-preprocessing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ms_preprocessing.utils.parquet_compat import write_parquet_with_normalized_fallback


class IntermediateStore:
    """Persist dataframe + metadata sidecar for step-to-step handoff."""

    @staticmethod
    def _meta_path(parquet_path: Path) -> Path:
        return parquet_path.with_suffix(parquet_path.suffix + ".meta.json")

    @staticmethod
    def save(
        df: pd.DataFrame,
        parquet_path: str | Path,
        metadata: dict[str, Any] | None = None,
        index: bool = False,
    ) -> Path:
        path = Path(parquet_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_parquet_with_normalized_fallback(df, path, index=index)

        payload = IntermediateStore._normalize_metadata(metadata or {})
        IntermediateStore._meta_path(path).write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def load(parquet_path: str | Path) -> tuple[pd.DataFrame, dict[str, Any]]:
        path = Path(parquet_path)
        df = pd.read_parquet(path)
        meta_path = IntermediateStore._meta_path(path)
        if not meta_path.exists():
            return df, {}

        raw = json.loads(meta_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return df, {}
        return df, raw

    @staticmethod
    def _normalize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        return {
            str(key): IntermediateStore._normalize_value(value)
            for key, value in metadata.items()
        }

    @staticmethod
    def _normalize_value(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(key): IntermediateStore._normalize_value(item)
                for key, item in value.items()
            }
        if isinstance(value, set):
            return [IntermediateStore._normalize_value(item) for item in sorted(value)]
        if isinstance(value, (list, tuple)):
            return [IntermediateStore._normalize_value(item) for item in value]
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, (np.integer, np.floating)):
            return value.item()
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value
