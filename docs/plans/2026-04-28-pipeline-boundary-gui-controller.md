# GUI Controller Boundary Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Move GUI Run All, async worker lifecycle, export, and combined TSV preprocessing out of `event_handlers.py` while preserving the current GUI workflow.

**Architecture:** `event_handlers.py` remains the event facade. New GUI/workflow services own pipeline control, async scheduling, export delegation, and combined TSV preprocessing.

**Tech Stack:** Python, pytest, pandas, CustomTkinter, toolkit workflow services.

---

## Ownership

Can modify:

- `src/ms_preprocessing/gui/pipeline_controller.py`
- `src/ms_preprocessing/gui/async_task_runner.py`
- `src/ms_preprocessing/workflow/combined_tsv_service.py`
- `src/ms_preprocessing/gui/event_handlers.py`
- `tests/test_gui_pipeline_controller.py`
- `tests/test_gui_async_task_runner.py`
- `tests/test_combined_tsv_service.py`
- focused parts of `tests/test_gui_event_handlers.py`

Do not modify:

- `ms-core/`
- CLI workflow logic in `src/ms_preprocessing/main.py`
- workflow runner contracts unless approved by main agent
- submodule pointer

## Precondition

Start implementation after `WorkflowRunner` and `ExportService` interfaces are stable.

## Task 1: Pipeline Controller

Step 1: Write failing tests in `tests/test_gui_pipeline_controller.py`.

Required tests:

- Run All prepares a clean session from loaded source
- validation warnings block before processing
- success updates current data, completed steps, step output paths, and summaries
- failure path reports error and clears busy state
- final export delegates to `ExportService`

Run:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\test_gui_pipeline_controller.py -v --tb=short
```

Expected RED:

- missing `ms_preprocessing.gui.pipeline_controller`.

Step 2: Implement `PipelineController`.

Target responsibility:

- collect widget parameters
- call workflow runner
- update GUI state through callbacks
- keep UI wording in event handlers or existing summary helpers

## Task 2: Async Task Runner

Step 1: Write failing tests in `tests/test_gui_async_task_runner.py`.

Required tests:

- schedules worker thread when UI callback scheduling is available
- supports direct execution fallback
- drains UI queue on UI thread
- prevents concurrent tasks
- clears busy state after failure

Run:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\test_gui_async_task_runner.py -v --tb=short
```

Expected RED:

- missing `ms_preprocessing.gui.async_task_runner`.

Step 2: Implement `AsyncTaskRunner`.

## Task 3: Combined TSV Service

Step 1: Write failing tests in `tests/test_combined_tsv_service.py`.

Required tests:

- output path is generated under `OUTPUT/combined_fix`
- adapter call receives combined TSV path and method file
- result is saved with `save_parquet_cache=False`
- generated file path is returned for Step1 loading

Run:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\test_combined_tsv_service.py -v --tb=short
```

Expected RED:

- missing `ms_preprocessing.workflow.combined_tsv_service`.

Step 2: Implement `CombinedTsvService`.

Target interface:

```python
class CombinedTsvService:
    def create_combined_fix(
        self,
        *,
        raw_path: Path,
        method_file: Path | None,
        output_dir: Path,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> Path:
        ...
```

## Task 4: Thin Event Handler Facade

Step 1: Refactor `event_handlers.py` so these methods delegate:

- `_run_all_steps()`
- `_run_all_steps_worker()`
- `_finish_run_all_steps()`
- `_export_results()`
- `_materialize_final_xlsx_from_latest_step()`
- `_schedule_step_output_save()`
- `_run_combined_tsv_preprocessor()`

Step 2: Keep method names stable for existing widgets/tests.

Step 3: Verify:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\test_gui_pipeline_controller.py tests\test_gui_async_task_runner.py tests\test_combined_tsv_service.py tests\test_gui_event_handlers.py tests\test_gui_main_window_sidebar_labels.py -v --tb=short
```

## Deliverable

Report:

- changed files
- event handler methods that are now wrappers
- GUI tests run
- any user-visible copy that changed, or explicitly state none changed
