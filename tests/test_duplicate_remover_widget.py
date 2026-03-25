"""Tests for the Step 3 duplicate remover widget."""

from __future__ import annotations

import pandas as pd
import pytest

from ms_preprocessing.adapters import duplicate_remover as duplicate_remover_adapter
from ms_preprocessing.gui.widgets.duplicate_remover_widget import DuplicateRemoverWidget
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult


@pytest.fixture
def widget(ctk_root):
    step3_widget = DuplicateRemoverWidget(ctk_root, step_index=2)
    step3_widget.pack()
    ctk_root.update_idletasks()
    try:
        yield step3_widget
    finally:
        step3_widget.destroy()


def test_duplicate_remover_widget_keeps_controls_in_aligned_columns(widget) -> None:
    assert widget.params_frame.grid_columnconfigure(0)["minsize"] == 180
    assert widget.mz_entry.grid_info()["column"] == 1
    assert widget.rt_entry.grid_info()["column"] == 1
    assert widget.topn_entry.grid_info()["column"] == 1
    assert widget.mz_entry.cget("justify") == "center"
    assert widget.rt_entry.cget("justify") == "center"
    assert widget.topn_entry.cget("justify") == "center"


def test_duplicate_remover_widget_hides_preserve_red_toggle_but_keeps_it_true(widget) -> None:
    params = widget.get_parameters()

    assert not hasattr(widget, "preserve_red_var")
    assert params["preserve_red_font"] is True


def test_duplicate_remover_widget_run_processing_forwards_parameters(widget, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_from_df(data, **kwargs):
        captured.update(kwargs)
        return ProcessingResult(
            success=True,
            step="duplicate_remover",
            output_path=None,
            data=data.copy(),
            metadata=ProcessingMetadata(),
            statistics={},
        )

    monkeypatch.setattr(duplicate_remover_adapter, "run_from_df", fake_run_from_df)
    widget.mz_entry.delete(0, "end")
    widget.mz_entry.insert(0, "15")
    widget.rt_entry.delete(0, "end")
    widget.rt_entry.insert(0, "0.8")
    widget.topn_entry.insert(0, "5")
    input_df = pd.DataFrame(
        {
            "Mz/RT": ["Sample_Type", "100.0/1.0"],
            "Case1": ["case", 9000],
            "QC1": ["qc", 9000],
        }
    )

    result = widget.run_processing(input_df, **widget.get_parameters())

    assert result.equals(input_df)
    assert captured["mz_tolerance_ppm"] == pytest.approx(15.0)
    assert captured["rt_tolerance"] == pytest.approx(0.8)
    assert captured["top_n"] == 5
