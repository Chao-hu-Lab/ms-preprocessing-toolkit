"""Tests for shared workflow parameter resolving and validation."""

from __future__ import annotations

import sys
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
        "profile_file": None,
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
        "ratio_rescue_threshold": None,
        "high_det_thresh": None,
        "low_det_thresh": None,
        "qc_ratio_threshold": None,
        "disable_ratio_rescue": False,
        "istd_mz": None,
        "istd_record_file": None,
        "istd_record_date": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _write_profile_file(path, *, background: float = 0.44) -> None:
    path.write_text(
        f"""
version: 1
name: local-test
description: Local test profile
steps:
  step1:
    mode: normalization
    auto_detect: true
    method_file: local-method.docx
  step2:
    xic_results_file: local-xic.xlsx
  step3:
    mz_tolerance_ppm: 12.0
    rt_tolerance: 0.3
    merge_mode: fill_gaps
    preserve_red_font: true
    top_n: null
    enable_degeneracy_annotation: false
    degeneracy_ppm_tolerance: 18.0
    degeneracy_rt_tolerance: 0.04
    degeneracy_correlation_threshold: 0.75
    degeneracy_min_correlation_points: 4
    degeneracy_adduct_table_file: ""
  step4:
    signal_threshold: 6000.0
    background_threshold: {background}
    high_det_thresh: 0.7
    low_det_thresh: 0.15
    qc_ratio_threshold: 0.2
    intensity_fc_threshold: 2.5
    ratio_rescue_threshold: 4.0
    enable_background_threshold: true
    enable_qc_ratio_threshold: true
    enable_intensity_fc_threshold: false
    enable_mnar_gate: true
    enable_ratio_rescue: true
""".lstrip(),
        encoding="utf-8",
    )


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


def test_cli_parameter_resolver_accepts_ratio_rescue_override_and_disable() -> None:
    args = _base_cli_args(ratio_rescue_threshold=4.0, disable_ratio_rescue=True)

    resolved = ParameterResolver.from_cli_args(args)

    assert resolved["step4"]["ratio_rescue_threshold"] == 4.0
    assert resolved["step4"]["enable_ratio_rescue"] is False


def test_cli_parameter_resolver_loads_explicit_profile_file(tmp_path) -> None:
    profile_path = tmp_path / "batch-profile.yml"
    _write_profile_file(profile_path, background=0.44)
    args = _base_cli_args(profile_file=str(profile_path), profile="strict")

    resolved = ParameterResolver.from_cli_args(args)

    assert resolved["step1"]["method_file"] == "local-method.docx"
    assert resolved["step2"]["xic_results_file"] == "local-xic.xlsx"
    assert resolved["step3"]["mz_tolerance_ppm"] == pytest.approx(12.0)
    assert resolved["step3"]["merge_mode"] == "fill_gaps"
    assert resolved["step4"]["background_threshold"] == pytest.approx(0.44)
    assert resolved["step4"]["ratio_rescue_threshold"] == pytest.approx(4.0)


def test_cli_parameter_resolver_explicit_overrides_win_over_profile_file(tmp_path) -> None:
    profile_path = tmp_path / "batch-profile.yml"
    _write_profile_file(profile_path, background=0.44)
    args = _base_cli_args(
        profile_file=str(profile_path),
        mz_tol=21.0,
        bg_threshold=0.66,
        ratio_rescue_threshold=5.0,
        disable_ratio_rescue=True,
    )

    resolved = ParameterResolver.from_cli_args(args)

    assert resolved["step3"]["mz_tolerance_ppm"] == pytest.approx(21.0)
    assert resolved["step4"]["background_threshold"] == pytest.approx(0.66)
    assert resolved["step4"]["ratio_rescue_threshold"] == pytest.approx(5.0)
    assert resolved["step4"]["enable_ratio_rescue"] is False


def test_cli_parameter_resolver_rejects_runtime_file_keys_in_profile_file(tmp_path) -> None:
    profile_path = tmp_path / "invalid-profile.yml"
    _write_profile_file(profile_path)
    text = profile_path.read_text(encoding="utf-8")
    profile_path.write_text(
        text.replace("step1:\n    mode:", "step1:\n    input_file: data.xlsx\n    mode:"),
        encoding="utf-8",
    )
    args = _base_cli_args(profile_file=str(profile_path))

    with pytest.raises(ValueError, match="runtime file key"):
        ParameterResolver.from_cli_args(args)


def test_main_parser_exposes_ratio_rescue_cli_flags(monkeypatch, tmp_path) -> None:
    from ms_preprocessing import main as main_module

    input_path = tmp_path / "input.csv"
    input_path.write_text("Mz/RT,Tolerance\nSample_Type,na\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run_cli(args):
        captured.update(vars(args))
        return 0

    monkeypatch.setattr(main_module, "run_cli", fake_run_cli)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ms-preprocessing",
            "--input",
            str(input_path),
            "--no-gui",
            "--ratio-rescue-threshold",
            "4.0",
            "--disable-ratio-rescue",
            "--profile-file",
            str(tmp_path / "profile.yml"),
        ],
    )

    assert main_module.main() == 0
    assert captured["ratio_rescue_threshold"] == 4.0
    assert captured["disable_ratio_rescue"] is True
    assert captured["profile_file"] == str(tmp_path / "profile.yml")


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
            "ratio_rescue_threshold": 3.0,
            "qc_ratio_threshold": 0.25,
            "enable_background_threshold": True,
            "enable_qc_ratio_threshold": True,
            "enable_intensity_fc_threshold": False,
            "enable_mnar_gate": True,
            "enable_ratio_rescue": True,
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
