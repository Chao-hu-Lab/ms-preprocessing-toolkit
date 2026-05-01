"""Tests for shared workflow runner orchestration."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult
from ms_preprocessing.workflow.pipeline_session import PipelineSession
from ms_preprocessing.workflow.workflow_runner import WorkflowRunner


def _frame(label: str) -> pd.DataFrame:
    return pd.DataFrame({"stage": [label], "value": [1]})


def _ok(step: str, data: pd.DataFrame, metadata: ProcessingMetadata | None = None) -> ProcessingResult:
    return ProcessingResult(
        success=True,
        step=step,
        output_path=None,
        data=data.copy(),
        metadata=metadata or ProcessingMetadata(),
    )


def _params(base: Path | None = None) -> dict[str, dict]:
    xic_results_file: str | Path = "xic_results.xlsx"
    if base is not None:
        xic_results_path = base / "xic_results.xlsx"
        xic_results_path.write_text("placeholder", encoding="utf-8")
        xic_results_file = xic_results_path

    return {
        "step1": {"method_file": None},
        "step2": {"xic_results_file": xic_results_file},
        "step3": {"mz_tolerance_ppm": 20.0, "rt_tolerance": 0.1},
        "step4": {"high_det_thresh": 0.8, "low_det_thresh": 0.2},
    }


def test_workflow_layer_does_not_import_gui_pipeline_session() -> None:
    workflow_root = Path("src/ms_preprocessing/workflow")
    offenders = [
        path
        for path in workflow_root.glob("*.py")
        if "ms_preprocessing.gui.pipeline_session" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_workflow_runner_runs_all_steps_in_adapter_order(monkeypatch, project_temp_dir) -> None:
    calls: list[str] = []
    inputs: list[str] = []

    def _make_runner(step_name: str):
        def _run(data, **kwargs):
            _ = kwargs
            calls.append(step_name)
            inputs.append(str(data["stage"].iloc[0]))
            return _ok(step_name, _frame(step_name))

        return _run

    import ms_preprocessing.workflow.workflow_runner as runner_module

    monkeypatch.setattr(runner_module._adapter_do, "run_from_df", _make_runner("data_organizer"))
    monkeypatch.setattr(runner_module._adapter_istd, "run_from_df", _make_runner("istd_marker"))
    monkeypatch.setattr(runner_module._adapter_dr, "run_from_df", _make_runner("duplicate_remover"))
    monkeypatch.setattr(runner_module._adapter_ff, "run_from_df", _make_runner("feature_filter"))

    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        session = PipelineSession(output_dir=base, source_file=base / "input.xlsx")
        result = WorkflowRunner().run(_frame("input"), step="all", resolved_parameters=_params(base), session=session)

    assert result.success is True
    assert calls == ["data_organizer", "istd_marker", "duplicate_remover", "feature_filter"]
    assert inputs == ["input", "data_organizer", "istd_marker", "duplicate_remover"]
    assert result.completed_steps == calls
    assert result.last_completed_step_index == 3
    assert result.final_export_ready is True
    assert result.step_results["feature_filter"].step == "feature_filter"
    assert result.session is session


def test_workflow_runner_runs_one_selected_step(monkeypatch, project_temp_dir) -> None:
    calls: list[str] = []

    import ms_preprocessing.workflow.workflow_runner as runner_module

    monkeypatch.setattr(
        runner_module._adapter_dr,
        "run_from_df",
        lambda data, **kwargs: (calls.append("duplicate_remover"), _ok("duplicate_remover", _frame("step3")))[1],
    )

    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        session = PipelineSession(output_dir=base, source_file=base / "input.xlsx")
        result = WorkflowRunner().run(
            _frame("input"),
            step="duplicate-removal",
            resolved_parameters=_params(base),
            session=session,
        )

    assert calls == ["duplicate_remover"]
    assert result.completed_steps == ["duplicate_remover"]
    assert result.last_completed_step_index == 2
    assert result.final_export_ready is True


def test_workflow_runner_blocks_on_validation_warnings_before_adapter_calls(monkeypatch, project_temp_dir) -> None:
    import ms_preprocessing.workflow.workflow_runner as runner_module

    called = False

    def _unexpected(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("adapter should not be called")

    monkeypatch.setattr(runner_module._adapter_istd, "run_from_df", _unexpected)

    params = _params()
    params["step2"] = {"xic_results_file": None}

    with project_temp_dir() as temp_dir:
        session = PipelineSession(output_dir=Path(temp_dir), source_file=Path(temp_dir) / "input.xlsx")
        result = WorkflowRunner().run(_frame("input"), step="istd", resolved_parameters=params, session=session)

    assert called is False
    assert result.success is False
    assert result.data is None
    assert result.completed_steps == []
    assert result.last_completed_step_index is None
    assert result.validation_warnings
    assert "requires an XIC Extractor results workbook" in result.message


def test_workflow_runner_returns_no_data_when_first_adapter_fails(monkeypatch, project_temp_dir) -> None:
    import ms_preprocessing.workflow.workflow_runner as runner_module

    monkeypatch.setattr(
        runner_module._adapter_do,
        "run_from_df",
        lambda data, **kwargs: ProcessingResult(
            success=False,
            step="data_organizer",
            output_path=None,
            data=None,
            metadata=ProcessingMetadata(),
            error="boom",
        ),
    )

    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        session = PipelineSession(output_dir=base, source_file=base / "input.xlsx")
        result = WorkflowRunner().run(_frame("input"), step="organize", resolved_parameters=_params(base), session=session)

    assert result.success is False
    assert result.data is None
    assert result.completed_steps == []
    assert result.last_completed_step_index is None
    assert result.errors == ["boom"]


def test_workflow_runner_rejects_unknown_step(project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        session = PipelineSession(output_dir=base, source_file=base / "input.xlsx")
        result = WorkflowRunner().run(
            _frame("input"),
            step="data_organizer",
            resolved_parameters=_params(base),
            session=session,
        )

    assert result.success is False
    assert result.data is None
    assert result.completed_steps == []
    assert result.last_completed_step_index is None
    assert result.errors == ["Unknown workflow step: data_organizer"]


def test_workflow_runner_passes_protected_rows_to_steps_three_and_four(monkeypatch, project_temp_dir) -> None:
    captured: dict[str, set[int]] = {}

    import ms_preprocessing.workflow.workflow_runner as runner_module

    monkeypatch.setattr(runner_module._adapter_do, "run_from_df", lambda data, **kwargs: _ok("data_organizer", data))
    monkeypatch.setattr(
        runner_module._adapter_istd,
        "run_from_df",
        lambda data, **kwargs: _ok(
            "istd_marker",
            data,
            ProcessingMetadata(red_font_rows={1, 3}, protected_rows={1, 3}),
        ),
    )
    monkeypatch.setattr(
        runner_module._adapter_dr,
        "run_from_df",
        lambda data, **kwargs: (
            captured.setdefault("step3", kwargs["protected_rows"]),
            _ok(
                "duplicate_remover",
                data,
                ProcessingMetadata(red_font_rows={1, 3}, protected_rows={1, 3}),
            ),
        )[1],
    )
    monkeypatch.setattr(
        runner_module._adapter_ff,
        "run_from_df",
        lambda data, **kwargs: (
            captured.setdefault("step4", kwargs["protected_rows"]),
            _ok("feature_filter", data),
        )[1],
    )

    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        session = PipelineSession(output_dir=base, source_file=base / "input.xlsx")
        session.update_context_from_metadata({"protected_rows": [1, 3]})
        WorkflowRunner().run(_frame("input"), step="all", resolved_parameters=_params(base), session=session)

    assert captured == {"step3": {1, 3}, "step4": {1, 3}}


def test_workflow_runner_uses_remapped_protected_rows_after_step_three(
    monkeypatch,
    project_temp_dir,
) -> None:
    captured: dict[str, set[int]] = {}

    import ms_preprocessing.workflow.workflow_runner as runner_module

    monkeypatch.setattr(runner_module._adapter_do, "run_from_df", lambda data, **kwargs: _ok("data_organizer", data))
    monkeypatch.setattr(
        runner_module._adapter_istd,
        "run_from_df",
        lambda data, **kwargs: _ok(
            "istd_marker",
            data,
            ProcessingMetadata(red_font_rows={8, 44}, protected_rows={8, 44}),
        ),
    )
    monkeypatch.setattr(
        runner_module._adapter_dr,
        "run_from_df",
        lambda data, **kwargs: (
            captured.setdefault("step3", kwargs["protected_rows"]),
            _ok(
                "duplicate_remover",
                data,
                ProcessingMetadata(red_font_rows={2}, protected_rows={2}),
            ),
        )[1],
    )
    monkeypatch.setattr(
        runner_module._adapter_ff,
        "run_from_df",
        lambda data, **kwargs: (
            captured.setdefault("step4", kwargs["protected_rows"]),
            _ok(
                "feature_filter",
                data,
                ProcessingMetadata(red_font_rows={1}, protected_rows={1}),
            ),
        )[1],
    )

    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        session = PipelineSession(output_dir=base, source_file=base / "input.xlsx")
        WorkflowRunner().run(_frame("input"), step="all", resolved_parameters=_params(base), session=session)

    assert captured == {"step3": {8, 44}, "step4": {2}}
    assert session.metadata.red_font_rows == {1}
    assert session.metadata.protected_rows == {1}


def test_workflow_runner_does_not_persist_progress_callback_in_step_parameters(
    monkeypatch,
    project_temp_dir,
) -> None:
    captured_kwargs: dict[str, object] = {}
    progress_events: list[tuple[int, str]] = []

    import ms_preprocessing.workflow.workflow_runner as runner_module

    def _run(data, **kwargs):
        captured_kwargs.update(kwargs)
        kwargs["progress_callback"](50, "halfway")
        return _ok("data_organizer", data)

    monkeypatch.setattr(runner_module._adapter_do, "run_from_df", _run)

    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        session = PipelineSession(output_dir=base, source_file=base / "input.xlsx")
        WorkflowRunner().run(
            _frame("input"),
            step="organize",
            resolved_parameters=_params(base),
            session=session,
            progress_callback=lambda step_index, message: progress_events.append(
                (step_index, message)
            ),
        )

    assert "progress_callback" in captured_kwargs
    assert "progress_callback" not in session.step_parameters[0]
    assert progress_events == [(0, "Step 1: Data Organization"), (0, "halfway")]


def test_workflow_runner_persists_optional_intermediates_to_session_cache(
    monkeypatch,
    project_temp_dir,
) -> None:
    import ms_preprocessing.workflow.workflow_runner as runner_module

    monkeypatch.setattr(runner_module._adapter_do, "run_from_df", lambda data, **kwargs: _ok("data_organizer", data))

    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        session = PipelineSession(
            output_dir=base / "out",
            source_file=base / "input.xlsx",
            intermediate_dir=base / "cache",
        )
        result = WorkflowRunner().run(
            _frame("input"),
            step="organize",
            resolved_parameters=_params(base),
            session=session,
            persist_intermediate=True,
        )

    assert result.step_output_paths[0].suffix == ".parquet"
    assert result.step_output_paths[0].parent == session.intermediate_dir
    assert 0 in session.step_output_paths


def test_workflow_runner_updates_result_metadata_into_session(monkeypatch, project_temp_dir) -> None:
    sample_info = pd.DataFrame({"Sample_Name": ["S1"]})
    metadata = ProcessingMetadata(red_font_rows={4}, protected_rows={4}, sample_info=sample_info)

    import ms_preprocessing.workflow.workflow_runner as runner_module

    monkeypatch.setattr(
        runner_module._adapter_do,
        "run_from_df",
        lambda data, **kwargs: _ok("data_organizer", data, metadata=metadata),
    )

    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        session = PipelineSession(output_dir=base, source_file=base / "input.xlsx")
        result = WorkflowRunner().run(_frame("input"), step="organize", resolved_parameters=_params(base), session=session)

    assert result.success is True
    assert session.metadata.red_font_rows == {4}
    assert session.metadata.protected_rows == {4}
    assert session.metadata.sample_info is sample_info
    assert "data_organizer" in session.completed_steps
