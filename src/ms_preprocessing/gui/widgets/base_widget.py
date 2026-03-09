"""
Base widget class for processing step widgets.
"""

from abc import ABC, abstractmethod
from typing import Optional, Callable, Any
import customtkinter as ctk
import pandas as pd

from ms_preprocessing.gui.styles import COLORS, FONTS, PADDING, DIMENSIONS
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
        self._context: dict = {}
        self._last_metadata: dict = {}
        self._last_parameters: dict = {}
        self.run_button = None
        self.reset_button = None
        self.input_entry: Optional[ctk.CTkEntry] = None
        self._stats_card: Optional[ctk.CTkFrame] = None
        self._stats_label: Optional[ctk.CTkLabel] = None

        self._create_layout()

    def _create_layout(self) -> None:
        """Create dual-column widget layout."""
        self.grid_columnconfigure(0, weight=0, minsize=DIMENSIONS["left_panel_width"])
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left frame — input + params
        self._left_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        # Right frame — description + stats
        self._right_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._right_frame.grid(row=0, column=1, sticky="nsew")

        self._build_left_panel()
        self._build_right_panel()

    def _build_left_panel(self) -> None:
        """Build left param panel."""
        # Step title
        self.title_label = ctk.CTkLabel(
            self._left_frame,
            text=self.title,
            font=FONTS["heading"],
            anchor="w",
        )
        self.title_label.pack(
            fill="x",
            padx=PADDING["large"],
            pady=(PADDING["large"], PADDING["small"]),
        )

        # Separator
        sep = ctk.CTkFrame(self._left_frame, height=1, fg_color="#2a3f5a")
        sep.pack(fill="x", padx=PADDING["large"], pady=(0, PADDING["medium"]))

        # Input file row
        input_frame = ctk.CTkFrame(self._left_frame, fg_color="transparent")
        input_frame.pack(fill="x", padx=PADDING["large"], pady=(0, PADDING["medium"]))
        input_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(input_frame, text="輸入檔案", font=FONTS["body"]).grid(
            row=0, column=0, padx=(0, PADDING["small"]), sticky="w"
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
            self._left_frame,
            text="參數設定",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(fill="x", padx=PADDING["large"], pady=(0, PADDING["small"]))

        # Params frame (subclasses fill this)
        self.params_frame = ctk.CTkFrame(self._left_frame)
        self.params_frame.pack(
            fill="x",
            padx=PADDING["large"],
            pady=(0, PADDING["medium"]),
        )

        self._create_parameters()

    def _build_right_panel(self) -> None:
        """Build right info/stats panel."""
        # Description card
        desc_card = ctk.CTkFrame(self._right_frame)
        desc_card.pack(fill="x", padx=PADDING["large"], pady=PADDING["large"])

        ctk.CTkLabel(
            desc_card,
            text="關於此步驟",
            font=FONTS["body"],
            anchor="w",
        ).pack(fill="x", padx=PADDING["medium"], pady=(PADDING["medium"], PADDING["small"]))

        self.desc_label = ctk.CTkLabel(
            desc_card,
            text=self.description,
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            wraplength=280,
            justify="left",
            anchor="w",
        )
        self.desc_label.pack(
            fill="x",
            padx=PADDING["medium"],
            pady=(0, PADDING["medium"]),
        )

        # Stats card (hidden until step completes)
        self._stats_card = ctk.CTkFrame(self._right_frame)
        # Not packed until show_stats() is called

        ctk.CTkLabel(
            self._stats_card,
            text="上次執行結果",
            font=FONTS["body"],
            anchor="w",
        ).pack(fill="x", padx=PADDING["medium"], pady=(PADDING["medium"], PADDING["small"]))

        self._stats_label = ctk.CTkLabel(
            self._stats_card,
            text="",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            justify="left",
            anchor="w",
            wraplength=280,
        )
        self._stats_label.pack(
            fill="x",
            padx=PADDING["medium"],
            pady=(0, PADDING["medium"]),
        )

        # Shortcut hint
        step_num = self.step_index + 1
        ctk.CTkLabel(
            self._right_frame,
            text=f"快捷鍵：Ctrl+{step_num}",
            font=FONTS["small"],
            text_color="#3a5a7a",
            anchor="w",
        ).pack(fill="x", padx=PADDING["large"], pady=(0, PADDING["medium"]))

    def show_stats(self, stats: dict) -> None:
        """Display execution stats in the right panel."""
        if not stats or self._stats_card is None or self._stats_label is None:
            return
        lines = [f"{k}：{v}" for k, v in list(stats.items())[:6]]
        self._stats_label.configure(text="\n".join(lines))
        if not self._stats_card.winfo_ismapped():
            self._stats_card.pack(
                fill="x",
                padx=PADDING["large"],
                pady=(0, PADDING["medium"]),
            )

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

    def get_last_parameters(self) -> dict:
        """Get parameters used by the latest run."""
        return dict(self._last_parameters)

    def log(self, message: str) -> None:
        """Log a message."""
        if self.on_log:
            self.on_log(f"[{self.title}] {message}")

    def update_progress(self, value: float, status: str = "") -> None:
        """Delegate progress update to injected callback (Action Bar)."""
        if self._on_progress:
            self._on_progress(value, status)
        self.update_idletasks()

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

        perf_start = take_snapshot()

        try:
            if self.run_button is not None:
                self.run_button.configure(state="disabled")
            self.update_progress(0, "Processing...")

            params = self.get_parameters()
            self._last_parameters = dict(params)
            self.log(f"Starting with parameters: {params}")

            self._last_metadata = {}
            self._result = self.run_processing(self._data, **params)

            self.update_progress(100, "Complete!")
            self.log("Processing completed successfully")

            if self.on_complete and self._result is not None:
                try:
                    self.on_complete(self._result, self._last_metadata)
                except TypeError:
                    self.on_complete(self._result)

        except Exception as e:
            self.update_progress(0, f"Error: {str(e)}")
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
        self.update_progress(0, "Ready")
        self.log("Reset")
