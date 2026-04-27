# GUI UX Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

## Review Status

This is the revised v2 plan after design review.

The main correction from v1 is that the GUI should not grow multiple disconnected summary surfaces. The implementation should add one compact **Run Context / Latest Result** surface, one shared result-summary formatter, and one validation path that is used by both single-step execution and Run All.

## Goal

Improve the existing GUI for expert users by making workflow state, applied parameters, outputs, and risky choices visible without turning the app into a guided consumer wizard.

## Context

- The current GUI already has the correct high-level four-step workflow.
- The target user is familiar with the data-processing flow, so guided onboarding is intentionally deferred.
- Step 4 parameter sweep UI is out of scope for now.
- Step 2 ISTD handling is expected to change later and must leave room for formats shared with other projects.
- A future Step 2 input format is represented by XIC Extractor workbooks such as `xic_results_20260427_1425.xlsx`.

## Constraints

- Keep the current CustomTkinter four-step workflow and sidebar layout.
- Do not change core scientific processing logic in `ms-core`.
- Do not implement new ISTD parser formats in this pass.
- Do not put future Step 2 schema-specific parsing in widgets, event handlers, or `PipelineSession`.
- Guardrails should prevent obvious mistakes, but expert users should keep control where the choice is scientifically intentional.

## Done When

- The GUI shows a concise current-run context and latest step result.
- Run All preset parameters are visible before execution.
- High-risk parameter mistakes warn consistently in single-step and Run All paths.
- Step 2 summary and metadata handling can accept future XIC-derived metadata without changing GUI layout.
- Focused GUI tests pass.

---

## Scope

### In Scope

- Expert-user GUI hardening.
- One compact Run Context / Latest Result panel.
- Human-readable per-step result summaries.
- Run All preset preview.
- Warning-level parameter guardrails.
- Step 2 metadata contract for future ISTD record formats.

### Out Of Scope

- Guided onboarding wizard.
- Productized beginner flow.
- Step 4 parameter sweep UI.
- New ISTD parser implementation.
- XIC Extractor workbook parser implementation.
- Core scientific logic changes in `ms-core`.

---

## Design Principles

1. Preserve the current four-step workflow.
2. Avoid adding new modes unless the user explicitly chooses one.
3. Prefer visible state over hidden behavior.
4. Use one summary surface instead of separate context/result panels.
5. Warnings should prevent obvious mistakes, but not remove expert controls.
6. `PipelineSession` should keep workflow state, not GUI display wording.
7. Step 2 UI and summary code must not assume the current ISTD record Excel schema is final.

---

## Future Step 2 ISTD/XIC Compatibility Contract

Step 2 will later need to accept more than the current ISTD record workbook. The supplied XIC Extractor workbook shape shows the useful future information:

- `Summary` sheet:
  - target-level `Target`, `Role`, `ISTD Pair`, detection count/rate, mean RT, paired area ratio, NL status counts, RT delta, confidence counts.
- `Targets` sheet:
  - target definitions such as `Label`, `Role`, `ISTD Pair`, m/z, RT window, NL settings, product m/z.
- `XIC Results` sheet:
  - sample/target-level `SampleName`, `Group`, `Target`, `Role`, `ISTD Pair`, RT, Area, NL, confidence, and reason.
- `Diagnostics` sheet:
  - sample/target issue records for warnings and review context.

This plan only reserves the presentation and metadata boundary. It does **not** implement XIC parsing yet.

### Reserved Step 2 Metadata Keys

Future Step 2 adapters should be able to populate these keys without changing GUI layout:

```python
{
    "istd_record_file": str | None,
    "istd_record_date": str | None,
    "istd_record_source": str | None,      # e.g. "current-record", "xic-extractor"
    "istd_record_format": str | None,      # e.g. "legacy-excel", "xic-workbook"
    "istd_record_summary": str | None,     # short human-readable source summary
    "istd_target_count": int | None,
    "istd_pair_count": int | None,
    "istd_sample_count": int | None,
    "istd_marked_count": int | None,
    "istd_duplicate_count": int | None,
    "istd_warning_count": int | None,
    "istd_confidence_summary": dict | None,
}
```

Rules:

- `step_summary.py` may display these fields.
- Widgets may collect parameters, but should not parse future workbook internals.
- `event_handlers.py` should pass metadata/statistics through without schema-specific branching.
- `PipelineSession` should store state needed by the workflow, not presentation-specific text.

---

## Task 1: Add Step Summary Formatter And Step 2 Metadata Contract

**Files:**

- Create: `src/ms_preprocessing/gui/step_summary.py`
- Test: `tests/test_gui_step_summary.py`

**Goal:** Convert raw adapter statistics and metadata into short user-facing summary lines.

This should not change processing behavior. It only formats available information.

### Step 1: Write failing formatter tests

Create `tests/test_gui_step_summary.py`.

Cover Step 1, Step 2, Step 3, and Step 4.

Step 2 tests must prove unknown or future-specific keys do not break formatting:

```python
def test_step2_summary_accepts_future_xic_metadata() -> None:
    lines = summarize_step_result(
        "istd_marker",
        statistics={},
        metadata={
            "istd_record_file": "xic_results.xlsx",
            "istd_record_date": "20260106",
            "istd_record_source": "xic-extractor",
            "istd_record_format": "xic-workbook",
            "istd_target_count": 14,
            "istd_pair_count": 7,
            "istd_warning_count": 12,
            "unexpected_future_key": "safe",
        },
    )

    assert any("Record: xic_results.xlsx" in line for line in lines)
    assert any("Date: 20260106" in line for line in lines)
    assert any("Source: xic-extractor" in line for line in lines)
    assert any("Targets: 14" in line for line in lines)
```

Expected: FAIL because `step_summary.py` does not exist yet.

### Step 2: Implement `summarize_step_result()`

Create:

```python
def summarize_step_result(
    step_name: str,
    statistics: dict | None,
    metadata: dict | None,
    parameters: dict | None = None,
) -> list[str]:
    ...
```

Suggested formatting:

- Step 1:
  - features / samples if available
  - SampleInfo created / not available
  - method file used / not selected
- Step 2:
  - ISTD record file selected / not selected
  - ISTD date
  - ISTD record source and format, if present
  - target/pair/sample counts, if available
  - marked count, if available
  - duplicate-of-ISTD count, if available
  - warning/confidence summary, if available
- Step 3:
  - merge mode
  - duplicates removed
  - groups merged
  - recovered data points
- Step 4:
  - kept / deleted feature count
  - QC deleted count
  - MNAR kept count
  - deleted feature sheet enabled / disabled

**Important Step 2 rule:** Do not parse record internals here. The formatter is a presentation boundary, not a parser.

### Step 3: Run formatter tests

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/test_gui_step_summary.py -v --tb=short
```

Expected: PASS.

---

## Task 2: Add One Run Context / Latest Result Panel

**Files:**

- Modify: `src/ms_preprocessing/gui/layout.py`
- Modify: `src/ms_preprocessing/gui/event_handlers.py`
- Test: `tests/test_gui_session_summary.py`
- Test: `tests/test_gui_event_handlers.py`

**Goal:** Add a compact, always-visible summary surface that combines current run context and latest step result.

The panel should show two sections:

- Run Context:
  - source file
  - current workflow step
  - completed steps
  - method file
  - ISTD record file and date
  - whether the loaded file came from combined TSV preprocessing
  - latest materialized output path
- Latest Result:
  - latest human-readable step summary from `summarize_step_result()`

### Step 1: Write failing tests for panel creation and updates

Create `tests/test_gui_session_summary.py`.

Expected assertions:

```python
def test_run_context_panel_exists(ctk_root) -> None:
    app = _ContentAreaHarness(ctk_root)
    app.pack(fill="both", expand=True)
    ctk_root.update_idletasks()
    try:
        assert hasattr(app, "run_context_frame")
        assert hasattr(app, "run_context_label")
        assert hasattr(app, "latest_result_label")
    finally:
        app.destroy()
```

Also add behavior tests for:

- source file load updates the context label
- combined TSV preprocessing updates the context label and latest output path
- `_on_step_complete()` updates latest result text
- Run All step completion also updates latest result text
- existing layout regression updates from the old two-row expectation to:
  - `content_frame` row 0 summary weight = 0
  - `content_frame` row 1 main step panel weight = 1
  - `content_frame` row 2 bottom log/action bar weight = 0

Expected: FAIL because the panel does not exist yet.

### Step 2: Add the panel layout

In `MainWindowLayoutMixin._create_content_area()`:

- Add one fixed-height panel above `main_frame`.
- Keep `main_frame` as the primary weighted content row.
- Keep bottom log/action bar unchanged.

Recommended layout:

```text
content_frame
  row 0: run_context_frame
  row 1: main_frame
  row 2: bottom_frame
```

The panel should use wrapping labels rather than a large text box so it does not feel like another log.

### Step 3: Add summary update helpers

In `event_handlers.py`, add helpers such as:

```python
def _update_run_context_summary(self) -> None:
    ...

def _update_latest_result_summary(self, lines: list[str]) -> None:
    ...
```

Read state defensively from:

- `_source_file`
- `_current_step`
- `_completed_steps`
- `_pipeline_session.context`
- `_last_materialized_export_path`
- Step 1 widget combined TSV state, if available

Do not add GUI display text or XIC-specific fields to `PipelineSession`.

### Step 4: Wire summaries into completion paths

Call `_update_run_context_summary()` after:

- GUI layout creation
- `_load_file_for_step()`
- `_run_combined_tsv_preprocessor()`
- `_on_step_complete()`
- `_run_all_steps_worker()` step completion
- `_export_results()`

For single-step completion:

- Use `widget.get_processing_result()`
- Use `widget.get_metadata()`
- Use `widget.get_last_parameters()`
- Pass the values to `summarize_step_result()`

For Run All:

- Generate a summary after each step in `_run_all_steps_worker()`.
- Keep only the latest step summary visible.
- Continue logging each step summary to the execution log for traceability.

### Step 5: Run focused tests

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/test_gui_session_summary.py tests/test_gui_event_handlers.py tests/test_gui_main_window_sidebar_labels.py -v --tb=short
```

Expected: PASS.

---

## Task 3: Add Run All Preset Preview

**Files:**

- Modify: `src/ms_preprocessing/gui/layout.py`
- Modify: `src/ms_preprocessing/gui/event_handlers.py`
- Modify: `src/ms_preprocessing/config/pipeline_profiles.py`
- Test: `tests/test_gui_main_window_sidebar_labels.py`
- Test: `tests/test_gui_event_handlers.py`
- Test: `tests/test_pipeline_profiles.py`

**Goal:** Make `loose/default/strict` meaningful before the user clicks Run All.

The preview should show:

- Step 1-3 are fixed defaults.
- Step 4 signal threshold.
- Step 4 background threshold.
- Step 4 MNAR high / low.
- Step 4 QC_ratio threshold.
- Intensity FC gate is off by default.

### Step 1: Write failing log-preview test

Add assertions that:

- `run_all_profile_preview_label` does not exist.
- Startup or preset selection logs `Preset parameters:`.
- Default preview log mentions `QC_ratio`.
- Default preview log mentions `Intensity FC: off`.
- Each preview line is logged as its own timestamped log entry.

Expected: FAIL.

### Step 2: Implement log-only preview

Do not add another persistent sidebar label. Log the selected Run All preset as
one header line followed by one log entry per preview line. This keeps the
sidebar stable and avoids the left action area shifting when preset copy changes.

### Step 3: Add preview formatter

Add `format_pipeline_profile_preview(name: str) -> str` in `pipeline_profiles.py`.

Use `get_pipeline_profile(name)` as the single source of truth so the preview cannot drift from the actual Run All parameters.

Do not use `PRESET_DESCRIPTIONS` from `feature_filter_presets.py` as the preview source because those descriptions mention the intensity FC threshold value even when `enable_intensity_fc_threshold` is `False`.

Expected preview content should include:

- `Step 1-3: fixed defaults`
- `Signal: 5000`
- `Background: 0.33` or selected preset value
- `MNAR: 0.80 / 0.20`
- `QC_ratio: 0.25` or selected preset value
- `Intensity FC: off`

### Step 4: Log preview on startup and preset selection

In `_apply_pipeline_profile_to_widgets()`, emit the preview when the profile is applied with logging enabled.

### Step 5: Run focused tests

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/test_gui_main_window_sidebar_labels.py tests/test_gui_event_handlers.py tests/test_pipeline_profiles.py -v --tb=short
```

Expected: PASS.

---

## Task 4: Add Shared Warning-Level Parameter Guardrails

**Files:**

- Create: `src/ms_preprocessing/gui/validation.py`
- Modify: `src/ms_preprocessing/gui/widgets/data_organizer_widget.py`
- Modify: `src/ms_preprocessing/gui/widgets/istd_marker_widget.py`
- Modify: `src/ms_preprocessing/gui/widgets/feature_filter_widget.py`
- Modify: `src/ms_preprocessing/gui/widgets/base_widget.py`
- Modify: `src/ms_preprocessing/gui/event_handlers.py`
- Test: `tests/test_gui_validation.py`
- Test: `tests/test_feature_filter_widget.py`
- Test: `tests/test_istd_marker_widget.py`
- Test: `tests/test_data_organizer_widget.py`
- Test: `tests/test_gui_event_handlers.py`

**Goal:** Prevent common expert mistakes without hiding expert controls.

Guardrails:

- Step 4 `high_det_thresh <= low_det_thresh`.
- Default-on Step 4 gates disabled by the user.
- Method file path does not exist.
- ISTD date is present but not `YYYYMMDD`.
- Raw combined TSV is sent through normal Step 1.

### Step 1: Write validation helper tests

Create `tests/test_gui_validation.py`.

Suggested API:

```python
@dataclass(frozen=True)
class ValidationWarning:
    code: str
    message: str
    blocking: bool = False
```

Validation helpers:

```python
validate_step1_params(params: dict) -> list[ValidationWarning]
validate_step2_params(params: dict) -> list[ValidationWarning]
validate_step4_params(params: dict) -> list[ValidationWarning]
```

Expected:

- Invalid Step 2 date returns blocking warning.
- `high_det_thresh <= low_det_thresh` returns blocking warning.
- Disabling default-on Step 4 gates returns non-blocking warning.

### Step 2: Implement `validation.py`

Keep validators independent from widgets.

Use `Path.exists()` only for fields that are present and non-empty.

Do not validate Step 2 ISTD record internals.

### Step 3: Add a shared validation execution path

Single-step and Run All must use the same validation logic.

Create a shared helper in `validation.py` or `base_widget.py` that separates:

- collecting validation warnings
- deciding whether any warning is blocking
- formatting warning text for logs/dialogs

For single-step:

- In `BaseProcessingWidget._on_run_clicked()`, if the widget exposes `validate_parameters(params)`, call it before starting the worker.
- Extract confirmation into a monkeypatch-friendly method such as `_confirm_validation_warnings(warnings)`.
- Blocking warnings stop before `_set_processing_state(True)`.

For Run All:

- In `_run_all_steps()`, after `params_by_step` is collected and before `_set_pipeline_busy_state(True)`, validate all steps on the UI thread.
- Aggregate blocking warnings across steps and stop before creating `_pipeline_worker_thread`.
- Aggregate non-blocking warnings and ask for confirmation once before creating `_pipeline_worker_thread`.
- Do not rely on `BaseProcessingWidget._on_run_clicked()` for Run All because Run All does not go through the normal button-click path.
- Do not open confirmation dialogs from `_run_all_steps_worker()` because it runs in a background worker when UI scheduling is available.

Blocking warnings:

- stop execution
- log/show a clear message

Non-blocking warnings:

- ask for confirmation or log loudly before continuing
- keep confirmation monkeypatch-friendly for tests

### Step 4: Preserve existing Step 4 data-dependent confirmations

`FeatureFilterWidget` already has data-dependent confirmations for single-group stable gate and small biological groups.

Keep those confirmations, but make the order explicit:

1. collect parameters
2. run blocking parameter validation
3. only if parameter validation passes, run single-group / small-N confirmations
4. start the worker

This avoids asking the user to confirm small-N or single-group behavior before later rejecting the run because of an invalid high/low threshold.

For Run All, do not attempt to run data-dependent Tk dialogs inside `_run_all_steps_worker()`. If Run All needs equivalent data-dependent Step 4 confirmation in this pass, evaluate it before worker startup using the original input data and collected Step 4 params. Otherwise, leave existing single-step data-dependent confirmations unchanged and document that Run All guardrails in this task are parameter-level only.

### Step 5: Add validation methods to Step widgets

Add:

```python
def validate_parameters(self, params: dict) -> list[ValidationWarning]:
    ...
```

For:

- `DataOrganizerWidget`
- `ISTDMarkerWidget`
- `FeatureFilterWidget`

Step 3 can be skipped unless a clear guardrail is identified.

### Step 6: Improve raw combined TSV normal Step 1 message

Current behavior raises:

```text
Combined TSV 請先使用上方 Combined TSV 前處理產生 combined_fix 檔案。
```

Keep the rule, but make the message action-oriented:

```text
偵測到 raw combined TSV。請先在「Combined TSV 前處理」選擇 TSV 與方法檔，按「產生 combined_fix」，再用產出的 .xlsx 跑一般 Toolkit 流程。
```

### Step 7: Run focused tests

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/test_gui_validation.py tests/test_data_organizer_widget.py tests/test_istd_marker_widget.py tests/test_feature_filter_widget.py tests/test_gui_event_handlers.py -v --tb=short
```

Expected: PASS.

---

## Task 5: Final Verification

**Files:**

- No new files.

### Step 1: Run focused GUI tests

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/test_gui_session_summary.py tests/test_gui_step_summary.py tests/test_gui_validation.py tests/test_data_organizer_widget.py tests/test_istd_marker_widget.py tests/test_duplicate_remover_widget.py tests/test_feature_filter_widget.py tests/test_gui_event_handlers.py tests/test_gui_main_window_sidebar_labels.py tests/test_gui_pipeline_session.py tests/test_gui_workflow_labels.py -v --tb=short
```

Expected: PASS.

### Step 2: Run profile and preset tests

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/test_pipeline_profiles.py tests/test_feature_filter_presets.py tests/test_pipeline_baseline_contract.py -v --tb=short
```

Expected: PASS.

### Step 3: Optional full focused suite

If the above changed shared event handling or base widget behavior, run:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/ -v --tb=short -x
```

Expected: PASS or stop on first failure and investigate.

### Step 4: Manual GUI smoke check

Start the GUI:

```powershell
$env:PYTHONPATH='ms-core/src'
python main.py
```

Manual checks:

- App starts without traceback.
- Run Context / Latest Result panel is visible at startup.
- Loading a normal `.xlsx` updates source file.
- Combined TSV preprocessing updates latest materialized output path.
- Selecting a Run All preset updates preview.
- Step 4 invalid high/low threshold warns before single-step run.
- Step 4 invalid high/low threshold warns before Run All.
- Step 2 invalid date warns before single-step run.
- Step 2 invalid date warns before Run All.
- Export button behavior is unchanged.
- At the current minimum practical window size, the panel does not crush the main step content or execution log.

---

## Rollback Plan

If GUI layout becomes unstable:

1. Keep `step_summary.py` and `validation.py` tests if they pass independently.
2. Revert only layout/event-handler surface changes.
3. Restore previous `content_frame` row structure.
4. Keep guardrails in widget-level tests for a narrower follow-up PR.

If Step 2 future ISTD work conflicts with this plan:

1. Do not modify widget layout first.
2. Extend adapter metadata/statistics.
3. Extend `step_summary.py` Step 2 formatter.
4. Keep `ISTDMarkerWidget` as a thin parameter form.

---

## Suggested PR Breakdown

Recommended sequence:

1. `feat(gui): add step result summary formatter`
2. `feat(gui): add run context summary panel`
3. `feat(gui): preview run all preset parameters`
4. `fix(gui): add shared parameter guardrails`

Avoid combining all tasks into one large PR unless the branch stays easy to review.
