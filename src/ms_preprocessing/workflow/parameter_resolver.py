"""Shared parameter resolving and validation for CLI and GUI workflows."""

from __future__ import annotations

from typing import Any

from ms_preprocessing.pipeline_validation import (
    ValidationWarning,
    validate_step1_params,
    validate_step2_params,
    validate_step4_params,
)

STEP2_XIC_REQUIRED_MESSAGE = (
    "Step2 now requires an XIC Extractor results workbook. "
    "Please set xic_results_file or pass --xic-results-file."
)
_LEGACY_STEP2_CLI_FLAGS = {
    "istd_mz": "--istd-mz",
    "istd_record_file": "--istd-record-file",
    "istd_record_date": "--istd-record-date",
}


def legacy_step2_cli_flags(args: Any) -> list[str]:
    """Return legacy Step2 CLI flags present in parsed argparse args."""
    return [
        flag
        for attr, flag in _LEGACY_STEP2_CLI_FLAGS.items()
        if getattr(args, attr, None) not in (None, "")
    ]


class ParameterResolver:
    """Resolve workflow parameters from CLI args or GUI raw step values."""

    @staticmethod
    def from_cli_args(args: Any) -> dict[str, dict[str, Any]]:
        from ms_preprocessing.config import get_pipeline_profile

        legacy_flags = legacy_step2_cli_flags(args)
        if legacy_flags:
            raise ValueError(
                f"{STEP2_XIC_REQUIRED_MESSAGE} Unsupported legacy option(s): "
                f"{', '.join(legacy_flags)}."
            )

        profile = get_pipeline_profile(args.profile)
        step1 = dict(profile["step1"])
        step2 = dict(profile["step2"])
        step3 = dict(profile["step3"])
        step4 = dict(profile["step4"])

        merge_mode = getattr(args, "merge_mode", None)
        enable_degeneracy_annotation = bool(
            getattr(args, "enable_degeneracy_annotation", False)
        )
        degeneracy_ppm_tol = getattr(args, "degeneracy_ppm_tol", None)
        degeneracy_rt_tol = getattr(args, "degeneracy_rt_tol", None)
        degeneracy_corr_threshold = getattr(args, "degeneracy_corr_threshold", None)
        degeneracy_min_corr_points = getattr(args, "degeneracy_min_corr_points", None)
        degeneracy_adduct_table_file = getattr(args, "degeneracy_adduct_table_file", None)

        return {
            "step1": {
                "method_file": (
                    args.method_file if args.method_file is not None else step1.get("method_file")
                ),
            },
            "step2": {
                "xic_results_file": (
                    args.xic_results_file
                    if getattr(args, "xic_results_file", None) is not None
                    else step2.get("xic_results_file")
                ),
            },
            "step3": {
                "mz_tolerance_ppm": (
                    args.mz_tol if args.mz_tol is not None else step3.get("mz_tolerance_ppm")
                ),
                "rt_tolerance": (
                    args.rt_tol if args.rt_tol is not None else step3.get("rt_tolerance")
                ),
                "merge_mode": (
                    merge_mode if merge_mode is not None else step3.get("merge_mode", "per_sample_max")
                ),
                "preserve_red_font": step3.get("preserve_red_font"),
                "top_n": step3.get("top_n"),
                "enable_degeneracy_annotation": (
                    enable_degeneracy_annotation
                    if enable_degeneracy_annotation
                    else step3.get("enable_degeneracy_annotation", False)
                ),
                "degeneracy_ppm_tolerance": (
                    degeneracy_ppm_tol
                    if degeneracy_ppm_tol is not None
                    else step3.get("degeneracy_ppm_tolerance", step3.get("mz_tolerance_ppm"))
                ),
                "degeneracy_rt_tolerance": (
                    degeneracy_rt_tol
                    if degeneracy_rt_tol is not None
                    else step3.get("degeneracy_rt_tolerance")
                ),
                "degeneracy_correlation_threshold": (
                    degeneracy_corr_threshold
                    if degeneracy_corr_threshold is not None
                    else step3.get("degeneracy_correlation_threshold", 0.8)
                ),
                "degeneracy_min_correlation_points": (
                    degeneracy_min_corr_points
                    if degeneracy_min_corr_points is not None
                    else step3.get("degeneracy_min_correlation_points", 3)
                ),
                "degeneracy_adduct_table_file": (
                    degeneracy_adduct_table_file
                    if degeneracy_adduct_table_file is not None
                    else step3.get("degeneracy_adduct_table_file")
                ),
            },
            "step4": {
                "signal_threshold": step4.get("signal_threshold"),
                "background_threshold": (
                    args.bg_threshold
                    if args.bg_threshold is not None
                    else step4.get("background_threshold")
                ),
                "high_det_thresh": (
                    args.high_det_thresh
                    if args.high_det_thresh is not None
                    else step4.get("high_det_thresh")
                ),
                "low_det_thresh": (
                    args.low_det_thresh
                    if args.low_det_thresh is not None
                    else step4.get("low_det_thresh")
                ),
                "intensity_fc_threshold": (
                    args.intensity_fc_threshold
                    if args.intensity_fc_threshold is not None
                    else step4.get("intensity_fc_threshold")
                ),
                "ratio_rescue_threshold": step4.get("ratio_rescue_threshold"),
                "qc_ratio_threshold": (
                    args.qc_ratio_threshold
                    if args.qc_ratio_threshold is not None
                    else step4.get("qc_ratio_threshold")
                ),
                "enable_background_threshold": step4.get("enable_background_threshold", True),
                "enable_qc_ratio_threshold": step4.get("enable_qc_ratio_threshold", True),
                "enable_intensity_fc_threshold": step4.get(
                    "enable_intensity_fc_threshold",
                    False,
                ),
                "enable_ratio_rescue": step4.get("enable_ratio_rescue", True),
            },
        }

    @staticmethod
    def from_gui_step_params(params_by_step: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        from ms_preprocessing.config import get_pipeline_profile

        profile = get_pipeline_profile("default")
        step3 = dict(profile["step3"])
        step4 = dict(profile["step4"])
        if len(params_by_step) > 2:
            step3.update(dict(params_by_step[2]))
        if len(params_by_step) > 3:
            step4.update(dict(params_by_step[3]))

        return {
            "step1": dict(params_by_step[0]) if len(params_by_step) > 0 else {},
            "step2": dict(params_by_step[1]) if len(params_by_step) > 1 else {},
            "step3": step3,
            "step4": step4,
        }


class WorkflowValidationService:
    """Collect shared workflow parameter validation warnings."""

    _STEP_LABELS = {
        "step1": "Step 1",
        "step2": "Step 2",
        "step4": "Step 4",
    }

    def collect(
        self,
        step: str,
        resolved: dict[str, dict[str, Any]],
    ) -> list[ValidationWarning]:
        warnings: list[ValidationWarning] = []
        if step in {"organize", "all"}:
            warnings.extend(validate_step1_params(resolved.get("step1", {})))
        if step in {"istd", "all"}:
            warnings.extend(validate_step2_params(resolved.get("step2", {})))
        if step in {"filter", "all"}:
            warnings.extend(validate_step4_params(resolved.get("step4", {})))
        return warnings

    def collect_prefixed(
        self,
        step: str,
        resolved: dict[str, dict[str, Any]],
    ) -> list[ValidationWarning]:
        warnings: list[ValidationWarning] = []
        for step_key, step_warning in self._collect_by_step(step, resolved):
            label = self._STEP_LABELS.get(step_key, step_key)
            warnings.append(
                ValidationWarning(
                    code=step_warning.code,
                    message=f"{label}: {step_warning.message}",
                    blocking=step_warning.blocking,
                )
            )
        return warnings

    def _collect_by_step(
        self,
        step: str,
        resolved: dict[str, dict[str, Any]],
    ) -> list[tuple[str, ValidationWarning]]:
        warnings: list[tuple[str, ValidationWarning]] = []
        if step in {"organize", "all"}:
            warnings.extend(
                ("step1", warning)
                for warning in validate_step1_params(resolved.get("step1", {}))
            )
        if step in {"istd", "all"}:
            warnings.extend(
                ("step2", warning)
                for warning in validate_step2_params(resolved.get("step2", {}))
            )
        if step in {"filter", "all"}:
            warnings.extend(
                ("step4", warning)
                for warning in validate_step4_params(resolved.get("step4", {}))
            )
        return warnings
