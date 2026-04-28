# Pipeline Boundary Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Split overloaded Step3, Step4, GUI, and CLI responsibilities into explicit internal modules while preserving the current four-step user workflow.

**Architecture:** Use one umbrella workstream rather than many small feature branches. `ms-core` keeps scientific processing boundaries, while the top-level toolkit owns GUI/CLI orchestration and export boundaries. Existing public classes such as `DuplicateRemover`, `FeatureFilter`, GUI event handler methods, and `run_cli()` remain compatibility facades during migration.

**Tech Stack:** Python, pandas, numpy, pytest, CustomTkinter, git submodule workflow for `ms-core`.

---

## Goal

Make the pipeline easier to change by aligning module boundaries with real responsibilities:

- Step3 should orchestrate duplicate grouping and merging, not own degeneracy annotation internals.
- Step4 should orchestrate feature filtering, not own every gate calculation and output-shaping detail.
- GUI event handlers should handle UI events, not own file IO, workflow execution, async scheduling, and exports.
- CLI should call the same workflow runner as GUI instead of duplicating the pipeline sequence.

## Context

The previous Step1 work proved the right pattern:

- Keep the user-facing step broad.
- Split internal responsibilities into narrow modules.
- Keep old entrypoints as wrappers until adapters, GUI, and CLI are migrated.
- Protect behavior with focused tests before moving logic.

This plan applies that pattern to Step3, Step4, GUI, and CLI in one larger workstream. The intent is not to change workflow behavior or scientific rules. The intent is to make each responsibility independently testable.

## Constraints

- Do not develop on `master`.
- Use one umbrella branch pair after the current Phase 4 branch lands:
  - `ms-core`: `feature/pipeline-boundary-refactor`
  - toolkit: `feature/pipeline-boundary-refactor`
- Because `ms-core` is a submodule, there will still be two PRs. Avoid creating separate branches per phase unless a blocker forces it.
- Commit in checkpoints, but keep the work on the same branch pair.
- Land order remains strict: `ms-core` PR first, toolkit pointer PR last.
- Preserve current public behavior for GUI, CLI, adapters, and generated output names.
- Avoid changing scientific thresholds or formulas while extracting modules.

## Done When

- Step3 degeneracy annotation, adduct loading, Pearson correlation, and intensity merge policy have focused module tests.
- Step4 group detection, ratio calculation, gate decision, zero-to-NaN cleanup, marker column insertion, and deleted-feature output are independently testable.
- GUI Run All uses a controller/service layer instead of embedding the workflow loop in `event_handlers.py`.
- CLI uses the same workflow runner as GUI for Step1-4 orchestration.
- `event_handlers.py`, `main.py`, `duplicate_remover.py`, and `ms_quality_filter.py` are meaningfully smaller and mostly orchestration/facade code.
- Focused core, adapter, CLI, GUI, and smoke tests pass.

---

## Workstream Shape

Use one umbrella worktree after Phase 4 is merged:

```powershell
git fetch origin
git pull --ff-only origin master
git worktree add ".worktrees\pipeline-boundary-refactor" -b feature/pipeline-boundary-refactor
Push-Location ".worktrees\pipeline-boundary-refactor"
git submodule update --init --recursive
Push-Location ms-core
git fetch origin
git checkout -b feature/pipeline-boundary-refactor origin/master
Pop-Location
```

If this starts before Phase 4 is merged, base the umbrella branch on `feature/step1-combined-tsv-preprocessor` and document the dependency in both PRs.

Checkpoint commit order:

1. `ms-core`: Step3 degeneracy annotation extraction.
2. `ms-core`: Step3 duplicate intensity merge extraction.
3. `ms-core`: Step4 decision table and output postprocessor extraction.
4. toolkit: shared workflow runner adopted by CLI.
5. toolkit: GUI controller/services adopted by event handlers.
6. toolkit: docs, skill references, and submodule pointer commit.

---

## Proposed Boundaries

### Step3 Core Boundaries

Keep:

- `ms_core.preprocessing.duplicate_remover.DuplicateRemover`
  - public `process()`
  - validation
  - high-level progress
  - duplicate grouping orchestration
  - compatibility wrappers for private helpers during migration

Extract:

- `ms_core.preprocessing.degeneracy_annotation`
  - `DegeneracyAnnotator`
  - `AdductTableLoader`
  - default adduct table
  - Pearson correlation selection/calculation
  - adduct match ranking
- `ms_core.preprocessing.duplicate_intensity_merge`
  - `MergeMode`
  - positive-value coercion
  - `DuplicateIntensityMerger`
  - merge stats
- Optional only if the file remains too large after those two:
  - `ms_core.preprocessing.duplicate_grouping`
  - RT-window duplicate grouping and representative selection

Protected rows should remain part of duplicate representative selection. They are not annotation logic.

### Step4 Core Boundaries

Keep:

- `ms_core.preprocessing.ms_quality_filter.FeatureFilter`
  - public `process()`
  - validation
  - progress updates
  - result metadata assembly
  - compatibility wrappers for private helpers during migration

Extract:

- `ms_core.preprocessing.feature_groups`
  - sample type row parsing
  - group/QC/excluded column detection
  - group summary
- `ms_core.preprocessing.detection_ratios`
  - numeric block construction
  - group ratio columns
  - QC ratio column
- `ms_core.preprocessing.feature_filter_decisions`
  - `FeatureFilterThresholds`
  - `FeatureFilterOptions`
  - Wilson lower bound
  - stable/MNAR/QC/intensity FC masks
  - keep/delete decision table
  - stats calculation
- `ms_core.preprocessing.feature_filter_output`
  - zero-to-NaN cleanup
  - deleted feature collection shape
  - `is_Presence_Absence_Marker` column insertion
  - protected row remapping

### Toolkit Workflow Boundaries

Create:

- `src/ms_preprocessing/workflow/input_loader.py`
  - load main matrix
  - preserve `SampleInfo`
  - preserve `deleted_feature`
  - normalize load metadata into `PipelineSession`
- `src/ms_preprocessing/workflow/workflow_runner.py`
  - Step1-4 sequence
  - profile parameters
  - validation warnings
  - protected row forwarding
  - adapter invocation
  - step metadata updates
  - optional intermediate persistence hook
- `src/ms_preprocessing/workflow/export_service.py`
  - final output naming
  - extra sheet assembly
  - xlsx/parquet save decisions
  - downstream handoff metadata
- `src/ms_preprocessing/gui/pipeline_controller.py`
  - GUI Run All preparation
  - GUI callback adaptation
  - current step/data/session state updates
- `src/ms_preprocessing/gui/async_task_runner.py`
  - worker thread lifecycle
  - UI queue dispatch
  - busy-state guardrails

Keep:

- `src/ms_preprocessing/gui/event_handlers.py`
  - event methods used by widgets/buttons
  - thin delegation to controller/services
  - logging and user-visible error display
- `src/ms_preprocessing/main.py`
  - argument parser
  - `main()`
  - thin `run_cli()` wrapper around the shared workflow runner

---

## Task 1: Step3 Degeneracy Annotation Boundary

**Files:**
- Create: `ms-core/src/ms_core/preprocessing/degeneracy_annotation.py`
- Create: `ms-core/tests/test_degeneracy_annotation.py`
- Modify: `ms-core/src/ms_core/preprocessing/duplicate_remover.py`
- Keep: `tests/core/test_duplicate_remover.py`

**Step 1: Write failing module tests**

Create tests that call `DegeneracyAnnotator` directly:

- annotates `[M+Na]+` adduct and base rows
- rejects low-correlation candidate pairs
- returns empty stats for empty input
- loads custom adduct table with `To` and `Delta_Da`
- falls back to built-in table when custom table is missing or invalid

Run:

```powershell
Push-Location ms-core
python -m pytest tests\test_degeneracy_annotation.py -v --tb=short
Pop-Location
```

Expected before implementation:

- FAIL with `ModuleNotFoundError: No module named 'ms_core.preprocessing.degeneracy_annotation'`

**Step 2: Implement minimal module**

Move these methods from `DuplicateRemover` into the new module:

- `_annotate_degeneracy`
- `_select_degeneracy_correlation_columns`
- `_compute_feature_correlation`
- `_find_best_adduct_match`
- `_load_adduct_table`
- `_create_default_adduct_table`

Target interface:

```python
class DegeneracyAnnotator:
    def annotate(
        self,
        df: pd.DataFrame,
        *,
        col_info: dict[str, object],
        sample_type_row: pd.Series,
        ppm_tolerance: float,
        rt_tolerance: float,
        correlation_threshold: float,
        min_correlation_points: int,
        adduct_table_file: str | None,
    ) -> tuple[pd.DataFrame, dict[str, object], str]:
        ...
```

`DuplicateRemover._annotate_degeneracy()` should become a compatibility wrapper that delegates to `DegeneracyAnnotator`.

**Step 3: Verify Step3 compatibility**

Run:

```powershell
Push-Location ms-core
python -m pytest tests\test_degeneracy_annotation.py tests\test_pipeline.py -v --tb=short
Pop-Location
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\core\test_duplicate_remover.py tests\adapters\test_adapter_duplicate_remover.py -v --tb=short
```

**Step 4: Commit checkpoint**

```powershell
Push-Location ms-core
git add src/ms_core/preprocessing/degeneracy_annotation.py src/ms_core/preprocessing/duplicate_remover.py tests/test_degeneracy_annotation.py
git commit -m "refactor: extract degeneracy annotation"
Pop-Location
```

---

## Task 2: Step3 Intensity Merge Policy Boundary

**Files:**
- Create: `ms-core/src/ms_core/preprocessing/duplicate_intensity_merge.py`
- Create: `ms-core/tests/test_duplicate_intensity_merge.py`
- Modify: `ms-core/src/ms_core/preprocessing/duplicate_remover.py`
- Modify if needed: `ms-core/src/ms_core/preprocessing/settings.py`

**Step 1: Write failing tests**

Cover:

- `per_sample_max` upgrades overlapping donor values
- `fill_gaps` preserves legacy overlap values
- zeros and blanks are treated as missing
- merge stats report `groups_merged`, `data_points_recovered`, `data_points_upgraded`
- protected rows do not freeze representative intensities

Run:

```powershell
Push-Location ms-core
python -m pytest tests\test_duplicate_intensity_merge.py -v --tb=short
Pop-Location
```

Expected before implementation:

- FAIL with missing module/class.

**Step 2: Extract merger**

Move:

- `MergeMode` if currently local to `duplicate_remover.py`
- `_normalize_merge_mode`
- `_coerce_positive_number`
- `_merge_duplicate_groups`

Target interface:

```python
class DuplicateIntensityMerger:
    def merge(
        self,
        df: pd.DataFrame,
        merge_groups: list[list[int]],
        intensity_cols: list[str],
        merge_mode: MergeMode,
    ) -> tuple[pd.DataFrame, dict[str, int]]:
        ...
```

Keep `DuplicateRemover._merge_duplicate_groups()` as a wrapper during migration.

**Step 3: Verify**

Run:

```powershell
Push-Location ms-core
python -m pytest tests\test_duplicate_intensity_merge.py tests\test_pipeline.py -v --tb=short
Pop-Location
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\core\test_duplicate_remover.py tests\adapters\test_adapter_duplicate_remover.py -v --tb=short
```

**Step 4: Commit checkpoint**

```powershell
Push-Location ms-core
git add src/ms_core/preprocessing/duplicate_intensity_merge.py src/ms_core/preprocessing/duplicate_remover.py tests/test_duplicate_intensity_merge.py
git commit -m "refactor: extract duplicate intensity merge policy"
Pop-Location
```

---

## Task 3: Step4 Group And Ratio Boundaries

**Files:**
- Create: `ms-core/src/ms_core/preprocessing/feature_groups.py`
- Create: `ms-core/src/ms_core/preprocessing/detection_ratios.py`
- Create: `ms-core/tests/test_feature_groups.py`
- Create: `ms-core/tests/test_detection_ratios.py`
- Modify: `ms-core/src/ms_core/preprocessing/ms_quality_filter.py`

**Step 1: Write failing tests**

Cover:

- group/QC/excluded detection from `Sample_Type` row
- `count_analysis_groups()` compatibility
- group ratio column creation
- QC ratio column creation
- numeric block reuse shape and column-position mapping

Run:

```powershell
Push-Location ms-core
python -m pytest tests\test_feature_groups.py tests\test_detection_ratios.py -v --tb=short
Pop-Location
```

Expected before implementation:

- FAIL with missing modules.

**Step 2: Extract modules**

Target interfaces:

```python
class FeatureGroupDetector:
    def detect(self, df: pd.DataFrame) -> dict[str, object]:
        ...

class DetectionRatioCalculator:
    def calculate(
        self,
        df: pd.DataFrame,
        group_info: dict[str, object],
    ) -> tuple[pd.DataFrame, dict[str, str], dict[str, object]]:
        ...
```

Keep `FeatureFilter._detect_sample_types()` and `_calculate_ratios()` as wrappers.

**Step 3: Verify**

Run:

```powershell
Push-Location ms-core
python -m pytest tests\test_feature_groups.py tests\test_detection_ratios.py tests\test_feature_filter_small_n.py -v --tb=short
Pop-Location
```

**Step 4: Commit checkpoint**

```powershell
Push-Location ms-core
git add src/ms_core/preprocessing/feature_groups.py src/ms_core/preprocessing/detection_ratios.py src/ms_core/preprocessing/ms_quality_filter.py tests/test_feature_groups.py tests/test_detection_ratios.py
git commit -m "refactor: extract feature group and ratio helpers"
Pop-Location
```

---

## Task 4: Step4 Decision Table And Output Boundary

**Files:**
- Create: `ms-core/src/ms_core/preprocessing/feature_filter_decisions.py`
- Create: `ms-core/src/ms_core/preprocessing/feature_filter_output.py`
- Create: `ms-core/tests/test_feature_filter_decisions.py`
- Create: `ms-core/tests/test_feature_filter_output.py`
- Modify: `ms-core/src/ms_core/preprocessing/ms_quality_filter.py`

**Step 1: Write failing decision tests**

Cover:

- Wilson lower bound for small-N groups
- stable gate
- MNAR high/low gate
- QC zero and QC low forced-delete gate
- intensity fold-change gate
- protected row override
- unique contribution stats

Target interface:

```python
@dataclass(frozen=True)
class FeatureFilterThresholds:
    background: float
    high_det: float
    low_det: float
    qc_ratio: float
    intensity_fc: float

@dataclass(frozen=True)
class FeatureFilterOptions:
    enable_background: bool
    enable_qc_ratio: bool
    enable_intensity_fc: bool
    enable_mnar: bool
    allow_single_group_stable: bool

class FeatureFilterDecisionTable:
    def decide(...) -> FeatureFilterDecisionResult:
        ...
```

Run:

```powershell
Push-Location ms-core
python -m pytest tests\test_feature_filter_decisions.py -v --tb=short
Pop-Location
```

Expected before implementation:

- FAIL with missing module/class.

**Step 2: Write failing output tests**

Cover:

- zero-to-NaN only touches sample/QC data columns after the Sample_Type row
- `is_Presence_Absence_Marker` column follows MNAR mask
- deleted feature rows preserve the expected shape
- protected row remapping is stable

Run:

```powershell
Push-Location ms-core
python -m pytest tests\test_feature_filter_output.py -v --tb=short
Pop-Location
```

Expected before implementation:

- FAIL with missing module/class.

**Step 3: Extract logic**

Move most of `_filter_features()` into:

- `FeatureFilterDecisionTable`
- `FeatureFilterOutputBuilder`

Keep `FeatureFilter._filter_features()` as a wrapper returning:

```python
tuple[pd.DataFrame, list[pd.Series], dict[str, object]]
```

**Step 4: Verify**

Run:

```powershell
Push-Location ms-core
python -m pytest tests\test_feature_filter_decisions.py tests\test_feature_filter_output.py tests\test_feature_filter_small_n.py tests\test_pipeline.py -v --tb=short
Pop-Location
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\core\test_feature_filter.py tests\adapters\test_adapter_feature_filter.py tests\test_feature_filter_widget.py tests\test_feature_filter_presets.py -v --tb=short
```

**Step 5: Commit checkpoint**

```powershell
Push-Location ms-core
git add src/ms_core/preprocessing/feature_filter_decisions.py src/ms_core/preprocessing/feature_filter_output.py src/ms_core/preprocessing/ms_quality_filter.py tests/test_feature_filter_decisions.py tests/test_feature_filter_output.py
git commit -m "refactor: extract feature filter decision table"
Pop-Location
```

---

## Task 5: Core Full Verification And Push

**Files:**
- No new files unless cleanup is needed.

**Step 1: Run full ms-core suite**

```powershell
Push-Location ms-core
python -m pytest tests\ -v --tb=short -x
Pop-Location
```

**Step 2: Run top-level adapter/core contract**

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest -m adapter -v --tb=short
```

**Step 3: Push ms-core first**

```powershell
Push-Location ms-core
git status --short --branch
git push -u origin feature/pipeline-boundary-refactor
Pop-Location
```

Do not create the top-level pointer commit until the core branch has been pushed.

---

## Task 6: Shared Workflow Runner For CLI First

**Files:**
- Create: `src/ms_preprocessing/workflow/__init__.py`
- Create: `src/ms_preprocessing/workflow/input_loader.py`
- Create: `src/ms_preprocessing/workflow/workflow_runner.py`
- Create: `src/ms_preprocessing/workflow/export_service.py`
- Create: `tests/test_workflow_runner.py`
- Create: `tests/test_workflow_export_service.py`
- Modify: `src/ms_preprocessing/main.py`
- Modify: `tests/test_cli_parquet_chain.py`

**Step 1: Write failing workflow runner tests**

Cover:

- Step1-4 adapter order for `step="all"`
- single-step execution
- validation warnings block before adapter calls
- Step3/Step4 protected rows forwarded from session metadata
- optional parquet intermediate persistence uses cache path, not output root
- result metadata updates `PipelineSession`

Run:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\test_workflow_runner.py -v --tb=short
```

Expected before implementation:

- FAIL with missing module.

**Step 2: Write failing export tests**

Cover:

- default output naming for `organize`, `istd`, `duplicate-removal`, `filter`, and `all`
- xlsx suffix normalization
- extra sheets include `SampleInfo`
- `deleted_feature` export is conditional
- no parquet cache is written for final xlsx export

Run:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\test_workflow_export_service.py -v --tb=short
```

Expected before implementation:

- FAIL with missing module.

**Step 3: Implement services**

Target interfaces:

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

`run_cli()` should become:

1. validate arguments
2. load input through `InputLoader`
3. resolve parameters
4. call `WorkflowRunner`
5. call `ExportService`
6. print summary and return exit code

**Step 4: Verify CLI**

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\test_workflow_runner.py tests\test_workflow_export_service.py tests\test_cli_parquet_chain.py -v --tb=short
```

**Step 5: Commit checkpoint**

```powershell
git add src/ms_preprocessing/workflow src/ms_preprocessing/main.py tests/test_workflow_runner.py tests/test_workflow_export_service.py tests/test_cli_parquet_chain.py
git commit -m "refactor: route cli through shared workflow runner"
```

---

## Task 7: GUI Controller And Export Service Adoption

**Files:**
- Create: `src/ms_preprocessing/gui/pipeline_controller.py`
- Create: `src/ms_preprocessing/gui/async_task_runner.py`
- Create: `tests/test_gui_pipeline_controller.py`
- Create: `tests/test_gui_async_task_runner.py`
- Modify: `src/ms_preprocessing/gui/event_handlers.py`
- Modify: `tests/test_gui_event_handlers.py`

**Step 1: Write failing controller tests**

Cover:

- Run All prepares clean session from loaded source
- validation warnings block before processing
- successful Step1-4 run updates current data, completed steps, latest summaries, and step output paths
- failure path restores busy state and reports error
- controller delegates final export to `ExportService`

Run:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\test_gui_pipeline_controller.py -v --tb=short
```

Expected before implementation:

- FAIL with missing module.

**Step 2: Write failing async tests**

Cover:

- schedules background worker only when UI callbacks can be scheduled
- drains UI queue on UI thread
- blocks concurrent Run All / load / export when busy
- always clears busy state on worker failure

Run:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\test_gui_async_task_runner.py -v --tb=short
```

Expected before implementation:

- FAIL with missing module.

**Step 3: Implement GUI controller**

`event_handlers.py` should keep public event methods but delegate:

- `_run_all_steps()` delegates to `PipelineController.run_all()`
- `_export_results()` delegates to `ExportService`
- `_materialize_final_xlsx_from_latest_step()` delegates to `ExportService`
- `_schedule_step_output_save()` delegates worker lifecycle to `AsyncTaskRunner`

Do not change visible workflow or labels in this task.

**Step 4: Verify GUI-focused tests**

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\test_gui_pipeline_controller.py tests\test_gui_async_task_runner.py tests\test_gui_event_handlers.py tests\test_gui_main_window_sidebar_labels.py -v --tb=short
```

**Step 5: Commit checkpoint**

```powershell
git add src/ms_preprocessing/gui/pipeline_controller.py src/ms_preprocessing/gui/async_task_runner.py src/ms_preprocessing/gui/event_handlers.py tests/test_gui_pipeline_controller.py tests/test_gui_async_task_runner.py tests/test_gui_event_handlers.py
git commit -m "refactor: split gui pipeline controller services"
```

---

## Task 8: Combined TSV GUI Service Boundary

**Files:**
- Create: `src/ms_preprocessing/workflow/combined_tsv_service.py`
- Create: `tests/test_combined_tsv_service.py`
- Modify: `src/ms_preprocessing/gui/event_handlers.py`
- Modify: `tests/test_gui_event_handlers.py`

**Step 1: Write failing tests**

Cover:

- output path generation under `OUTPUT/combined_fix`
- adapter call receives combined TSV and method file
- result is saved without parquet cache
- generated file is loaded into Step1
- method prefill still runs after load

Run:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\test_combined_tsv_service.py tests\test_gui_event_handlers.py::test_combined_preprocessor_saves_loads_and_prefills_method -v --tb=short
```

**Step 2: Implement service**

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

**Step 3: Commit checkpoint**

```powershell
git add src/ms_preprocessing/workflow/combined_tsv_service.py src/ms_preprocessing/gui/event_handlers.py tests/test_combined_tsv_service.py tests/test_gui_event_handlers.py
git commit -m "refactor: extract combined tsv gui service"
```

---

## Task 9: Final Verification And Landing Prep

**Step 1: Run core verification**

```powershell
Push-Location ms-core
python -m pytest tests\ -v --tb=short -x
Pop-Location
```

**Step 2: Run top-level verification**

Start narrow, then expand:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest -m smoke -v --tb=short
$env:PYTHONPATH='ms-core/src'
python -m pytest -m adapter -v --tb=short
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\test_cli_parquet_chain.py tests\test_workflow_runner.py tests\test_workflow_export_service.py -v --tb=short
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\test_gui_event_handlers.py tests\test_gui_pipeline_controller.py tests\test_gui_async_task_runner.py -v --tb=short
```

If GUI/shared workflow changes are large, run:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\ -v --tb=short -x
```

**Step 3: Run review checks**

```powershell
git diff --check
git -C ms-core diff --check
git status --short --branch
git -C ms-core status --short --branch
git diff --submodule
```

**Step 4: Push and open PRs**

```powershell
Push-Location ms-core
git push -u origin feature/pipeline-boundary-refactor
Pop-Location
git add ms-core
git commit -m "docs: track pipeline boundary refactor"
git push -u origin feature/pipeline-boundary-refactor
```

Open:

1. `ms-core` PR: Step3/Step4 boundary extraction.
2. toolkit PR: shared workflow runner, GUI/CLI service extraction, submodule pointer.

Before merging toolkit PR, run the submodule landing guard:

```powershell
$coreSha = git rev-parse HEAD:ms-core
Push-Location ms-core
git fetch origin
git merge-base --is-ancestor $coreSha origin/master
$isLanded = $LASTEXITCODE -eq 0
Pop-Location
if (-not $isLanded) { throw "Block merge: top-level ms-core pointer is not on ms-core origin/master" }
```

---

## Risk Register

| Risk | Where | Mitigation |
| --- | --- | --- |
| Large branch becomes hard to review | Whole workstream | Use checkpoint commits and draft PR review after each checkpoint. |
| Step3 annotation extraction changes output columns | `degeneracy_annotation.py` | Keep integration tests in `tests/core/test_duplicate_remover.py`; compare exact annotation columns. |
| Step4 decision table changes scientific gate behavior | `feature_filter_decisions.py` | Move tests first; keep `test_feature_filter_small_n.py` and `tests/core/test_feature_filter.py` green after each commit. |
| GUI async split causes stale UI updates | `async_task_runner.py` | Token/session checks stay in service; add failure and cancellation tests. |
| CLI and GUI diverge while runner is introduced | `workflow_runner.py` | CLI adopts runner first, GUI second; both share the same runner tests. |
| Submodule pointer lands too early | toolkit PR | Use `skills/submodule-update` landing guard before merge. |

---

## Review Gates

After each checkpoint:

- Check file ownership: no core logic in GUI/CLI services.
- Check compatibility wrappers: old methods still exist until all callers migrate.
- Check public output shape: `RawIntensity`, `SampleInfo`, `deleted_feature`, marker columns, red/blue row metadata.
- Check branch state: `ms-core` commit pushed before top-level pointer commit.

Final review target:

- `duplicate_remover.py` mainly orchestrates Step3.
- `ms_quality_filter.py` mainly orchestrates Step4.
- `event_handlers.py` mainly maps user events to controller/service calls.
- `main.py` mainly parses args and invokes CLI workflow service.

