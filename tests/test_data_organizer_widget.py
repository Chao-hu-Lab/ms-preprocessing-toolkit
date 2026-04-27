"""Tests for the Step 1 data organizer widget."""

from __future__ import annotations

import pandas as pd
import pytest

from ms_preprocessing.adapters import data_organizer as data_organizer_adapter
from ms_preprocessing.gui.widgets.data_organizer_widget import DataOrganizerWidget
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult


@pytest.fixture
def widget(step_widget_factory):
    return step_widget_factory(DataOrganizerWidget, step_index=0)


def test_data_organizer_widget_uses_global_form_alignment(widget) -> None:
    assert widget.params_frame.grid_columnconfigure(0)["minsize"] == 180
    assert widget.method_entry.grid_info()["column"] == 1


def test_data_organizer_widget_validates_missing_method_file(widget, tmp_path) -> None:
    warnings = widget.validate_parameters({"method_file": str(tmp_path / "missing.docx")})

    assert len(warnings) == 1
    assert warnings[0].code == "method_file_not_found"
    assert warnings[0].blocking is True


def test_data_organizer_widget_hides_mode_selector_and_defaults_normalization(widget) -> None:
    params = widget.get_parameters()

    assert not hasattr(widget, "mode_selector")
    assert not hasattr(widget, "mode_var")
    assert params["mode"] == "normalization"


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

    result = widget.run_processing(input_df, auto_detect=False)

    assert result.equals(input_df)
    assert captured["mode"] == "normalization"
    assert captured["auto_detect"] is True


def test_data_organizer_widget_has_combined_preprocessor_controls_without_output_picker(widget) -> None:
    assert widget.combined_tsv_entry is not None
    assert widget.combined_method_entry is not None
    assert not hasattr(widget, "combined_output_entry")
    assert not hasattr(widget, "combined_output_btn")
    assert widget.combined_run_btn is not None


def test_combined_method_prefill_is_one_way(widget) -> None:
    widget.combined_method_entry.insert(0, "combined-method.docx")

    widget.prefill_normal_method_from_combined()

    assert widget.method_entry.get() == "combined-method.docx"
    widget.method_entry.delete(0, "end")
    widget.method_entry.insert(0, "normal-method.docx")
    assert widget.combined_method_entry.get() == "combined-method.docx"
    assert widget.get_parameters()["method_file"] == "normal-method.docx"


def test_get_parameters_uses_combined_method_as_normal_default(widget) -> None:
    widget.combined_method_entry.insert(0, "combined-method.docx")

    params = widget.get_parameters()

    assert params["method_file"] == "combined-method.docx"


def test_combined_method_browse_prefills_normal_method(widget, monkeypatch) -> None:
    monkeypatch.setattr(
        "ms_preprocessing.gui.widgets.data_organizer_widget.filedialog.askopenfilename",
        lambda **_kwargs: "combined-method.docx",
    )

    widget._browse_combined_method_file()

    assert widget.combined_method_entry.get() == "combined-method.docx"
    assert widget.method_entry.get() == "combined-method.docx"


def test_normal_step1_rejects_raw_combined_tsv(widget) -> None:
    df = pd.DataFrame(
        {
            "Mz": [1.0],
            "RT": [2.0],
            "SampleA": [10],
            "MZmine ID": ["id1"],
            "mz": [1.0],
            "rt": [2.0],
            "SampleA.1": [99],
        }
    )

    with pytest.raises(Exception, match="Combined TSV"):
        widget.run_processing(df)
