"""Application-layer result types for the ms-preprocessing pipeline.

Note:
    ``ms_core.preprocessing.base`` also defines a ``ProcessingResult``.
    Always import these application-layer types from
    ``ms_preprocessing.utils.results`` to avoid shadowing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class ProcessingMetadata:
    """Typed replacement for the unstructured pipeline context dict."""

    red_font_rows: set[int] = field(default_factory=set)
    protected_rows: set[int] = field(default_factory=set)
    blue_font_cells: list[Any] = field(default_factory=list)
    highlight_rows: set[int] = field(default_factory=set)
    sample_info: pd.DataFrame | None = None
    deleted_feature_df: pd.DataFrame | None = None

    @classmethod
    def from_mapping(cls, metadata: dict[str, Any] | None) -> "ProcessingMetadata":
        """Build typed metadata from a legacy metadata/context mapping."""
        if not metadata:
            return cls()

        sample_info = metadata.get("sample_info")
        deleted_feature_df = metadata.get("deleted_feature_df")
        protected_rows = metadata.get("protected_rows")
        if protected_rows is None:
            protected_rows = metadata.get("red_font_rows")

        return cls(
            red_font_rows=set(metadata.get("red_font_rows") or []),
            protected_rows=set(protected_rows or []),
            blue_font_cells=list(metadata.get("blue_font_cells") or []),
            highlight_rows=set(metadata.get("highlight_rows") or []),
            sample_info=sample_info if isinstance(sample_info, pd.DataFrame) else None,
            deleted_feature_df=(
                deleted_feature_df if isinstance(deleted_feature_df, pd.DataFrame) else None
            ),
        )

    def as_context_dict(self) -> dict[str, Any]:
        """Return a backward-compatible dict for legacy GUI callers."""
        return {
            "red_font_rows": set(self.red_font_rows),
            "protected_rows": set(self.protected_rows),
            "blue_font_cells": list(self.blue_font_cells),
            "highlight_rows": set(self.highlight_rows),
            "sample_info": self.sample_info,
            "deleted_feature_df": self.deleted_feature_df,
        }

    def copy(self) -> "ProcessingMetadata":
        """Return an independent typed metadata snapshot."""
        return ProcessingMetadata(
            red_font_rows=set(self.red_font_rows),
            protected_rows=set(self.protected_rows),
            blue_font_cells=list(self.blue_font_cells),
            highlight_rows=set(self.highlight_rows),
            sample_info=(
                self.sample_info.copy(deep=True)
                if isinstance(self.sample_info, pd.DataFrame)
                else None
            ),
            deleted_feature_df=(
                self.deleted_feature_df.copy(deep=True)
                if isinstance(self.deleted_feature_df, pd.DataFrame)
                else None
            ),
        )


@dataclass
class ProcessingResult:
    """Unified result wrapper returned by application-layer adapters."""

    success: bool
    step: str
    output_path: str | None
    data: pd.DataFrame | None
    metadata: ProcessingMetadata
    error: str | None = None
    statistics: dict[str, Any] = field(default_factory=dict)
