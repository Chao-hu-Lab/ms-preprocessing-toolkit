"""Shared parameter validation helpers for GUI and CLI pipeline execution."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ValidationWarning:
    code: str
    message: str
    blocking: bool = False


def validate_step1_params(params: dict) -> list[ValidationWarning]:
    warnings: list[ValidationWarning] = []
    method_file = str(params.get("method_file") or "").strip()
    if method_file and not Path(method_file).exists():
        warnings.append(
            ValidationWarning(
                code="method_file_not_found",
                message=f"Method file does not exist: {Path(method_file)}",
                blocking=True,
            )
        )
    return warnings


def validate_step2_params(params: dict) -> list[ValidationWarning]:
    warnings: list[ValidationWarning] = []
    legacy_keys = ("istd_record_file", "istd_record_date", "istd_mz_list")
    if any(key in params for key in legacy_keys):
        warnings.append(
            ValidationWarning(
                code="legacy_step2_source_key",
                message=(
                    "Step2 now requires an XIC Extractor results workbook. "
                    "Please set xic_results_file or pass --xic-results-file."
                ),
                blocking=True,
            )
        )
        return warnings
    from ms_preprocessing.config.pipeline_defaults import (
        STEP2_XIC_REQUIRED_MESSAGE,
        get_legacy_step2_source_details,
    )

    legacy_source_details = get_legacy_step2_source_details()
    if legacy_source_details:
        warnings.append(
            ValidationWarning(
                code="legacy_step2_source_key",
                message=f"{STEP2_XIC_REQUIRED_MESSAGE} Remove {', '.join(legacy_source_details)}.",
                blocking=True,
            )
        )
        return warnings

    xic_results_file = str(params.get("xic_results_file") or "").strip()
    if not xic_results_file:
        warnings.append(
            ValidationWarning(
                code="xic_results_file_required",
                message=(
                    "Step2 now requires an XIC Extractor results workbook. "
                    "Please set xic_results_file or pass --xic-results-file."
                ),
                blocking=True,
            )
        )
        return warnings

    xic_path = Path(xic_results_file)
    if not xic_path.exists():
        warnings.append(
            ValidationWarning(
                code="xic_results_file_not_found",
                message=f"XIC results file does not exist: {xic_path}",
                blocking=True,
            )
        )
    elif xic_path.suffix.lower() != ".xlsx":
        warnings.append(
            ValidationWarning(
                code="invalid_xic_results_file_extension",
                message=f"XIC results file must be an .xlsx workbook: {xic_path}",
                blocking=True,
            )
        )
    return warnings


def validate_step4_params(params: dict) -> list[ValidationWarning]:
    warnings: list[ValidationWarning] = []
    high = _to_float(params.get("high_det_thresh"))
    low = _to_float(params.get("low_det_thresh"))
    if high is not None and low is not None and high <= low:
        warnings.append(
            ValidationWarning(
                code="invalid_mnar_threshold_order",
                message="High detection threshold must be greater than low detection threshold.",
                blocking=True,
            )
        )

    ratio_rescue = _to_float(params.get("ratio_rescue_threshold"))
    if ratio_rescue is not None and ratio_rescue < 1.0:
        warnings.append(
            ValidationWarning(
                code="invalid_ratio_rescue_threshold",
                message="Ratio rescue threshold must be >= 1.0.",
                blocking=True,
            )
        )

    default_on_gates = (
        ("enable_background_threshold", "background_gate_disabled", "Background gate is disabled."),
        ("enable_qc_ratio_threshold", "qc_ratio_gate_disabled", "QC_ratio gate is disabled."),
        ("enable_mnar_gate", "mnar_gate_disabled", "MNAR gate is disabled."),
        ("enable_ratio_rescue", "ratio_rescue_gate_disabled", "Ratio rescue gate is disabled."),
    )
    for key, code, message in default_on_gates:
        if params.get(key) is False:
            warnings.append(ValidationWarning(code=code, message=message))
    return warnings


def has_blocking_warnings(warnings: Iterable[ValidationWarning]) -> bool:
    return any(warning.blocking for warning in warnings)


def format_validation_warnings(warnings: Iterable[ValidationWarning]) -> str:
    return "\n".join(
        f"{'Blocking' if warning.blocking else 'Warning'}: {warning.message}"
        for warning in warnings
    )


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
