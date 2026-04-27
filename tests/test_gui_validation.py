"""Tests for GUI parameter validation guardrails."""

from __future__ import annotations

from ms_preprocessing.gui.validation import (
    ValidationWarning,
    format_validation_warnings,
    has_blocking_warnings,
    validate_step1_params,
    validate_step2_params,
    validate_step4_params,
)


def test_step1_missing_method_file_returns_blocking_warning(tmp_path) -> None:
    warnings = validate_step1_params({"method_file": str(tmp_path / "missing.docx")})

    assert warnings == [
        ValidationWarning(
            code="method_file_not_found",
            message=f"Method file does not exist: {tmp_path / 'missing.docx'}",
            blocking=True,
        )
    ]


def test_step2_invalid_istd_date_returns_blocking_warning() -> None:
    warnings = validate_step2_params({"istd_record_date": "2026-01-06"})

    assert len(warnings) == 1
    assert warnings[0].code == "invalid_istd_date"
    assert warnings[0].blocking is True


def test_step4_high_detection_threshold_must_exceed_low_threshold() -> None:
    warnings = validate_step4_params({"high_det_thresh": 0.3, "low_det_thresh": 0.7})

    assert len(warnings) == 1
    assert warnings[0].code == "invalid_mnar_threshold_order"
    assert warnings[0].blocking is True


def test_step4_disabling_default_on_gates_returns_nonblocking_warnings() -> None:
    warnings = validate_step4_params(
        {
            "high_det_thresh": 0.8,
            "low_det_thresh": 0.2,
            "enable_background_threshold": False,
            "enable_qc_ratio_threshold": False,
            "enable_mnar_gate": False,
            "enable_intensity_fc_threshold": False,
        }
    )

    assert {warning.code for warning in warnings} == {
        "background_gate_disabled",
        "qc_ratio_gate_disabled",
        "mnar_gate_disabled",
    }
    assert all(warning.blocking is False for warning in warnings)


def test_validation_warning_helpers_report_blocking_and_format_messages() -> None:
    warnings = [
        ValidationWarning("soft", "Soft warning"),
        ValidationWarning("hard", "Hard warning", blocking=True),
    ]

    assert has_blocking_warnings(warnings) is True
    assert format_validation_warnings(warnings) == "Warning: Soft warning\nBlocking: Hard warning"
