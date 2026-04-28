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


def test_step2_missing_xic_results_file_returns_blocking_warning() -> None:
    warnings = validate_step2_params({"xic_results_file": ""})

    assert len(warnings) == 1
    assert warnings[0].code == "xic_results_file_required"
    assert warnings[0].blocking is True


def test_step2_nonexistent_xic_results_file_returns_blocking_warning(tmp_path) -> None:
    warnings = validate_step2_params({"xic_results_file": str(tmp_path / "missing.xlsx")})

    assert len(warnings) == 1
    assert warnings[0].code == "xic_results_file_not_found"
    assert warnings[0].blocking is True


def test_step2_non_xlsx_xic_results_file_returns_blocking_warning(tmp_path) -> None:
    xic_file = tmp_path / "xic_results.csv"
    xic_file.write_text("placeholder", encoding="utf-8")

    warnings = validate_step2_params({"xic_results_file": str(xic_file)})

    assert len(warnings) == 1
    assert warnings[0].code == "invalid_xic_results_file_extension"
    assert warnings[0].blocking is True


def test_step2_existing_xlsx_xic_results_file_passes_path_validation(tmp_path) -> None:
    xic_file = tmp_path / "xic_results.xlsx"
    xic_file.write_text("placeholder", encoding="utf-8")

    warnings = validate_step2_params({"xic_results_file": str(xic_file)})

    assert warnings == []


def test_step2_legacy_keys_return_blocking_warning() -> None:
    warnings = validate_step2_params({"istd_record_file": "legacy.xlsx"})

    assert len(warnings) == 1
    assert warnings[0].code == "legacy_step2_source_key"
    assert warnings[0].blocking is True


def test_step2_legacy_env_returns_blocking_warning(monkeypatch, tmp_path) -> None:
    with monkeypatch.context() as env:
        env.setenv("MSPTK_ISTD_RECORD_FILE", "legacy.xlsx")
        env.setenv("MSPTK_LOCAL_REFERENCE_CONFIG", str(tmp_path / "missing-config.json"))

        warnings = validate_step2_params({"xic_results_file": ""})

    assert len(warnings) == 1
    assert warnings[0].code == "legacy_step2_source_key"
    assert warnings[0].blocking is True


def test_step2_legacy_local_config_returns_blocking_warning(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "local_reference_paths.json"
    config_path.write_text('{"istd_record_file": "legacy.xlsx"}', encoding="utf-8")

    with monkeypatch.context() as env:
        env.delenv("MSPTK_ISTD_RECORD_FILE", raising=False)
        env.delenv("MSPTK_ISTD_RECORD_DATE", raising=False)
        env.setenv("MSPTK_LOCAL_REFERENCE_CONFIG", str(config_path))

        warnings = validate_step2_params({"xic_results_file": ""})

    assert len(warnings) == 1
    assert warnings[0].code == "legacy_step2_source_key"
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
