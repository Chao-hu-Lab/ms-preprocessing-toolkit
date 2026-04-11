"""Tests for the Step 2 ISTD marker widget."""

from __future__ import annotations

import pandas as pd
import pytest

from ms_preprocessing.adapters import istd_marker as istd_marker_adapter
from ms_preprocessing.config.pipeline_defaults import STEP2_PARAMS
from ms_preprocessing.gui.widgets.istd_marker_widget import ISTDMarkerWidget
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult


@pytest.fixture
def widget(step_widget_factory):
    return step_widget_factory(ISTDMarkerWidget, step_index=1)


def test_istd_marker_widget_defaults_rt_tolerance_to_1_5(widget) -> None:
    params = widget.get_parameters()

    assert params["ppm_tolerance"] == pytest.approx(20.0)
    assert params["rt_tolerance"] == pytest.approx(1.5)


def test_istd_marker_widget_run_processing_forwards_rt_tolerance(widget, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_from_df(data, **kwargs):
        captured.update(kwargs)
        return ProcessingResult(
            success=True,
            step="istd_marker",
            output_path=None,
            data=data.copy(),
            metadata=ProcessingMetadata(),
            statistics={},
        )

    monkeypatch.setattr(istd_marker_adapter, "run_from_df", fake_run_from_df)
    input_df = pd.DataFrame(
        {
            "Mz/RT": ["Sample_Type", "100.0/1.0"],
            "Case1": ["case", 9000],
            "QC1": ["qc", 9000],
        }
    )

    result = widget.run_processing(input_df, **widget.get_parameters())

    assert result.equals(input_df)
    assert captured["rt_tolerance"] == pytest.approx(1.5)


def test_istd_marker_widget_apply_parameters_populates_profile_defaults(widget) -> None:
    widget.apply_parameters(STEP2_PARAMS)

    params = widget.get_parameters()

    assert params["ppm_tolerance"] == pytest.approx(STEP2_PARAMS["ppm_tolerance"])
    assert params["rt_tolerance"] == pytest.approx(STEP2_PARAMS["rt_tolerance"])
    assert params["istd_mz_list"] == STEP2_PARAMS["istd_mz_list"]
    if STEP2_PARAMS["istd_record_file"]:
        assert params["istd_record_file"] == STEP2_PARAMS["istd_record_file"]
        assert params["istd_record_date"] == STEP2_PARAMS["istd_record_date"]
    else:
        assert "istd_record_file" not in params
        assert "istd_record_date" not in params


def test_istd_marker_widget_uses_aligned_form_columns(widget) -> None:
    assert widget.params_frame.grid_columnconfigure(0)["minsize"] == 180
    assert widget.ppm_entry.grid_info()["column"] == 1
    assert widget.rt_entry.grid_info()["column"] == 1
    assert widget.istd_entry.grid_info()["column"] == 1
    assert widget.record_entry.grid_info()["column"] == 1
    assert widget.date_entry.grid_info()["column"] == 1
    assert widget.ppm_entry.cget("justify") == "center"
    assert widget.rt_entry.cget("justify") == "center"
