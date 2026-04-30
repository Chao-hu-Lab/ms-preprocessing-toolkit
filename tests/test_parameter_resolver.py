"""Tests for shared workflow parameter resolving and validation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ms_preprocessing.workflow.parameter_resolver import (
    ParameterResolver,
    STEP2_XIC_REQUIRED_MESSAGE,
    WorkflowValidationService,
)


def _base_cli_args(**overrides):
    values = {
        "profile": "default",
        "method_file": None,
        "xic_results_file": None,
        "mz_tol": None,
        "rt_tol": None,
        "merge_mode": None,
        "enable_degeneracy_annotation": False,
        "degeneracy_ppm_tol": None,
        "degeneracy_rt_tol": None,
        "degeneracy_corr_threshold": None,
        "degeneracy_min_corr_points": None,
        "degeneracy_adduct_table_file": None,
        "bg_threshold": None,
        "intensity_fc_threshold": None,
        "high_det_thresh": None,
        "low_det_thresh": None,
        "qc_ratio_threshold": None,
        "istd_mz": None,
        "istd_record_file": None,
        "istd_record_date": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_cli_parameter_resolver_preserves_existing_override_contract() -> None:
    from ms_preprocessing.main import _resolve_cli_step_parameters

    args = _base_cli_args(
        method_file="method.docx",
        xic_results_file="xic.xlsx",
        mz_tol=15.0,
        rt_tol=0.2,
        high_det_thresh=0.9,
        low_det_thresh=0.1,
    )

    assert _resolve_cli_step_parameters(args) == ParameterResolver.from_cli_args(args)
    resolved = ParameterResolver.from_cli_args(args)
    assert resolved["step1"]["method_file"] == "method.docx"
    assert resolved["step2"]["xic_results_file"] == "xic.xlsx"
    assert resolved["step3"]["mz_tolerance_ppm"] == 15.0
    assert resolved["step3"]["rt_tolerance"] == 0.2
    assert resolved["step4"]["high_det_thresh"] == 0.9
    assert resolved["step4"]["low_det_thresh"] == 0.1


def test_gui_parameter_resolver_returns_canonical_step_keyed_values() -> None:
    params = ParameterResolver.from_gui_step_params(
        [
            {"method_file": "method.docx"},
            {"xic_results_file": "xic.xlsx"},
            {"mz_tolerance_ppm": 20.0},
            {"high_det_thresh": 0.3, "low_det_thresh": 0.7},
        ]
    )

    assert params == {
        "step1": {"method_file": "method.docx"},
        "step2": {"xic_results_file": "xic.xlsx"},
        "step3": {
            "mz_tolerance_ppm": 20.0,
            "rt_tolerance": 0.1,
            "merge_mode": "per_sample_max",
            "preserve_red_font": True,
            "top_n": None,
            "enable_degeneracy_annotation": False,
            "degeneracy_ppm_tolerance": 20.0,
            "degeneracy_rt_tolerance": 0.05,
            "degeneracy_correlation_threshold": 0.8,
            "degeneracy_min_correlation_points": 3,
            "degeneracy_adduct_table_file": "",
        },
        "step4": {
            "signal_threshold": 5000,
            "background_threshold": 0.33,
            "high_det_thresh": 0.3,
            "low_det_thresh": 0.7,
            "intensity_fc_threshold": 2.0,
            "qc_ratio_threshold": 0.25,
            "enable_background_threshold": True,
            "enable_qc_ratio_threshold": True,
            "enable_intensity_fc_threshold": False,
        },
    }


@pytest.mark.parametrize(
    ("attr", "flag"),
    [
        ("istd_mz", "--istd-mz"),
        ("istd_record_file", "--istd-record-file"),
        ("istd_record_date", "--istd-record-date"),
    ],
)
def test_cli_parameter_resolver_rejects_legacy_step2_flags(attr: str, flag: str) -> None:
    args = _base_cli_args(**{attr: "legacy-value"})

    with pytest.raises(ValueError) as exc_info:
        ParameterResolver.from_cli_args(args)

    message = str(exc_info.value)
    assert STEP2_XIC_REQUIRED_MESSAGE in message
    assert flag in message


def test_workflow_validation_service_collects_prefixed_gui_warnings() -> None:
    warnings = WorkflowValidationService().collect_prefixed(
        "all",
        {
            "step1": {},
            "step2": {"xic_results_file": ""},
            "step3": {},
            "step4": {"high_det_thresh": 0.3, "low_det_thresh": 0.7},
        },
    )

    assert [warning.code for warning in warnings] == [
        "xic_results_file_required",
        "invalid_mnar_threshold_order",
    ]
    assert warnings[0].message.startswith("Step 2:")
    assert warnings[1].message.startswith("Step 4:")
    assert all(warning.blocking for warning in warnings)
