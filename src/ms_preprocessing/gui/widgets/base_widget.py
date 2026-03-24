"""
Base widget class for processing step widgets.
"""

from abc import ABC, abstractmethod
import queue
import threading
from typing import Optional, Callable, Any
import customtkinter as ctk
import pandas as pd

from ms_preprocessing.gui.styles import COLORS, FONTS, PADDING, DIMENSIONS
from ms_preprocessing.utils.perf import take_snapshot, format_perf_delta
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
        on_load_file: Optional[Callable[[int], None]] = None,
        on_complete: Optional[Callable[[pd.DataFrame], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[float, str], None]] = None,
    ):
        """
        Initialize the base widget.

        Args:
            parent: Parent widget
            title: Title of this processing step
            description: Description of what this step does
            step_index: Zero-based index of this step in the pipeline
            on_load_file: Callback when user requests file load
            on_complete: Callback when processing completes
            on_log: Callback for logging messages
            on_progress: Callback for progress updates (value, status)
        """
        super().__init__(parent)

        self.title = title
        self.description = description
        self.step_index = step_index
        self._on_load_file = on_load_file
        self.on_complete = on_complete
        self.on_log = on_log
        self._on_progress = on_progress
        self._data: Optional[pd.DataFrame] = None
        self._result: Optional[pd.DataFrame] = None
        self._processing_result: Optional[ProcessingResult] = None
        self._context: dict = {}
        self._last_metadata: dict = {}
        self._last_parameters: dict = {}
        self.run_button = None
        self.reset_button = None
        self.input_entry: Optional[ctk.CTkEntry] = None
        self._ui_thread_id = threading.get_ident()
        self._ui_queue: queue.SimpleQueue[tuple[Callable[..., None], tuple[Any, ...]]] = queue.SimpleQueue()
        self._ui_queue_after_id: str | None = None
        self._worker_thread: threading.Thread | None = None
        self._is_processing = False

        self._create_layout()

    def _create_layout(self) -> None:
        """Create single-column widget layout (no right panel)."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # params area — fixed, no vertical expansion

        self._content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._content_frame.grid(row=0, column=0, sticky="new", padx=60)
        self._content_frame.grid_columnconfigure(0, weight=1)

        self._build_content_panel()

    def _build_content_panel(self) -> None:
        """Build single-column content panel: title, subtitle desc, input, params."""
        # Step title
        self.title_label = ctk.CTkLabel(
            self._content_frame,
            text=self.title,
            font=FONTS["heading"],
            anchor="w",
        )
        self.title_label.pack(
            fill="x",
            padx=PADDING["large"],
            pady=(PADDING["large"], 2),
        )

        # Description as subtitle (hidden if empty)
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

        # Separator
        ctk.CTkFrame(self._content_frame, height=1, fg_color="#2a3f5a").pack(
            fill="x", padx=PADDING["large"], pady=(0, PADDING["medium"])
        )

        # Input file row
        input_frame = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        input_frame.pack(fill="x", padx=PADDING["large"], pady=(0, PADDING["medium"]))
        input_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(input_frame, text="輸入檔案", font=FONTS["body"]).grid(
            row=0, column=0, padx=(0, PADDING["small"]), sticky="e"
        )

        self.input_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="選擇輸入檔案",
            font=FONTS["body"],
        )
        self.input_entry.grid(row=0, column=1, sticky="ew", padx=(0, PADDING["small"]))

        ctk.CTkButton(
            input_frame,
            text="選擇",
            command=self._on_load_clicked,
            width=60,
            height=32,
            font=FONTS["body"],
        ).grid(row=0, column=2)

        # Params section label
        ctk.CTkLabel(
            self._content_frame,
            text="參數設定",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(fill="x", padx=PADDING["large"], pady=(0, PADDING["small"]))

        # Params outer container — max width 800px, centered
        self._params_outer = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        self._params_outer.pack(fill="x", padx=PADDING["large"])

        # Params frame (subclasses fill this via _create_parameters)
        self.params_frame = ctk.CTkFrame(self._params_outer)
        self.params_frame.pack(anchor="center", fill="x")

        # Bind max width 800px
        def _clamp_width(event):
            w = min(event.width, 800)
            self.params_frame.configure(width=w)
        self._params_outer.bind("<Configure>", _clamp_width)

        self._create_parameters()

    def show_stats(self, stats: dict) -> None:
        """No-op: stats panel removed from base widget."""
        pass

    @abstractmethod
    def _create_parameters(self) -> None:
        """Create parameter input widgets. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def get_parameters(self) -> dict:
        """Get current parameter values. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def run_processing(self, data: pd.DataFrame, **params) -> pd.DataFrame:
        """Run the processing step. Must be implemented by subclasses."""
        pass

    def set_data(self, data: pd.DataFrame) -> None:
        """Set the input data for processing."""
        self._data = data
        self.log(f"Loaded data with {len(data)} rows and {len(data.columns)} columns")

    def set_input_file(self, path: Optional[str]) -> None:
        """Update input file display."""
        if not self.input_entry:
            return
        self.input_entry.delete(0, "end")
        if path:
            self.input_entry.insert(0, path)

    def set_context(self, context: Optional[dict]) -> None:
        """Set shared processing context (e.g., protected rows)."""
        self._context = context or {}

    def get_metadata(self) -> dict:
        """Get metadata from the last processing run."""
        return self._last_metadata or {}

    def get_result(self) -> Optional[pd.DataFrame]:
        """Get the processing result."""
        return self._result

    def get_processing_result(self) -> Optional[ProcessingResult]:
        """Get the typed processing result from the latest run."""
        return self._processing_result

    def get_last_parameters(self) -> dict:
        """Get parameters used by the latest run."""
        return dict(self._last_parameters)

    def apply_parameters(self, params: dict) -> None:
        """Apply a parameter bundle to the widget controls."""
        _ = params

    def is_processing(self) -> bool:
        """Return True while a background processing worker is active."""
        return self._is_processing

    def log(self, message: str) -> None:
        """Log a message."""
        self._dispatch_to_ui(self._emit_log, message)

    def update_progress(self, value: float, status: str = "") -> None:
        """Delegate progress update to injected callback (Action Bar)."""
        self._dispatch_to_ui(self._emit_progress, float(value), status)

    def _emit_log(self, message: str) -> None:
        if self.on_log:
            self.on_log(f"[{self.title}] {message}")

    def _emit_progress(self, value: float, status: str = "") -> None:
        if self._on_progress:
            self._on_progress(value, status)
        self.update_idletasks()

    def _dispatch_to_ui(self, callback: Callable[..., None], *args: Any) -> None:
        if threading.get_ident() == self._ui_thread_id:
            callback(*args)
            return
        self._ui_queue.put((callback, args))

    # Poll a simple queue from the UI thread so worker threads never call Tk directly.
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
        result: Optional[pd.DataFrame],
        error_message: str | None,
        perf_summary: str,
    ) -> None:
        try:
            if error_message is None and result is not None:
                self._result = result
                self.update_progress(100, "Complete!")
                self.log("Processing completed successfully")

                if self.on_complete:
                    try:
                        self.on_complete(self._result, self._last_metadata)
                    except TypeError:
                        self.on_complete(self._result)
            else:
                message = error_message or "Processing failed"
                self.update_progress(0, f"Error: {message}")
                self.log(f"Error: {message}")
        finally:
            self.log(f"Performance: {perf_summary}")
            self._worker_thread = None
            self._set_processing_state(False)

    def _on_load_clicked(self) -> None:
        """Handle input file selection."""
        if self._on_load_file:
            self._on_load_file(self.step_index)

    def _on_run_clicked(self) -> None:
        """Handle run button click."""
        if self._data is None:
            self.log("Error: No data loaded")
            self.update_progress(0, "Error: No data loaded")
            return

        if self._is_processing:
            self.log("Run request ignored because processing is already in progress")
            return

        perf_start = take_snapshot()
        self._set_processing_state(True)
        self.update_progress(0, "Processing...")

        params = self.get_parameters()
        self._last_parameters = dict(params)
        self.log(f"Starting with parameters: {params}")

        self._last_metadata = {}
        self._processing_result = None
        self._result = None

        self._schedule_ui_queue_drain()
        self._worker_thread = threading.Thread(
            target=self._run_processing_worker,
            args=(self._data, params, perf_start),
            daemon=True,
            name=f"step-{self.step_index + 1}-worker",
        )
        self._worker_thread.start()

    def _on_reset_clicked(self) -> None:
        """Handle reset button click."""
        if self._is_processing:
            self.log("Reset request ignored because processing is still in progress")
            return
        self._result = None
        self._processing_result = None
        self._last_metadata = {}
        self.update_progress(0, "Ready")
        self.log("Reset")
