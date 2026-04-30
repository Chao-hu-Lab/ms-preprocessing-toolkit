"""Shared Step1-4 workflow orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from ms_preprocessing.adapters import data_organizer as _adapter_do
from ms_preprocessing.adapters import duplicate_remover as _adapter_dr
from ms_preprocessing.adapters import feature_filter as _adapter_ff
from ms_preprocessing.adapters import istd_marker as _adapter_istd
from ms_preprocessing.pipeline_validation import format_validation_warnings, has_blocking_warnings
from ms_preprocessing.utils.file_handler import FileHandler
from ms_preprocessing.utils.results import ProcessingResult
from ms_preprocessing.workflow.parameter_resolver import WorkflowValidationService
from ms_preprocessing.workflow.pipeline_session import PipelineSession


@dataclass(frozen=True)
class WorkflowRunResult:
    success: bool
    data: pd.DataFrame | None
    step: str
    completed_steps: list[str]
    last_completed_step_index: int | None
    step_results: dict[str, ProcessingResult]
    session: PipelineSession
    step_output_paths: dict[int, Path]
    validation_warnings: list[str]
    errors: list[str]
    message: str
    final_export_ready: bool


@dataclass(frozen=True)
class _StepSpec:
    cli_step: str
    param_key: str
    index: int
    label: str
    adapter_step: str
    needs_protected_rows: bool = False


class WorkflowRunner:
    """Run selected workflow adapters against an in-memory dataframe."""

    _STEPS = (
        _StepSpec("organize", "step1", 0, "Step 1: Data Organization", "data_organizer"),
        _StepSpec("istd", "step2", 1, "Step 2: ISTD Marking", "istd_marker"),
        _StepSpec(
            "duplicate-removal",
            "step3",
            2,
            "Step 3: Duplicate Removal",
            "duplicate_remover",
            True,
        ),
        _StepSpec("filter", "step4", 3, "Step 4: Feature Filtering", "feature_filter", True),
    )

    def __init__(self, file_handler: FileHandler | None = None) -> None:
        self._file_handler = file_handler or FileHandler()

    def run(
        self,
        data: pd.DataFrame,
        *,
        step: str,
        resolved_parameters: dict[str, dict],
        session: PipelineSession,
        persist_intermediate: bool = False,
        progress_callback: Callable[[int, str], None] | None = None,
        log_callback: Callable[[str], None] | None = None,
    ) -> WorkflowRunResult:
        steps_to_run = self._steps_for(step)
        if not steps_to_run:
            message = f"Unknown workflow step: {step}"
            return self._result(
                success=False,
                data=None,
                step=step,
                session=session,
                errors=[message],
                message=message,
            )

        validation_warnings = self._collect_validation_warnings(step, resolved_parameters)
        if validation_warnings and has_blocking_warnings(validation_warnings):
            message = format_validation_warnings(validation_warnings)
            return self._result(
                success=False,
                data=None,
                step=step,
                session=session,
                validation_warnings=[warning.message for warning in validation_warnings],
                errors=[message],
                message=message,
            )

        current = data
        completed_steps: list[str] = []
        step_results: dict[str, ProcessingResult] = {}
        last_index: int | None = None
        protected_rows = set(session.metadata.protected_rows)

        for spec in steps_to_run:
            self._restore_protected_rows(session, protected_rows)
            result = self._run_step(spec, current, resolved_parameters, session, progress_callback, log_callback)
            if not result.success:
                message = result.error or "Processing failed"
                return self._result(
                    False,
                    current if completed_steps else None,
                    step,
                    session,
                    completed_steps,
                    last_index,
                    step_results,
                    errors=[message],
                    message=message,
                )

            current = result.data if result.data is not None else current
            session.update_from_result(result)
            protected_rows |= set(session.metadata.protected_rows)
            self._restore_protected_rows(session, protected_rows)
            if persist_intermediate:
                session.save_step_output(spec.index, current, self._file_handler)
            completed_steps.append(spec.adapter_step)
            step_results[spec.adapter_step] = result
            last_index = spec.index

        message = "Done" if completed_steps else "No steps selected"
        return self._result(
            True,
            current,
            step,
            session,
            completed_steps,
            last_index,
            step_results,
            [warning.message for warning in validation_warnings],
            message=message,
            final_export_ready=bool(completed_steps and current is not None),
        )

    def _run_step(
        self,
        spec: _StepSpec,
        data: pd.DataFrame,
        resolved_parameters: dict[str, dict],
        session: PipelineSession,
        progress_callback: Callable[[int, str], None] | None,
        log_callback: Callable[[str], None] | None,
    ) -> ProcessingResult:
        if log_callback is not None:
            log_callback(f"{spec.label}...")
        if progress_callback is not None:
            progress_callback(spec.index, spec.label)

        recorded_params = self._step_params(spec, resolved_parameters, session)
        call_params = dict(recorded_params)
        if progress_callback is not None:
            call_params["progress_callback"] = lambda _pct, message: progress_callback(
                spec.index,
                str(message),
            )
        session.record_step_parameters(spec.index, recorded_params)
        return self._adapter_runner(spec)(data, **call_params)

    @staticmethod
    def _step_params(
        spec: _StepSpec,
        resolved_parameters: dict[str, dict],
        session: PipelineSession,
    ) -> dict[str, Any]:
        params = dict(resolved_parameters.get(spec.param_key, {}))
        if spec.param_key == "step2" and params.get("xic_results_file"):
            params["xic_results_file"] = Path(params["xic_results_file"])
        if spec.needs_protected_rows:
            params["protected_rows"] = set(session.metadata.protected_rows)
        return params

    @classmethod
    def _steps_for(cls, step: str) -> tuple[_StepSpec, ...]:
        if step == "all":
            return cls._STEPS
        return tuple(spec for spec in cls._STEPS if spec.cli_step == step)

    @staticmethod
    def _adapter_runner(spec: _StepSpec) -> Callable[..., ProcessingResult]:
        runners = {
            "data_organizer": _adapter_do.run_from_df,
            "istd_marker": _adapter_istd.run_from_df,
            "duplicate_remover": _adapter_dr.run_from_df,
            "feature_filter": _adapter_ff.run_from_df,
        }
        return runners[spec.adapter_step]

    @staticmethod
    def _restore_protected_rows(session: PipelineSession, protected_rows: set[int]) -> None:
        if protected_rows and not protected_rows.issubset(session.metadata.protected_rows):
            session.update_context_from_metadata({"protected_rows": protected_rows})

    @staticmethod
    def _collect_validation_warnings(step: str, resolved: dict[str, dict]) -> list:
        return WorkflowValidationService().collect(step, resolved)

    @staticmethod
    def _result(
        success: bool,
        data: pd.DataFrame | None,
        step: str,
        session: PipelineSession,
        completed_steps: list[str] | None = None,
        last_completed_step_index: int | None = None,
        step_results: dict[str, ProcessingResult] | None = None,
        validation_warnings: list[str] | None = None,
        errors: list[str] | None = None,
        message: str = "",
        final_export_ready: bool = False,
    ) -> WorkflowRunResult:
        return WorkflowRunResult(
            success=success,
            data=data,
            step=step,
            completed_steps=list(completed_steps or []),
            last_completed_step_index=last_completed_step_index,
            step_results=dict(step_results or {}),
            session=session,
            step_output_paths=dict(session.step_output_paths),
            validation_warnings=list(validation_warnings or []),
            errors=list(errors or []),
            message=message,
            final_export_ready=final_export_ready,
        )
