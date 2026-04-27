"""
Base widget class for processing step widgets.
"""

from __future__ import annotations

import queue
import threading
from abc import ABC, abstractmethod
from typing import Any, Callable

import customtkinter as ctk
import pandas as pd

from ms_preprocessing.gui.styles import COLORS, DIMENSIONS, FONTS, PADDING
from ms_preprocessing.gui.validation import (
    ValidationWarning,
    format_validation_warnings,
    has_blocking_warnings,
)
from ms_preprocessing.utils.perf import format_perf_delta, take_snapshot
from ms_preprocessing.utils.results import ProcessingResult


class BaseProcessingWidget(ctk.CTkFrame, ABC):
    """
    Abstract base class for processing step widgets.

    Each processing step in the pipeline has a corresponding widget
    that provides the UI for configuring and running that step.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        title: str,
        description: str,
        step_index: int,
        on_load_file: Callable[[int], None] | None = None,
        on_complete: Callable[[pd.DataFrame], None] | None = None,
        on_log: Callable[[str], None] | None = None,
        on_progress: Callable[[float, str], None] | None = None,
        scrollable_content: bool = False,
    ):
        super().__init__(parent)

        self.title = title
        self.description = description
        self.step_index = step_index
        self._on_load_file = on_load_file
        self.on_complete = on_complete
        self.on_log = on_log
        self._on_progress = on_progress
        self._data: pd.DataFrame | None = None
        self._result: pd.DataFrame | None = None
        self._processing_result: ProcessingResult | None = None
        self._context: dict = {}
        self._last_metadata: dict = {}
        self._last_parameters: dict = {}
        self.run_button = None
        self.reset_button = None
        self.input_entry: ctk.CTkEntry | None = None
        self._ui_thread_id = threading.get_ident()
        self._ui_queue: queue.SimpleQueue[tuple[Callable[..., None], tuple[Any, ...]]] = queue.SimpleQueue()
        self._ui_queue_after_id: str | None = None
        self._worker_thread: threading.Thread | None = None
        self._is_processing = False
        self._scrollable_content = scrollable_content

        self._create_layout()

    def _create_layout(self) -> None:
        """Create single-column widget layout."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        if self._scrollable_content:
            self._content_frame = ctk.CTkScrollableFrame(
                self,
                fg_color="transparent",
                corner_radius=0,
            )
        else:
            self._content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._content_frame.grid(row=0, column=0, sticky="nsew", padx=60)
        self._content_frame.grid_columnconfigure(0, weight=1)

        self._build_content_panel()

    def _build_content_panel(self) -> None:
        """Build the content panel: title, description, input row, and params."""
        self.title_label = ctk.CTkLabel(
            self._content_frame,
            text=self.title,
            font=FONTS["heading"],
            anchor="w",
        )
        self.title_label.pack(
            fill="x",
            padx=PADDING["large"],
            pady=(0, 2),
        )

        if self.description:
            self.desc_label = ctk.CTkLabel(
                self._content_frame,
                text=self.description,
                font=FONTS["small"],
                text_color=COLORS["text_secondary"],
                anchor="w",
                wraplength=700,
                justify="left",
            )
            self.desc_label.pack(
                fill="x",
                padx=PADDING["large"],
                pady=(0, PADDING["small"]),
            )

        ctk.CTkFrame(self._content_frame, height=1, fg_color="#2a3f5a").pack(
            fill="x",
            padx=PADDING["large"],
            pady=(0, PADDING["medium"]),
        )

        input_frame = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        input_frame.pack(fill="x", padx=PADDING["large"], pady=(0, PADDING["medium"]))
        input_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(input_frame, text="輸入檔案", font=FONTS["body"]).grid(
            row=0,
            column=0,
            padx=(0, PADDING["small"]),
            sticky="e",
        )

        self.input_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="選擇輸入檔案",
            font=FONTS["body"],
        )
        self.input_entry.grid(row=0, column=1, sticky="ew", padx=(0, PADDING["small"]))

        ctk.CTkButton(
            input_frame,
            text="瀏覽",
            command=self._on_load_clicked,
            width=60,
            height=32,
            font=FONTS["body"],
        ).grid(row=0, column=2)

        ctk.CTkLabel(
            self._content_frame,
            text="參數設定",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(fill="x", padx=PADDING["large"], pady=(0, PADDING["small"]))

        self._params_outer = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        self._params_outer.pack(fill="x", padx=PADDING["large"])

        self.params_frame = ctk.CTkFrame(self._params_outer)
        self.params_frame.pack(anchor="n", fill="x")

        def _clamp_width(event):
            width = min(int(event.width), 800)
            current_width = int(self.params_frame.cget("width"))
            if current_width != width:
                self.params_frame.configure(width=width)

        self._params_outer.bind("<Configure>", _clamp_width)
        self._create_parameters()

    def _configure_form_grid(self) -> None:
        """Apply a consistent label/control grid to the parameter form."""
        self.params_frame.grid_columnconfigure(0, minsize=DIMENSIONS["form_label_width"])
        self.params_frame.grid_columnconfigure(1, minsize=DIMENSIONS["form_value_width"], weight=1)
        self.params_frame.grid_columnconfigure(2, minsize=110)
        self.params_frame.grid_columnconfigure(3, weight=1)

    def _style_form_label(self, label: ctk.CTkLabel) -> None:
        """Right-align labels so control columns line up vertically."""
        label.configure(
            width=DIMENSIONS["form_label_width"],
            anchor="e",
            justify="right",
        )

    def _style_form_switch(self, switch: ctk.CTkSwitch) -> None:
        """Give switch labels the same alignment column as regular labels."""
        switch.configure(width=DIMENSIONS["form_switch_width"])

    def _style_numeric_entry(self, entry: ctk.CTkEntry) -> None:
        """Keep numeric controls visually consistent across all steps."""
        entry.configure(
            width=DIMENSIONS["numeric_input_width"],
            justify="center",
        )

    def show_stats(self, stats: dict) -> None:
        """No-op: stats panel removed from base widget."""
        _ = stats

    @abstractmethod
    def _create_parameters(self) -> None:
        pass

    @abstractmethod
    def get_parameters(self) -> dict:
        pass

    @abstractmethod
    def run_processing(self, data: pd.DataFrame, **params) -> pd.DataFrame:
        pass

    def set_data(self, data: pd.DataFrame) -> None:
        self._data = data
        self.log(f"Loaded data with {len(data)} rows and {len(data.columns)} columns")

    def set_input_file(self, path: str | None) -> None:
        if not self.input_entry:
            return
        self.input_entry.delete(0, "end")
        if path:
            self.input_entry.insert(0, path)

    def set_context(self, context: dict | None) -> None:
        self._context = context or {}

    def get_metadata(self) -> dict:
        return self._last_metadata or {}

    def get_result(self) -> pd.DataFrame | None:
        return self._result

    def get_processing_result(self) -> ProcessingResult | None:
        return self._processing_result

    def get_last_parameters(self) -> dict:
        return dict(self._last_parameters)

    def apply_parameters(self, params: dict) -> None:
        _ = params

    def validate_parameters(self, params: dict) -> list[ValidationWarning]:
        _ = params
        return []

    def is_processing(self) -> bool:
        return self._is_processing

    def log(self, message: str) -> None:
        self._dispatch_to_ui(self._emit_log, message)

    def update_progress(self, value: float, status: str = "") -> None:
        self._dispatch_to_ui(self._emit_progress, float(value), status)

    def _emit_log(self, message: str) -> None:
        if self.on_log:
            self.on_log(f"[{self.title}] {message}")

    def _emit_progress(self, value: float, status: str = "") -> None:
        if self._on_progress:
            self._on_progress(value, status)

    def _dispatch_to_ui(self, callback: Callable[..., None], *args: Any) -> None:
        if threading.get_ident() == self._ui_thread_id:
            callback(*args)
            return
        self._ui_queue.put((callback, args))

    def _schedule_ui_queue_drain(self) -> None:
        if self._ui_queue_after_id is not None or not self.winfo_exists():
            return
        self._ui_queue_after_id = self.after(16, self._drain_ui_queue)

    def _drain_ui_queue(self) -> None:
        self._ui_queue_after_id = None
        if not self.winfo_exists():
            return

        while True:
            try:
                callback, args = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            callback(*args)

        worker_alive = self._worker_thread is not None and self._worker_thread.is_alive()
        if worker_alive or not self._ui_queue.empty():
            self._schedule_ui_queue_drain()

    def _iter_shared_action_buttons(self) -> list[Any]:
        controls = []
        if self.run_button is not None:
            controls.append(self.run_button)
        if self.reset_button is not None:
            controls.append(self.reset_button)

        toplevel = self.winfo_toplevel()
        for attr_name in (
            "run_step_btn",
            "reset_step_btn",
            "export_results_btn",
            "open_output_folder_btn",
            "run_all_btn",
        ):
            control = getattr(toplevel, attr_name, None)
            if control is not None and control not in controls:
                controls.append(control)

        for button in getattr(toplevel, "step_buttons", []):
            if button not in controls:
                controls.append(button)

        return controls

    def _set_processing_state(self, processing: bool) -> None:
        self._is_processing = processing
        state = "disabled" if processing else "normal"
        for control in self._iter_shared_action_buttons():
            try:
                control.configure(state=state)
            except Exception:
                continue

    def _run_processing_worker(self, data: pd.DataFrame, params: dict, perf_start: object) -> None:
        error_message: str | None = None
        result: pd.DataFrame | None = None

        try:
            result = self.run_processing(data, **params)
        except Exception as exc:
            error_message = str(exc)

        perf_end = take_snapshot()
        self._ui_queue.put(
            (
                self._finish_processing,
                (result, error_message, format_perf_delta(perf_start, perf_end)),
            )
        )

    def _finish_processing(
        self,
        result: pd.DataFrame | None,
        error_message: str | None,
        perf_summary: str,
    ) -> None:
        restore_controls = False
        try:
            if error_message is None and result is not None:
                self._result = result
                self.update_progress(100, "Complete!")
                self.log("Processing completed successfully")
                self.log(perf_summary)
                self._is_processing = False
                restore_controls = True
                if self.on_complete:
                    self.on_complete(result, self.get_metadata())
            else:
                self.update_progress(0, "Failed")
                self.log(f"Error: {error_message or 'Unknown error'}")
                restore_controls = True
        finally:
            if restore_controls or self._is_processing:
                self._set_processing_state(False)
            self._worker_thread = None
            if not self._ui_queue.empty():
                self._schedule_ui_queue_drain()

    def _on_load_clicked(self) -> None:
        if self._on_load_file:
            self._on_load_file(self.step_index)

    def _on_run_clicked(self) -> None:
        if self._is_processing:
            self.log("Processing is already in progress")
            return
        if self._data is None:
            self.log("No input data loaded")
            return

        params = self.get_parameters()
        self._last_parameters = dict(params)
        if not self._validate_parameters_before_run(params):
            return
        self._start_processing(params)

    def _validate_parameters_before_run(self, params: dict) -> bool:
        warnings = self.validate_parameters(params)
        if not warnings:
            return True

        message = format_validation_warnings(warnings)
        self.log(message)
        if has_blocking_warnings(warnings):
            return False
        return self._confirm_validation_warnings(warnings)

    def _confirm_validation_warnings(self, warnings: list[ValidationWarning]) -> bool:
        import tkinter.messagebox

        return bool(
            tkinter.messagebox.askokcancel(
                "Parameter warning",
                format_validation_warnings(warnings),
                parent=self,
            )
        )

    def _start_processing(self, params: dict) -> None:
        self._set_processing_state(True)
        self.update_progress(0, "Running...")

        perf_start = take_snapshot()
        self._worker_thread = threading.Thread(
            target=self._run_processing_worker,
            args=(self._data.copy(), params, perf_start),
            daemon=True,
        )
        self._worker_thread.start()
        self._schedule_ui_queue_drain()

    def _on_reset_clicked(self) -> None:
        self._result = None
        self._processing_result = None
        self._last_metadata = {}
        self._last_parameters = {}
        self.update_progress(0, "Ready")
        self.log("Step reset")
