"""Final workflow export service."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ms_preprocessing.utils.file_handler import FileHandler
from ms_preprocessing.workflow.pipeline_session import PipelineSession


_STEP_INDEX = {
    "organize": 0,
    "istd": 1,
    "duplicate-removal": 2,
    "filter": 3,
    "all": 3,
}


class ExportService:
    """Materialize the final workflow dataframe to an Excel workbook."""

    def __init__(self, file_handler: FileHandler | None = None) -> None:
        self._file_handler = file_handler or FileHandler()

    def export_final(
        self,
        data: pd.DataFrame,
        *,
        output_path: Path | None,
        input_path: Path,
        step: str,
        session: PipelineSession,
        export_deleted_feature: bool,
    ) -> Path:
        session.set_source_file(input_path)
        target = self._resolve_output_path(output_path, step, session)
        extra_sheets = self._build_extra_sheets(session, export_deleted_feature)

        return self._file_handler.save_data(
            data,
            target,
            sheet_name="RawIntensity",
            red_font_rows=session.metadata.red_font_rows,
            blue_font_cells=session.metadata.blue_font_cells,
            highlight_rows=session.metadata.highlight_rows,
            extra_sheets=extra_sheets or None,
            save_parquet_cache=False,
        )

    @staticmethod
    def _resolve_output_path(
        output_path: Path | None,
        step: str,
        session: PipelineSession,
    ) -> Path:
        if output_path is not None:
            path = Path(output_path)
            if path.suffix.lower() in {".xlsx", ".parquet"}:
                return path
            return path.with_suffix(".xlsx")

        last_completed_step = _STEP_INDEX.get(step, 0)
        return session.build_final_export_path(
            last_completed_step=last_completed_step,
            last_run_all=step == "all",
            suffix=".xlsx",
        )

    @staticmethod
    def _build_extra_sheets(
        session: PipelineSession,
        export_deleted_feature: bool,
    ) -> dict[str, pd.DataFrame]:
        extra_sheets: dict[str, pd.DataFrame] = dict(getattr(session, "preserved_sheets", {}) or {})
        if session.metadata.sample_info is not None:
            extra_sheets["SampleInfo"] = session.metadata.sample_info
        deleted_feature = session.metadata.deleted_feature_df
        if export_deleted_feature and deleted_feature is not None and not deleted_feature.empty:
            extra_sheets["deleted_feature"] = deleted_feature
        return extra_sheets
