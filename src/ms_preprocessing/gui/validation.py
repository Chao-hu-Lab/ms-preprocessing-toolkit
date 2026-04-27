"""Shared GUI parameter validation helpers."""

from __future__ import annotations

import re
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
    record_file = str(params.get("istd_record_file") or "").strip()
    if record_file and not Path(record_file).exists():
        warnings.append(
            ValidationWarning(
                code="istd_record_file_not_found",
                message=f"ISTD record file does not exist: {Path(record_file)}",
                blocking=True,
            )
        )

    record_date = str(params.get("istd_record_date") or "").strip()
    if record_date and not re.fullmatch(r"\d{8}", record_date):
        warnings.append(
            ValidationWarning(
                code="invalid_istd_date",
                message="ISTD record date must use YYYYMMDD format.",
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

    default_on_gates = (
        ("enable_background_threshold", "background_gate_disabled", "Background gate is disabled."),
        ("enable_qc_ratio_threshold", "qc_ratio_gate_disabled", "QC_ratio gate is disabled."),
        ("enable_mnar_gate", "mnar_gate_disabled", "MNAR gate is disabled."),
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
