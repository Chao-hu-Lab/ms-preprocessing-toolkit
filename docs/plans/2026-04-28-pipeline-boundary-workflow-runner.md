# Workflow Runner Boundary Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Move CLI Step1-4 orchestration into shared workflow services that GUI can reuse later.

**Architecture:** Add top-level `workflow` services for input loading, step execution, and final export. `run_cli()` becomes a thin adapter around these services.

**Tech Stack:** Python, pandas, pytest, toolkit adapters, `PipelineSession`.

---

## Ownership

Can modify:

- `src/ms_preprocessing/workflow/__init__.py`
- `src/ms_preprocessing/workflow/input_loader.py`
- `src/ms_preprocessing/workflow/workflow_runner.py`
- `src/ms_preprocessing/workflow/export_service.py`
- `src/ms_preprocessing/main.py`
- `tests/test_workflow_runner.py`
- `tests/test_workflow_input_loader.py`
- `tests/test_workflow_export_service.py`
- `tests/test_cli_parquet_chain.py`

Do not modify:

- `src/ms_preprocessing/gui/event_handlers.py`
- `src/ms_preprocessing/gui/main_window.py`
- `ms-core/`
- submodule pointer
- `tests/testing_markers.py`
- `tests/test_testing_markers.py`

## Precondition

Start implementation after Step3 and Step4 core APIs are stable and the main agent has run focused adapter tests.

## Task 1: Input Loader

Step 1: Write failing tests in `tests/test_workflow_input_loader.py` if the loader needs enough behavior to justify its own tests. Otherwise keep it covered through workflow runner tests.

Required behavior:

- load main matrix through `FileHandler`
- preserve `SampleInfo` from Excel
- preserve `deleted_feature` from Excel
- update `PipelineSession` context from file metadata

Step 2: Implement `InputLoader`.

## Task 2: Workflow Runner

Step 1: Write failing tests in `tests/test_workflow_runner.py`.

Required tests:

- runs Step1-4 adapter order for `step="all"`
- runs one selected step
- validation warnings block before adapter calls
- Step3 and Step4 receive protected rows from session metadata
- optional parquet intermediate persistence writes to internal cache
- result metadata updates `PipelineSession`

Run:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\test_workflow_runner.py -v --tb=short
```

Expected RED:

- missing `ms_preprocessing.workflow.workflow_runner`.

Step 2: Implement `WorkflowRunner`.

Result contract:

```python
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
```

Contract rules:

- `data` is the latest in-memory dataframe after the final completed step, or
  `None` when validation fails before any adapter call.
- `completed_steps` uses the canonical adapter step names in execution order.
- `last_completed_step_index` uses GUI-compatible zero-based indices
  (`0=Step1`, `1=Step2`, `2=Step3`, `3=Step4`) and is `None` when no step
  completed.
- `step_results` stores the raw toolkit `ProcessingResult` for each completed
  step so GUI/CLI adapters can preserve current metadata behavior.
- `session` is the same `PipelineSession` instance passed into `run()` after
  metadata updates.
- `step_output_paths` mirrors `session.step_output_paths`; the runner owns
  intermediate persistence when `persist_intermediate=True`.
- `validation_warnings` contains blocking or user-confirmable validation
  messages collected before adapter execution.
- `final_export_ready` is true when the run reached Step4 or a selected step
  produced data that can be exported through `ExportService`.

Target interface:

```python
class WorkflowRunner:
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
        ...
```

## Task 3: Export Service

Step 1: Write failing tests in `tests/test_workflow_export_service.py`.

Required tests:

- default output naming for each CLI step
- suffix normalization to `.xlsx`
- `SampleInfo` extra sheet export
- optional `deleted_feature` extra sheet export
- no parquet cache for final xlsx export

Run:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\test_workflow_export_service.py -v --tb=short
```

Expected RED:

- missing `ms_preprocessing.workflow.export_service`.

Step 2: Implement `ExportService`.

Target interface:

```python
class ExportService:
    def export_final(
        self,
        data: pd.DataFrame,
        *,
        output_path: Path | None,
        input_path: Path,
        step: str,
        session: PipelineSession,
        export_deleted_feature: bool,
    ) -> Path:
        ...
```

## Task 4: Route CLI Through Services

Step 1: Refactor `run_cli()` to:

1. validate input args
2. resolve parameters
3. collect validation warnings
4. use `InputLoader`
5. use `WorkflowRunner`
6. use `ExportService`
7. print concise CLI progress and return exit code

Step 2: Verify:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\test_workflow_runner.py tests\test_workflow_export_service.py tests\test_cli_parquet_chain.py -v --tb=short
```

## Deliverable

Report:

- changed files
- new service interfaces
- CLI behavior intentionally preserved
- any GUI assumptions that the GUI controller subagent must know
