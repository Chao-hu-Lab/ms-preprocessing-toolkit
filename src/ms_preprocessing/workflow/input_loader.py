"""Workflow input loading and workbook context preservation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from ms_preprocessing.utils.file_handler import FileHandler
from ms_preprocessing.workflow.pipeline_session import PipelineSession


@dataclass(frozen=True)
class LoadedWorkflowInput:
    """Loaded dataframe plus metadata required by workflow services."""

    data: pd.DataFrame
    metadata: dict[str, Any]
    preserved_sheets: dict[str, pd.DataFrame] = field(default_factory=dict)


class InputLoader:
    """Load workflow input files and update pipeline session context."""

    def __init__(self, file_handler: FileHandler | None = None) -> None:
        self._file_handler = file_handler or FileHandler()

    def load(self, input_path: str | Path, *, session: PipelineSession) -> LoadedWorkflowInput:
        path = Path(input_path)
        data, metadata = self._file_handler.load_data(path)

        session.set_source_file(path)
        session.update_context_from_metadata(
            {
                "red_font_rows": metadata.get("red_font_rows", []),
                "protected_rows": metadata.get("protected_rows")
                or metadata.get("red_font_rows")
                or [],
                "blue_font_cells": metadata.get("blue_font_cells", []),
                "highlight_rows": metadata.get("highlight_rows", []),
            }
        )

        preserved_sheets = self._load_auxiliary_sheets(path, metadata)
        self._attach_auxiliary_context(session, preserved_sheets)
        return LoadedWorkflowInput(data=data, metadata=metadata, preserved_sheets=preserved_sheets)

    @staticmethod
    def _load_auxiliary_sheets(path: Path, metadata: dict[str, Any]) -> dict[str, pd.DataFrame]:
        if path.suffix.lower() not in {".xlsx", ".xls"}:
            return {}

        try:
            with pd.ExcelFile(path, engine="openpyxl") as workbook:
                raw_sheet = InputLoader._resolve_raw_sheet(workbook.sheet_names, metadata)
                return {
                    sheet: pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
                    for sheet in workbook.sheet_names
                    if sheet != raw_sheet
                }
        except (OSError, ValueError, ImportError):
            return {}

    @staticmethod
    def _resolve_raw_sheet(sheet_names: list[str], metadata: dict[str, Any]) -> str | None:
        if "RawIntensity" in sheet_names:
            return "RawIntensity"

        sheet_ref = metadata.get("sheet_name")
        if isinstance(sheet_ref, str) and sheet_ref in sheet_names:
            return sheet_ref
        if isinstance(sheet_ref, int) and 0 <= sheet_ref < len(sheet_names):
            return sheet_names[sheet_ref]
        return sheet_names[0] if sheet_names else None

    @staticmethod
    def _attach_auxiliary_context(
        session: PipelineSession,
        preserved_sheets: dict[str, pd.DataFrame],
    ) -> None:
        remaining = dict(preserved_sheets)
        sample_info = remaining.pop("SampleInfo", None)
        deleted_feature = remaining.pop("deleted_feature", None)

        metadata: dict[str, Any] = {}
        if sample_info is not None:
            metadata["sample_info"] = sample_info
        if deleted_feature is not None:
            metadata["deleted_feature_df"] = deleted_feature
        if metadata:
            session.update_context_from_metadata(metadata)

        session.preserved_sheets = remaining
