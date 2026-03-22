"""Main window assembly for MS Preprocessing Toolkit GUI."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import customtkinter as ctk
import pandas as pd

from ms_preprocessing.config.settings import Settings
from ms_preprocessing.gui.event_handlers import MainWindowEventHandlersMixin
from ms_preprocessing.gui.layout import MainWindowLayoutMixin
from ms_preprocessing.gui.pipeline_session import PipelineSession
from ms_preprocessing.utils.file_handler import FileHandler


class MainWindow(MainWindowEventHandlersMixin, MainWindowLayoutMixin, ctk.CTk):
    """Coordinate the GUI layout, workflow session, and file interactions."""

    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title(Settings.WINDOW_TITLE)
        self.geometry(f"{Settings.WINDOW_SIZE[0]}x{Settings.WINDOW_SIZE[1]}")
        self.minsize(*Settings.WINDOW_MIN_SIZE)

        self._project_root = Path(__file__).resolve().parents[3]
        self._output_dir = self._project_root / "OUTPUT"

        self._file_handler = FileHandler()
        self._current_data: Optional[pd.DataFrame] = None
        self._original_data: Optional[pd.DataFrame] = None
        self._source_file: Optional[Path] = None
        self._current_step = 0
        self._last_completed_step: Optional[int] = None
        self._last_run_all = False
        self._completed_steps: set[int] = set()
        self._pipeline_session = PipelineSession(output_dir=self._output_dir, source_file=None)
        self._step_output_paths = self._pipeline_session.step_output_paths
        self._context = self._pipeline_session.context
        self._source_context_snapshot: dict[str, object] | None = None
        self._last_materialized_export_path: Optional[Path] = None

        self._create_layout()
        self._bind_shortcuts()


def run_app():
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    run_app()
