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


def test_istd_marker_widget_only_exposes_xic_file_parameter(widget) -> None:
    params = widget.get_parameters()

    assert params["xic_results_file"] == ""
    assert "ppm_tolerance" not in params
    assert "rt_tolerance" not in params
    assert "istd_mz_list" not in params
    assert "istd_record_file" not in params
    assert "istd_record_date" not in params
    assert not hasattr(widget, "ppm_entry")
    assert not hasattr(widget, "rt_entry")


def test_istd_marker_widget_run_processing_forwards_only_xic_source(widget, monkeypatch) -> None:
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
    assert "xic_results_file" in captured
    assert "ppm_tolerance" not in captured
    assert "rt_tolerance" not in captured
    assert "istd_mz_list" not in captured
    assert "istd_record_file" not in captured
    assert "istd_record_date" not in captured


def test_istd_marker_widget_apply_parameters_populates_profile_defaults(widget) -> None:
    widget.apply_parameters(STEP2_PARAMS)

    params = widget.get_parameters()

    assert params["xic_results_file"] == STEP2_PARAMS["xic_results_file"]
    assert "ppm_tolerance" not in params
    assert "rt_tolerance" not in params
    assert "istd_mz_list" not in params
    assert "istd_record_file" not in params
    assert "istd_record_date" not in params


def test_istd_marker_widget_validates_missing_xic_file(widget, tmp_path) -> None:
    warnings = widget.validate_parameters({"xic_results_file": str(tmp_path / "missing.xlsx")})

    assert len(warnings) == 1
    assert warnings[0].code == "xic_results_file_not_found"
    assert warnings[0].blocking is True


def test_istd_marker_widget_uses_aligned_form_columns(widget) -> None:
    assert widget.params_frame.grid_columnconfigure(0)["minsize"] == 180
    assert widget.xic_entry.grid_info()["column"] == 1
