"""Layout builders for the main preprocessing window."""

from __future__ import annotations

import customtkinter as ctk

from ms_preprocessing.config.settings import Settings
from ms_preprocessing.gui.styles import COLORS, FONTS, PADDING, DIMENSIONS
from ms_preprocessing.gui.widgets.data_organizer_widget import DataOrganizerWidget
from ms_preprocessing.gui.widgets.duplicate_remover_widget import DuplicateRemoverWidget
from ms_preprocessing.gui.widgets.feature_filter_widget import FeatureFilterWidget
from ms_preprocessing.gui.widgets.istd_marker_widget import ISTDMarkerWidget


class MainWindowLayoutMixin:
    """Build and update the CustomTkinter view hierarchy."""

    def _create_layout(self) -> None:
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        self._create_pipeline_nav()
        self._create_sidebar()
        self._create_content_area()

    def _update_action_bar_progress(self, value: float, status: str = "") -> None:
        self.progress_bar.set(value / 100)
        if status:
            self.status_label.configure(text=status)

    def _create_pipeline_nav(self) -> None:
        nav_frame = ctk.CTkFrame(self, height=36, fg_color="#0d1b2a")
        nav_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        nav_frame.grid_propagate(False)

        inner = ctk.CTkFrame(nav_frame, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        steps = [
            ("Step 1: Preprocessing", True),
            ("Step 2: Normalization", False),
            ("Step 3: Statistical Analysis", False),
        ]

        for index, (label, is_current) in enumerate(steps):
            if index > 0:
                ctk.CTkLabel(
                    inner,
                    text="  ->  ",
                    font=("Consolas", 14),
                    text_color="#4a6fa5",
                ).pack(side="left")

            fg_color = "#1f538d" if is_current else "transparent"
            text_color = "#e0e0e0" if is_current else "#5a6a7a"
            font = (FONTS["body"][0], FONTS["body"][1], "bold") if is_current else FONTS["small"]
            ctk.CTkLabel(
                inner,
                text=label,
                font=font,
                text_color=text_color,
                fg_color=fg_color,
                corner_radius=4,
                padx=10,
                pady=2,
            ).pack(side="left")

    def _create_sidebar(self) -> None:
        self.sidebar = ctk.CTkFrame(self, width=DIMENSIONS["sidebar_width"])
        self.sidebar.grid(row=1, column=0, rowspan=1, sticky="nsw")
        self.sidebar.grid_propagate(False)

        ctk.CTkLabel(
            self.sidebar,
            text="MS Preprocessing\nToolkit",
            font=FONTS["heading"],
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=PADDING["medium"], pady=(PADDING["large"], PADDING["small"]))

        ctk.CTkFrame(self.sidebar, height=1, fg_color="#2a3f5a").pack(
            fill="x",
            padx=PADDING["medium"],
            pady=(0, PADDING["small"]),
        )

        ctk.CTkLabel(
            self.sidebar,
            text="Workflow",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(fill="x", padx=PADDING["medium"], pady=(0, PADDING["small"]))

        self.step_buttons = []
        self._step_status_labels = []

        for index, (_, name_zh, _) in enumerate(Settings.WORKFLOW_STEPS):
            row_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
            row_frame.pack(fill="x", padx=PADDING["small"], pady=2)
            row_frame.grid_columnconfigure(1, weight=1)

            status_label = ctk.CTkLabel(
                row_frame,
                text=">",
                font=FONTS["body"],
                text_color="#4a6fa5",
                width=20,
            )
            status_label.grid(row=0, column=0, padx=(4, 0))
            self._step_status_labels.append(status_label)

            button = ctk.CTkButton(
                row_frame,
                text=f"{index + 1}. {name_zh}",
                command=lambda step_index=index: self._switch_step(step_index),
                anchor="w",
                height=32,
                fg_color=COLORS["primary"] if index == 0 else "transparent",
                border_width=0,
                font=FONTS["body"],
            )
            button.grid(row=0, column=1, sticky="ew", padx=4)
            self.step_buttons.append(button)

        ctk.CTkFrame(self.sidebar, fg_color="transparent").pack(fill="both", expand=True)
        ctk.CTkFrame(self.sidebar, height=1, fg_color="#2a3f5a").pack(
            fill="x",
            padx=PADDING["medium"],
            pady=(0, PADDING["small"]),
        )

        ctk.CTkLabel(
            self.sidebar,
            text="Actions",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(fill="x", padx=PADDING["medium"], pady=(0, PADDING["small"]))

        action_buttons = [
            ("Export Results", self._export_results, COLORS["secondary"]),
            ("Open Output Folder", self._open_output_folder, "transparent"),
            ("Run All Steps", self._run_all_steps, COLORS["accent"]),
        ]
        for label, command, color in action_buttons:
            ctk.CTkButton(
                self.sidebar,
                text=label,
                command=command,
                height=32,
                fg_color=color,
                font=FONTS["small"],
                anchor="w",
            ).pack(fill="x", padx=PADDING["medium"], pady=2)

        self.export_dnp_btn = ctk.CTkButton(
            self.sidebar,
            text="Export DNP",
            command=self._export_to_dnp,
            height=32,
            fg_color="#6b7280",
            font=FONTS["small"],
            anchor="w",
            state="disabled",
        )
        self.export_dnp_btn.pack(
            fill="x",
            padx=PADDING["medium"],
            pady=(2, PADDING["large"]),
        )

    def _create_content_area(self) -> None:
        self.content_frame = ctk.CTkFrame(self)
        self.content_frame.grid(row=1, column=1, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=0)
        self.content_frame.grid_rowconfigure(1, weight=1)

        self.main_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.main_frame.grid(row=0, column=0, sticky="ew")
        self.main_frame.grid_columnconfigure(0, weight=1)

        self.step_widgets = [
            DataOrganizerWidget(
                self.main_frame,
                step_index=0,
                on_load_file=self._load_file_for_step,
                on_complete=self._on_step_complete,
                on_log=self._log,
                on_progress=self._update_action_bar_progress,
            ),
            ISTDMarkerWidget(
                self.main_frame,
                step_index=1,
                on_load_file=self._load_file_for_step,
                on_complete=self._on_step_complete,
                on_log=self._log,
                on_progress=self._update_action_bar_progress,
            ),
            DuplicateRemoverWidget(
                self.main_frame,
                step_index=2,
                on_load_file=self._load_file_for_step,
                on_complete=self._on_step_complete,
                on_log=self._log,
                on_progress=self._update_action_bar_progress,
            ),
            FeatureFilterWidget(
                self.main_frame,
                step_index=3,
                on_load_file=self._load_file_for_step,
                on_complete=self._on_step_complete,
                on_log=self._log,
                on_progress=self._update_action_bar_progress,
            ),
        ]

        self._show_step(0)
        self._create_bottom_group()

    def _create_bottom_group(self) -> None:
        self.bottom_frame = ctk.CTkFrame(self.content_frame, fg_color="#0d1b2a")
        self.bottom_frame.grid(row=1, column=0, sticky="nsew")
        self.bottom_frame.grid_columnconfigure(0, weight=1)
        self.bottom_frame.grid_rowconfigure(0, weight=0)
        self.bottom_frame.grid_rowconfigure(1, weight=0)
        self.bottom_frame.grid_rowconfigure(2, weight=0)
        self.bottom_frame.grid_rowconfigure(3, weight=1)

        self.progress_bar = ctk.CTkProgressBar(self.bottom_frame, height=6)
        self.progress_bar.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=PADDING["large"],
            pady=(PADDING["medium"], 4),
        )
        self.progress_bar.set(0)

        button_row = ctk.CTkFrame(self.bottom_frame, fg_color="transparent")
        button_row.grid(row=1, column=0, sticky="ew", padx=PADDING["large"], pady=(0, PADDING["small"]))
        button_row.grid_columnconfigure(0, weight=1)
        button_row.grid_columnconfigure(3, weight=1)

        self.run_step_btn = ctk.CTkButton(
            button_row,
            text="Run Step",
            command=self._run_current_step,
            width=110,
            height=34,
            font=FONTS["body"],
            fg_color=COLORS["primary"],
        )
        self.run_step_btn.grid(row=0, column=1, padx=(0, PADDING["medium"]))

        self.reset_step_btn = ctk.CTkButton(
            button_row,
            text="Reset",
            command=self._reset_current_step,
            width=90,
            height=34,
            font=FONTS["body"],
            fg_color="transparent",
            border_width=1,
        )
        self.reset_step_btn.grid(row=0, column=2, padx=(0, PADDING["medium"]))

        self.status_label = ctk.CTkLabel(
            button_row,
            text="Ready",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
        )
        self.status_label.grid(row=0, column=3, padx=(0, PADDING["large"]), sticky="w")

        log_header = ctk.CTkFrame(self.bottom_frame, fg_color="transparent")
        log_header.grid(row=2, column=0, sticky="ew", padx=PADDING["medium"], pady=(PADDING["small"], 0))

        ctk.CTkLabel(
            log_header,
            text="Execution Log",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
        ).pack(side="left")

        ctk.CTkButton(
            log_header,
            text="Clear",
            command=self._clear_log,
            width=50,
            height=22,
            font=FONTS["small"],
            fg_color="transparent",
            border_width=1,
        ).pack(side="right")

        self.log_text = ctk.CTkTextbox(self.bottom_frame, font=FONTS["mono"])
        self.log_text.grid(
            row=3,
            column=0,
            sticky="nsew",
            padx=PADDING["medium"],
            pady=(4, PADDING["medium"]),
        )

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-o>", lambda _event: self._load_file_for_step(self._current_step))
        self.bind("<Control-s>", lambda _event: self._export_results())
        self.bind("<Control-1>", lambda _event: self._switch_step(0))
        self.bind("<Control-2>", lambda _event: self._switch_step(1))
        self.bind("<Control-3>", lambda _event: self._switch_step(2))
        self.bind("<Control-4>", lambda _event: self._switch_step(3))

    def _show_step(self, step_index: int) -> None:
        for widget in self.step_widgets:
            widget.grid_forget()
        self.step_widgets[step_index].grid(
            row=0,
            column=0,
            sticky="ew",
            padx=0,
            pady=0,
        )
