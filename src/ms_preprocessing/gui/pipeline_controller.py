"""GUI pipeline controller facade."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from ms_preprocessing.gui.async_task_runner import AsyncTaskRunner
from ms_preprocessing.gui.combined_tsv_controller import CombinedTsvController
from ms_preprocessing.gui.final_export_controller import FinalExportController
from ms_preprocessing.gui.run_all_controller import RunAllController
from ms_preprocessing.gui.step_output_autosave_service import StepOutputAutosaveService
from ms_preprocessing.workflow.workflow_runner import WorkflowRunner

if TYPE_CHECKING:
    from ms_preprocessing.workflow.combined_tsv_service import CombinedTsvService
    from ms_preprocessing.workflow.export_service import ExportService


class PipelineController:
    """Stable facade for GUI event handlers."""

    def __init__(
        self,
        host: Any,
        *,
        export_service: ExportService | None = None,
        combined_tsv_service: CombinedTsvService | None = None,
        async_runner: AsyncTaskRunner | None = None,
    ) -> None:
        self._host = host
        file_handler = host.__dict__.get("_file_handler")
        if export_service is None:
            from ms_preprocessing.workflow.export_service import ExportService

            export_service = ExportService(file_handler=file_handler)
        if combined_tsv_service is None:
            from ms_preprocessing.workflow.combined_tsv_service import CombinedTsvService

            combined_tsv_service = CombinedTsvService(file_handler=file_handler)

        shared_async_runner = async_runner or AsyncTaskRunner(host)
        self._run_all = RunAllController(
            host,
            async_runner=shared_async_runner,
            workflow_runner_cls=WorkflowRunner,
        )
        self._final_export = FinalExportController(host, export_service=export_service)
        self._autosave = StepOutputAutosaveService(host, async_runner=shared_async_runner)
        self._combined_tsv = CombinedTsvController(
            host,
            combined_tsv_service=combined_tsv_service,
        )

    def reset_pipeline_for_run_all(self) -> None:
        self._run_all.reset_pipeline_for_run_all()

    def run_all_steps(self) -> None:
        self._run_all.run_all_steps()

    def run_all_steps_worker(
        self,
        original_step: int,
        data: pd.DataFrame,
        params_by_step: list[dict[str, Any]],
    ) -> None:
        self._run_all.run_all_steps_worker(original_step, data, params_by_step)

    def finish_run_all_steps(self, original_step: int, success: bool) -> None:
        self._run_all.finish_run_all_steps(original_step, success)

    def export_results(self) -> Path | None:
        return self._final_export.export_results()

    def materialize_final_xlsx_from_latest_step(self) -> Path | None:
        return self._final_export.materialize_final_xlsx_from_latest_step()

    def schedule_step_output_save(
        self,
        step_index: int,
        data: pd.DataFrame | None,
        *,
        next_step_index: int | None = None,
    ) -> None:
        self._autosave.schedule_step_output_save(
            step_index,
            data,
            next_step_index=next_step_index,
        )

    def run_combined_tsv_preprocessor(self) -> None:
        self._combined_tsv.run_combined_tsv_preprocessor()
