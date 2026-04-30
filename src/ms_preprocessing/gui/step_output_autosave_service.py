"""Deferred step-output autosave scheduling for the GUI pipeline."""

from __future__ import annotations

import threading
from typing import Any

import pandas as pd

from ms_preprocessing.gui.async_task_runner import AsyncTaskRunner


class StepOutputAutosaveService:
    """Schedule background autosave workers while preserving host callbacks."""

    def __init__(
        self,
        host: Any,
        *,
        async_runner: AsyncTaskRunner | None = None,
    ) -> None:
        self._host = host
        self._async_runner = async_runner or AsyncTaskRunner(host)

    def schedule_step_output_save(
        self,
        step_index: int,
        data: pd.DataFrame | None,
        *,
        next_step_index: int | None = None,
    ) -> None:
        host = self._host
        if data is None:
            return
        try:
            self._async_runner.ensure_state()
            session = host._pipeline_session
            session.set_source_file(getattr(host, "_source_file", None))
            output_path = session.build_step_output_path(step_index)
            metadata = session.metadata
            formatting_context = {
                "highlight_rows": set(metadata.highlight_rows),
                "blue_font_cells": list(metadata.blue_font_cells),
                "red_font_rows": set(metadata.red_font_rows),
            }
            session_token = id(session)
            data_snapshot = data.copy(deep=False)
        except Exception as exc:
            host._log(f"Auto-save error: {exc}")
            return

        worker = threading.Thread(
            target=host._run_step_output_save_worker,
            args=(
                step_index,
                data_snapshot,
                next_step_index,
                session_token,
                output_path,
                formatting_context,
            ),
            daemon=True,
            name=f"step-{step_index + 1}-autosave-worker",
        )
        host._step_output_save_threads.append(worker)
        host._schedule_ui_queue_drain()
        worker.start()
