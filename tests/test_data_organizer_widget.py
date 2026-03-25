"""Tests for the Step 1 data organizer widget."""

from __future__ import annotations

import pandas as pd
import pytest

from ms_preprocessing.adapters import data_organizer as data_organizer_adapter
from ms_preprocessing.gui.widgets.data_organizer_widget import DataOrganizerWidget
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult


@pytest.fixture
def widget(ctk_root):
    step1_widget = DataOrganizerWidget(ctk_root, step_index=0)
    step1_widget.pack()
    ctk_root.update_idletasks()
    try:
        yield step1_widget
    finally:
        step1_widget.destroy()


def test_data_organizer_widget_uses_global_form_alignment(widget) -> None:
    assert widget.params_frame.grid_columnconfigure(0)["minsize"] == 180
    assert widget.mode_selector.grid_info()["column"] == 1
    assert widget.method_entry.grid_info()["column"] == 1


def test_data_organizer_widget_hides_auto_detect_but_keeps_it_enabled(widget) -> None:
    params = widget.get_parameters()

    assert not hasattr(widget, "auto_detect_var")
    assert params["auto_detect"] is True


def test_data_organizer_widget_run_processing_forces_auto_detect(widget, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_from_df(data, **kwargs):
        captured.update(kwargs)
        return ProcessingResult(
            success=True,
            step="data_organizer",
            output_path=None,
            data=data.copy(),
            metadata=ProcessingMetadata(),
            statistics={},
        )

    monkeypatch.setattr(data_organizer_adapter, "run_from_df", fake_run_from_df)
    input_df = pd.DataFrame({"A": [1], "B": [2]})

    result = widget.run_processing(input_df, mode="statistics", auto_detect=False)

    assert result.equals(input_df)
    assert captured["mode"] == "statistics"
    assert captured["auto_detect"] is True
