# GUI PipelineController Slimming Implementation Plan

> Implement this plan task-by-task, validating behavior after each change.

**Goal:** Slim `PipelineController` and remaining `event_handlers.py` glue without changing current GUI behavior.

**Architecture:** Keep `event_handlers.py` as the stable GUI event facade. Split Run All, final export/materialization, autosave, and optional combined TSV UI orchestration into focused GUI controller/service modules that delegate to existing workflow services.

**Tech Stack:** Python, pandas, pytest, CustomTkinter host callbacks, toolkit workflow services.

---

## Ownership

Can modify:

- `src/ms_preprocessing/gui/pipeline_controller.py`
- `src/ms_preprocessing/gui/event_handlers.py`
- new focused GUI modules under `src/ms_preprocessing/gui/`, if they reduce `PipelineController` responsibility
- focused GUI tests for pipeline controller and event handler behavior

Allowed new modules:

- `src/ms_preprocessing/gui/run_all_controller.py`
- `src/ms_preprocessing/gui/final_export_controller.py`
- `src/ms_preprocessing/gui/step_output_autosave_service.py`
- `src/ms_preprocessing/gui/combined_tsv_controller.py`

Must not modify:

- `ms-core/`
- `src/ms_preprocessing/workflow/workflow_runner.py` or its result contract unless separately approved
- CLI behavior in `src/ms_preprocessing/main.py`
- submodule pointer
- user-visible copy unless the relevant GUI tests are updated

## Contract To Preserve

- Existing `event_handlers.py` method names remain available as compatibility wrappers.
- Run All still blocks raw combined TSV input until users generate `combined_fix`.
- WorkflowRunner fast path still syncs host state and widget-local state.
- Final export and parquet materialization still preserve deleted_feature sheets and `save_parquet_cache=False` behavior.
- Busy state, progress updates, log messages, step switching, and auto-export timing remain unchanged unless covered by updated tests.

## Implementation Sequence

### Task 1: Lock current controller behavior

Before extraction, ensure tests cover:

- Run All widget path and WorkflowRunner fast path
- validation warning block/cancel behavior
- raw combined TSV guard
- widget-local state sync after WorkflowRunner fast path
- final export and materialization
- autosave scheduling
- combined TSV preprocessing UI flow

Run:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\test_gui_pipeline_controller.py tests\test_gui_event_handlers.py -v --tb=short -x
```

### Task 2: Extract RunAllController

Move Run All orchestration from `PipelineController` into `RunAllController`:

- prepare source data and step parameters
- run validation warning flow through host callbacks
- choose widget path vs WorkflowRunner fast path
- apply WorkflowRunner result and sync widgets
- finish Run All and restore the original step

Leave `PipelineController.run_all_steps()`, `run_all_steps_worker()`, and `finish_run_all_steps()` as wrappers.

### Task 3: Extract FinalExportController

Move final export and materialization behavior:

- export current data through `ExportService`
- materialize latest parquet step output into final xlsx
- build export session view
- preserve downstream handoff reminder and run context summary updates

Leave `PipelineController.export_results()` and `materialize_final_xlsx_from_latest_step()` as wrappers.

Required regression tests:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\test_final_export_handoff.py tests\test_final_export_cache_policy.py -v --tb=short -x
```

### Task 4: Extract StepOutputAutosaveService

Move autosave scheduling out of `PipelineController`:

- build step output path from current `PipelineSession`
- capture formatting context
- create and track the worker thread
- preserve existing worker callback into `event_handlers.py`

Leave `PipelineController.schedule_step_output_save()` as a wrapper.

If `StepOutputAutosaveService` gets its own test file, include it in the focused GUI check and update top-level marker ownership in the same branch.

### Task 5: Extract CombinedTsvController if still valuable

After Tasks 2-4, evaluate remaining controller size. If combined TSV orchestration is still a major responsibility, move it into `CombinedTsvController`:

- read Step1 widget combined TSV paths
- validate file existence
- call `CombinedTsvService.create_combined_fix()`
- load generated file into Step1 and prefill normal method controls

Leave `PipelineController.run_combined_tsv_preprocessor()` as a wrapper.

## Verification

Focused GUI checks:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\test_gui_pipeline_controller.py tests\test_gui_event_handlers.py tests\test_gui_async_task_runner.py tests\test_final_export_handoff.py tests\test_final_export_cache_policy.py tests\test_combined_tsv_service.py -v --tb=short -x
```

Marker ownership:

- If no new test files are added, do not edit `tests/testing_markers.py`.
- If new top-level test files are added, update `tests/testing_markers.py` and `tests/test_testing_markers.py` in the same branch before handoff.

Broader shard before handoff:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest -m gui -v --tb=short
```

## Handoff

Report:

- new GUI modules created and their responsibilities
- `event_handlers.py` methods that remain wrappers
- tests run and results
- confirmation that `ms-core` and the submodule pointer were not changed
- any user-visible copy changes, or explicitly state none changed
