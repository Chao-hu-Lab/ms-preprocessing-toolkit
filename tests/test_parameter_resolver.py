"""Tests for shared workflow parameter resolving and validation."""

from __future__ import annotations

from types import SimpleNamespace

from ms_preprocessing.workflow.parameter_resolver import (
    ParameterResolver,
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


def test_gui_parameter_resolver_returns_step_keyed_raw_values() -> None:
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
        "step3": {"mz_tolerance_ppm": 20.0},
        "step4": {"high_det_thresh": 0.3, "low_det_thresh": 0.7},
    }


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
