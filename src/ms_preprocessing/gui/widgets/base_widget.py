"""
Base widget class for processing step widgets.
"""

from abc import ABC, abstractmethod
from typing import Optional, Callable, Any
import customtkinter as ctk
import pandas as pd

from ms_preprocessing.gui.styles import COLORS, FONTS, PADDING
from ms_preprocessing.utils.perf import take_snapshot, format_perf_delta


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
    ):
        """
        Initialize the base widget.

        Args:
            parent: Parent widget
            title: Title of this processing step
            description: Description of what this step does
            on_complete: Callback when processing completes
            on_log: Callback for logging messages
        """
        super().__init__(parent)

        self.title = title
        self.description = description
        self.step_index = step_index
        self._on_load_file = on_load_file
        self.on_complete = on_complete
        self.on_log = on_log
        self._data: Optional[pd.DataFrame] = None
        self._result: Optional[pd.DataFrame] = None
        self._context: dict = {}
        self._last_metadata: dict = {}
        self.run_button = None
        self.reset_button = None
        self.input_entry: Optional[ctk.CTkEntry] = None

        self._create_layout()

    def _create_layout(self) -> None:
        """Create the widget layout."""
        # Title
        self.title_label = ctk.CTkLabel(
            self,
            text=self.title,
            font=FONTS["heading"],
        )
        self.title_label.pack(pady=(PADDING["small"], PADDING["small"]))

        # Description
        self.desc_label = ctk.CTkLabel(
            self,
            text=self.description,
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            wraplength=520,
        )
        self.desc_label.pack(pady=(0, PADDING["small"]))

        # Input file row
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.pack(fill="x", padx=PADDING["small"], pady=(0, PADDING["small"]))
        input_frame.grid_columnconfigure(1, weight=1)

        input_label = ctk.CTkLabel(
            input_frame,
            text="輸入檔案：",
            font=FONTS["body"],
        )
        input_label.grid(row=0, column=0, padx=PADDING["small"], pady=PADDING["small"], sticky="w")

        self.input_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="選擇輸入檔案",
            font=FONTS["body"],
        )
        self.input_entry.grid(row=0, column=1, padx=PADDING["small"], pady=PADDING["small"], sticky="ew")

        load_btn = ctk.CTkButton(
            input_frame,
            text="選擇檔案",
            command=self._on_load_clicked,
            width=90,
            font=FONTS["body"],
        )
        load_btn.grid(row=0, column=2, padx=PADDING["small"], pady=PADDING["small"])

        # Parameters frame (to be filled by subclasses)
        self.params_frame = ctk.CTkFrame(self)
        self.params_frame.pack(fill="x", padx=0, pady=PADDING["small"])

        # Create subclass-specific parameters
        self._create_parameters()

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.pack(fill="x", padx=PADDING["small"], pady=PADDING["small"])
        self.progress_bar.set(0)

        # Status label
        self.status_label = ctk.CTkLabel(
            self,
            text="Ready",
            font=FONTS["small"],
        )
        self.status_label.pack(pady=PADDING["small"])

    @abstractmethod
    def _create_parameters(self) -> None:
        """Create parameter input widgets. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def _get_parameters(self) -> dict:
        """Get current parameter values. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def _run_processing(self, data: pd.DataFrame, **params) -> pd.DataFrame:
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

    def log(self, message: str) -> None:
        """Log a message."""
        if self.on_log:
            self.on_log(f"[{self.title}] {message}")

    def update_progress(self, value: float, status: str = "") -> None:
        """Update the progress bar and status."""
        self.progress_bar.set(value / 100)
        if status:
            self.status_label.configure(text=status)
        self.update_idletasks()

    def _on_load_clicked(self) -> None:
        """Handle input file selection."""
        if self._on_load_file:
            self._on_load_file(self.step_index)

    def _on_run_clicked(self) -> None:
        """Handle run button click."""
        if self._data is None:
            self.log("Error: No data loaded")
            self.status_label.configure(text="Error: No data loaded")
            return

        perf_start = take_snapshot()

        try:
            if self.run_button is not None:
                self.run_button.configure(state="disabled")
            self.status_label.configure(text="Processing...")
            self.progress_bar.set(0)

            params = self._get_parameters()
            self.log(f"Starting with parameters: {params}")

            self._last_metadata = {}
            self._result = self._run_processing(self._data, **params)

            self.progress_bar.set(1)
            self.status_label.configure(text="Complete!")
            self.log("Processing completed successfully")

            if self.on_complete and self._result is not None:
                try:
                    self.on_complete(self._result, self._last_metadata)
                except TypeError:
                    self.on_complete(self._result)

        except Exception as e:
            self.status_label.configure(text=f"Error: {str(e)}")
            self.log(f"Error: {str(e)}")
        finally:
            perf_end = take_snapshot()
            self.log(f"Performance: {format_perf_delta(perf_start, perf_end)}")
            if self.run_button is not None:
                self.run_button.configure(state="normal")

    def _on_reset_clicked(self) -> None:
        """Handle reset button click."""
        self._result = None
        self._last_metadata = {}
        self.progress_bar.set(0)
        self.status_label.configure(text="Ready")
        self.log("Reset")
