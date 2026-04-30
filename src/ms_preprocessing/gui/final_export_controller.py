"""Final export and materialization orchestration for the GUI pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ms_preprocessing.utils.results import ProcessingMetadata


class FinalExportController:
    """Coordinate GUI final export behavior through ExportService."""

    def __init__(self, host: Any, *, export_service: Any) -> None:
        self._host = host
        self._export_service = export_service

    def export_results(self) -> Path | None:
        host = self._host
        if host._has_active_processing():
            host._log("Busy: wait for processing to finish before exporting results.")
            return None

        if host._current_data is None:
            materialized = self.materialize_final_xlsx_from_latest_step()
            if materialized is None:
                host._log("Error: No data to export")
            return materialized

        try:
            filepath = self._export_service.export_final(
                host._current_data,
                output_path=self._final_export_path(),
                input_path=host._source_file,
                step="all" if host._last_run_all else self._last_step_name(),
                session=self._export_session_view(),
                export_deleted_feature=self._export_deleted_feature(),
            )
            host._last_materialized_export_path = filepath
            host._log(f"Exported to: {filepath}")
            self._log_downstream_handoff_reminder()
            self._update_run_context_summary()
            return filepath
        except Exception as exc:
            host._log(f"Export error: {exc}")
            return None

    def materialize_final_xlsx_from_latest_step(self) -> Path | None:
        host = self._host
        if host._last_completed_step is None:
            return None
        source_path = host._step_output_paths.get(host._last_completed_step)
        if source_path is None:
            return None

        source_path = Path(source_path)
        if source_path.suffix.lower() == ".xlsx":
            host._last_materialized_export_path = source_path
            host._log(f"Final xlsx available: {source_path}")
            self._log_downstream_handoff_reminder()
            return source_path

        target_path = self._final_export_path()
        try:
            data, metadata = host._file_handler.load_data(source_path)
            host._pipeline_session.update_context_from_metadata(metadata)
            host._context = host._pipeline_session.context
            host._current_data = data

            filepath = self._export_service.export_final(
                data,
                output_path=target_path,
                input_path=host._source_file,
                step="all" if host._last_run_all else self._last_step_name(),
                session=self._export_session_view(),
                export_deleted_feature=self._export_deleted_feature(),
            )
            host._step_output_paths[host._last_completed_step] = filepath
            host._last_materialized_export_path = filepath
            host._log(f"Materialized final xlsx from parquet: {filepath}")
            self._log_downstream_handoff_reminder()
            self._update_run_context_summary()
            return filepath
        except Exception as exc:
            host._log(f"Materialization error: {exc}")
            return None

    def _final_export_path(self) -> Path:
        host = self._host
        host._pipeline_session.set_source_file(host._source_file)
        return host._pipeline_session.build_final_export_path(
            last_completed_step=host._last_completed_step,
            last_run_all=host._last_run_all,
            suffix=".xlsx",
        )

    def _last_step_name(self) -> str:
        last_completed = self._host._last_completed_step
        mapping = {
            0: "organize",
            1: "istd",
            2: "duplicate-removal",
            3: "filter",
        }
        return mapping.get(last_completed, "filter")

    def _export_session_view(self) -> Any:
        session = self._host._pipeline_session
        metadata = getattr(session, "metadata", None)
        if not isinstance(metadata, ProcessingMetadata):
            metadata = ProcessingMetadata()
        return _ExportSessionView(session=session, metadata=metadata)

    def _export_deleted_feature(self) -> bool:
        step_widgets = self._host.__dict__.get("step_widgets", [])
        if len(step_widgets) < 4:
            return False
        export_var = getattr(step_widgets[3], "_export_deleted_var", None)
        getter = getattr(export_var, "get", None)
        if not callable(getter):
            return False
        try:
            return bool(getter())
        except Exception:
            return False

    def _log_downstream_handoff_reminder(self) -> None:
        reminder = getattr(self._host, "_log_downstream_handoff_reminder", None)
        if callable(reminder):
            reminder()

    def _update_run_context_summary(self) -> None:
        updater = getattr(self._host, "_update_run_context_summary", None)
        if callable(updater):
            updater()


class _ExportSessionView:
    """Adapter exposing typed export metadata while delegating path behavior."""

    def __init__(self, *, session: Any, metadata: ProcessingMetadata) -> None:
        self._session = session
        self.metadata = metadata
        preserved = session.__dict__.get("preserved_sheets") if hasattr(session, "__dict__") else None
        self.preserved_sheets = preserved if isinstance(preserved, dict) else {}

    def set_source_file(self, source_file: Path | None) -> None:
        self._session.set_source_file(source_file)

    def build_final_export_path(
        self,
        last_completed_step: int | None,
        last_run_all: bool,
        suffix: str = ".xlsx",
    ) -> Path:
        return self._session.build_final_export_path(
            last_completed_step=last_completed_step,
            last_run_all=last_run_all,
            suffix=suffix,
        )
