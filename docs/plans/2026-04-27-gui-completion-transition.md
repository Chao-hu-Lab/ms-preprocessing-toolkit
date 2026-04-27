# GUI Completion Transition Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Remove the visible tearing during manual `Run Step` completion by making step completion render as one coherent transition instead of a chain of intermediate UI states.

**Architecture:** Treat manual step completion as a small transaction: commit workflow state, prepare the next step from in-memory data, switch the visible page, then run non-visual side effects. Forced repaint and autosave must not happen before the visual transition.

**Tech Stack:** Python, CustomTkinter, pandas, pytest, existing `MainWindowEventHandlersMixin`, `BaseProcessingWidget`, `PipelineSession`, and `FileHandler` patterns.

---

## Review Status

This plan supersedes the earlier animation/layout-only fixes for the Step 1 to Step 2 tearing issue.

The engineering review found that the tearing is not primarily caused by Step 2 being constructed late. All step widgets are already constructed during startup and stacked in the same grid cell. The stronger cause is that completion currently paints several intermediate states before the next step is shown.

---

## Problem Statement

Manual Step 1 completion currently performs UI and I/O work in this order:

```text
worker finishes
  |
  v
BaseProcessingWidget._finish_processing()
  |
  +--> update_progress(100, "Complete!")
  |       |
  |       +--> BaseProcessingWidget._emit_progress()
  |               |
  |               +--> update_idletasks()  <-- forced repaint while still on Step 1
  |
  +--> log completion/perf
  +--> restore shared controls
  +--> MainWindow._on_step_complete()
          |
          +--> update latest result summary
          +--> save step output synchronously
          +--> set Step 2 data/context/input path
          +--> update status
          +--> switch to Step 2
```

This creates visible intermediate states:

- Step 1 briefly repaints as complete.
- Buttons can re-enable before the page transition is done.
- Synchronous autosave can block the UI thread before Step 2 is visible.
- Log and summary writes happen during the same visual transition.

The result feels like page tearing or flicker, especially when Step 1 is tall and Step 2 is shorter.

---

## Target Flow

```text
worker finishes
  |
  v
BaseProcessingWidget._finish_processing()
  |
  +--> record final result/progress status without forced repaint
  +--> mark widget internally idle so busy guards are accurate
  +--> MainWindow._on_step_complete()
          |
          +--> commit session/context/completed step state
          +--> set next step in-memory data/context
          +--> switch visible page
          +--> restore controls
          +--> update summaries/logs/run context
          +--> schedule step-output autosave in background
                  |
                  +--> on save complete: update cached path and optional next-step input path
```

The user should see one state change:

```text
Step 1 running -> Step 2 ready
```

Not:

```text
Step 1 running -> Step 1 complete -> buttons flash -> save stalls -> Step 2 ready
```

---

## In Scope

- Remove forced repaint from normal progress updates.
- Prevent shared controls from visually restoring before parent completion finishes.
- Split manual step completion into visual transition and post-transition side effects.
- Move manual step autosave out of the pre-switch UI path.
- Preserve in-memory step chaining so Step 2 can run even if autosave is still pending.
- Add regression tests for ordering, not just final state.

## Out Of Scope

- Animation or fade transitions: this would hide symptoms while the UI thread can still be blocked.
- Replacing CustomTkinter or rewriting the GUI framework.
- Changing `ms-core` scientific processing logic.
- Changing Run All processing architecture unless tests reveal shared helper regressions.
- Changing final export behavior beyond keeping it compatible with deferred autosave.

---

## Existing Code To Reuse

- `MainWindowEventHandlersMixin._dispatch_to_ui()` already provides a UI-thread handoff for background worker callbacks.
- `MainWindowEventHandlersMixin._safe_update_action_bar_progress()` already wraps progress updates defensively.
- `PipelineSession.save_step_output()` currently owns step intermediate persistence, but it also mutates `step_output_paths`; background autosave must either keep using it on the UI thread through `after_idle`, or split its pure file-write behavior from its UI/session state mutation.
- Step widgets already accept in-memory data through `set_data()`, so step chaining does not need cached parquet paths to proceed.
- `_show_step()` already stacks all step widgets and uses `tkraise()`, so the plan should not add another page-switching abstraction.

---

## Failure Modes To Cover

| Failure Mode | User Impact | Test / Handling Needed |
| --- | --- | --- |
| `update_idletasks()` fires before `_on_step_complete()` switches page | visible Step 1 complete flash | test `BaseProcessingWidget._finish_processing()` does not call `update_idletasks()` before completion callback |
| `_save_step_output()` runs before `_switch_step()` | UI freezes before Step 2 appears | test manual completion switches before scheduling autosave |
| autosave fails after user is already on Step 2 | user can continue but cache path is missing | log clear warning, keep in-memory data active |
| user clicks Run Step 2 before autosave finishes | should still run from memory | keep `set_data()` as the source of truth for chaining |
| final Step 4 export needs a path while autosave is pending | export may use stale path | final export should use `_current_data`; if `_current_data` is missing, report a direct export failure |
| async autosave finishes after a new source file is loaded | stale cache path could overwrite new session state | tag autosave with session object/source token and ignore stale completion |
| background autosave mutates `PipelineSession` directly | cross-thread session state corruption or stale path registration | worker writes files only; UI thread records session paths after token check |
| deferred save observes mutated result data | saved intermediate differs from the completed step result | define result DataFrame as immutable after handoff, or snapshot deeply before worker write |

---

## Task 1: Lock Down Progress Repaint Behavior

**Files:**
- Modify: `tests/test_feature_filter_widget.py`
- Modify: `src/ms_preprocessing/gui/widgets/base_widget.py`

**Step 1: Write the failing test**

Add a focused test that progress emission updates progress callbacks but does not force `update_idletasks()`.

```python
def test_progress_update_does_not_force_immediate_repaint(widget) -> None:
    updates: list[tuple[float, str]] = []
    widget._on_progress = lambda value, status: updates.append((value, status))
    widget.update_idletasks = Mock()

    widget._emit_progress(100, "Complete!")

    assert updates == [(100.0, "Complete!")]
    widget.update_idletasks.assert_not_called()
```

**Step 2: Run the failing test**

Run:

```powershell
$env:PYTHONPATH='ms-core/src'; python -m pytest tests/test_feature_filter_widget.py::test_progress_update_does_not_force_immediate_repaint -v --tb=short
```

Expected before implementation: fail because `_emit_progress()` calls `update_idletasks()`.

**Step 3: Implement the minimal fix**

Remove this line from `BaseProcessingWidget._emit_progress()`:

```python
self.update_idletasks()
```

Do not replace it with another forced update. Let Tk's normal event loop repaint.

**Step 4: Verify**

Run:

```powershell
$env:PYTHONPATH='ms-core/src'; python -m pytest tests/test_feature_filter_widget.py::test_progress_update_does_not_force_immediate_repaint tests/test_feature_filter_widget.py::test_finish_processing_marks_widget_idle_before_completion_callback -v --tb=short
```

Expected: pass.

---

## Task 2: Keep Busy Guards Correct Without Early Visual Restore

**Files:**
- Modify: `tests/test_feature_filter_widget.py`
- Modify: `src/ms_preprocessing/gui/widgets/base_widget.py`

**Step 1: Write the failing test**

The completion callback must see `is_processing() == False`, but shared controls should not be re-enabled before the parent completion callback runs.

Use a fake shared button list so the test can observe when controls are configured:

```python
def test_finish_processing_marks_idle_before_callback_but_restores_controls_after(widget) -> None:
    events: list[str] = []
    control = Mock()
    control.configure.side_effect = lambda **kwargs: events.append(f"control:{kwargs['state']}")
    widget._iter_shared_action_buttons = lambda: [control]
    widget._on_progress = lambda _value, _status: None
    widget.on_log = lambda _message: None

    def on_complete(_result, _metadata):
        events.append(f"callback_busy:{widget.is_processing()}")

    widget.on_complete = on_complete
    widget._set_processing_state(True)
    events.clear()

    widget._finish_processing(pd.DataFrame({"S1": [1]}), None, "perf ok")

    assert events[0] == "callback_busy:False"
    assert events[-1] == "control:normal"
```

**Step 2: Run the failing test**

Run:

```powershell
$env:PYTHONPATH='ms-core/src'; python -m pytest tests/test_feature_filter_widget.py::test_finish_processing_marks_idle_before_callback_but_restores_controls_after -v --tb=short
```

Expected before implementation: fail if controls are restored before callback.

**Step 3: Implement the state split**

In `BaseProcessingWidget._finish_processing()` success path:

- Set `self._is_processing = False` before `on_complete` so busy guards work.
- Do not call `_set_processing_state(False)` until after `on_complete` returns.
- Keep the failure path restoring controls immediately in `finally`.

Expected structure:

```python
restore_controls = False

if error_message is None and result is not None:
    self._result = result
    self.update_progress(100, "Complete!")
    self.log("Processing completed successfully")
    self.log(perf_summary)
    self._is_processing = False
    restore_controls = True
    if self.on_complete:
        self.on_complete(result, self.get_metadata())
else:
    self._is_processing = False
    restore_controls = True
    # existing error logging path

finally:
    if restore_controls:
        self._set_processing_state(False)
    self._worker_thread = None
```

Rules:

- `on_complete` must observe `is_processing() == False`.
- Shared controls must not visually restore until `on_complete` returns.
- Do not use a vague `controls_are_still_disabled` condition. The restore decision must be explicit.
- If `_set_processing_state(False)` cannot be used after `_is_processing` has already been set to `False`, add a small helper such as `_restore_processing_controls()` and keep `_set_processing_state()` as the state-transition wrapper.
- Keep the implementation simple. If a helper is needed, name it for state ownership, not animation.

**Step 4: Verify**

Run:

```powershell
$env:PYTHONPATH='ms-core/src'; python -m pytest tests/test_feature_filter_widget.py -v --tb=short
```

Expected: pass.

---

## Task 3: Split Manual Step Completion Into Transition And Side Effects

**Files:**
- Modify: `tests/test_gui_event_handlers.py`
- Modify: `src/ms_preprocessing/gui/event_handlers.py`

**Step 1: Write the failing ordering test**

Manual Step 1 completion must switch to Step 2 before autosave is started.

```python
def test_manual_step_completion_switches_before_autosave(tmp_path) -> None:
    events: list[str] = []
    window = MainWindow.__new__(MainWindow)
    data = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.0/1.0"], "S1": ["case", 123]})
    current_widget = Mock()
    current_widget.get_last_parameters.return_value = {}
    current_widget.get_processing_result.return_value = None
    current_widget.get_metadata.return_value = {"statistics": {}}
    next_widget = Mock()
    next_widget.set_data.side_effect = lambda _data: events.append("next-data")

    window.step_widgets = [current_widget, next_widget]
    window._current_step = 0
    window._context = {}
    window._completed_steps = set()
    window._last_completed_step = None
    window._last_run_all = False
    window._step_output_paths = {}
    window._pipeline_session = PipelineSession(output_dir=tmp_path / "OUTPUT", source_file=tmp_path / "input.xlsx")
    window._update_export_dnp_btn = lambda: events.append("export-dnp")
    window._update_latest_result_summary = lambda _lines: events.append("summary")
    window._update_run_context_summary = lambda: events.append("context-summary")
    window._safe_update_action_bar_progress = lambda *_args: events.append("progress")
    window._log = lambda _message: events.append("log")
    window._switch_step = lambda step: events.append(f"switch:{step}")
    window._schedule_step_output_save = lambda *_args, **_kwargs: events.append("schedule-save")
    window._save_step_output = Mock(side_effect=AssertionError("sync save not allowed"))
    window._auto_export_final_results = Mock()

    window._on_step_complete(data, metadata={})

    assert events.index("next-data") < events.index("switch:1")
    assert events.index("switch:1") < events.index("schedule-save")
    assert events.index("switch:1") < events.index("summary")
    assert events.index("switch:1") < events.index("context-summary")
    window._save_step_output.assert_not_called()
    window._auto_export_final_results.assert_not_called()
```

**Step 2: Run the failing test**

Run:

```powershell
$env:PYTHONPATH='ms-core/src'; python -m pytest tests/test_gui_event_handlers.py::test_manual_step_completion_switches_before_autosave -v --tb=short
```

Expected before implementation: fail because current code calls `_save_step_output()` before `_switch_step()`.

**Step 3: Implement transition-first completion**

Refactor `_on_step_complete()` into explicit phases:

```python
step_index = self._current_step
next_step = step_index + 1

# Phase 1: commit workflow state
self._current_data = result_data
self._pipeline_session.record_step_parameters(step_index, current_widget.get_last_parameters())
...
self._completed_steps.add(step_index)
self._last_completed_step = step_index
self._last_run_all = False

# Phase 2: visual transition
if next_step < len(self.step_widgets):
    self.step_widgets[next_step].set_data(result_data)
    self.step_widgets[next_step].set_context(self._context)
    self._switch_step(next_step)
    self._safe_update_action_bar_progress(100, f"Step {step_index + 1} complete. Step {next_step + 1} ready.")

    # Phase 3: post-transition effects
    self._update_latest_result_summary(summary_lines)
    self._update_export_dnp_btn()
    self._schedule_step_output_save(step_index, result_data, next_step_index=next_step)
    return
```

Rules:

- Do not call `_save_step_output()` in the pre-switch path.
- Do not set the current widget input to its own output path.
- Step chaining must continue to use `set_data(result_data)`.
- The next step must receive `set_data(result_data)` before it becomes visible.
- `summary_lines` may be computed before switching, but configuring labels should happen after switching.
- Run context and result summary updates should happen after the visible step switch unless they are proven not to repaint visible widgets.

**Step 4: Verify**

Run:

```powershell
$env:PYTHONPATH='ms-core/src'; python -m pytest tests/test_gui_event_handlers.py::test_manual_step_completion_auto_advances_to_next_step tests/test_gui_event_handlers.py::test_manual_step_completion_switches_before_autosave -v --tb=short
```

Expected: pass.

---

## Task 4: Add Deferred Step Autosave

**Files:**
- Modify: `tests/test_gui_event_handlers.py`
- Modify: `src/ms_preprocessing/gui/event_handlers.py`
- Modify: `src/ms_preprocessing/gui/pipeline_session.py`
- Modify: `tests/test_gui_pipeline_session.py`

**Step 1: Write tests for deferred autosave completion**

Add a unit-level test for the completion callback, not a real thread timing test.

```python
def test_finish_deferred_step_output_save_updates_path_and_next_input(tmp_path) -> None:
    window = MainWindow.__new__(MainWindow)
    next_widget = Mock()
    path = tmp_path / "STEP1_input.parquet"
    window.step_widgets = [Mock(), next_widget]
    window._step_output_paths = {}
    window._pipeline_session = PipelineSession(output_dir=tmp_path / "OUTPUT", source_file=tmp_path / "input.xlsx")
    window._log = Mock()
    window._update_run_context_summary = Mock()

    window._finish_deferred_step_output_save(
        step_index=0,
        next_step_index=1,
        session_token=id(window._pipeline_session),
        path=path,
        error_message=None,
    )

    assert window._step_output_paths[0] == path
    next_widget.set_input_file.assert_called_once_with(str(path))
    window._update_run_context_summary.assert_called_once()
```

Add an error-path test:

```python
def test_finish_deferred_step_output_save_logs_error_without_clearing_memory_data(tmp_path) -> None:
    window = MainWindow.__new__(MainWindow)
    window.step_widgets = [Mock(), Mock()]
    window._step_output_paths = {}
    window._pipeline_session = PipelineSession(output_dir=tmp_path / "OUTPUT", source_file=tmp_path / "input.xlsx")
    logs: list[str] = []
    window._log = logs.append
    window._update_run_context_summary = Mock()

    window._finish_deferred_step_output_save(
        step_index=0,
        next_step_index=1,
        session_token=id(window._pipeline_session),
        path=None,
        error_message="disk full",
    )

    assert window._step_output_paths == {}
    assert any("Auto-save error" in message and "disk full" in message for message in logs)
```

Add a stale-session completion test:

```python
def test_finish_deferred_step_output_save_ignores_stale_session(tmp_path) -> None:
    window = MainWindow.__new__(MainWindow)
    window.step_widgets = [Mock(), Mock()]
    window._step_output_paths = {}
    window._pipeline_session = PipelineSession(output_dir=tmp_path / "OUTPUT", source_file=tmp_path / "new.xlsx")
    window._log = Mock()
    window._update_run_context_summary = Mock()

    window._finish_deferred_step_output_save(
        step_index=0,
        next_step_index=1,
        session_token=object(),
        path=tmp_path / "old.parquet",
        error_message=None,
    )

    assert window._step_output_paths == {}
    window.step_widgets[1].set_input_file.assert_not_called()
    window._update_run_context_summary.assert_not_called()
```

Add a `PipelineSession` unit test for the new path builder if one is extracted:

```python
def test_build_step_output_path_does_not_register_path(tmp_path) -> None:
    session = PipelineSession(output_dir=tmp_path / "OUTPUT", source_file=tmp_path / "input.xlsx")

    path = session.build_step_output_path(0)

    assert path.parent == session.intermediate_dir
    assert path.name.startswith("STEP1_input_")
    assert session.step_output_paths == {}
```

**Step 2: Implement helper methods**

Add these helpers in `MainWindowEventHandlersMixin`:

```python
def _schedule_step_output_save(
    self,
    step_index: int,
    data: pd.DataFrame,
    *,
    next_step_index: int | None = None,
) -> None:
    ...

def _run_step_output_save_worker(
    self,
    step_index: int,
    data: pd.DataFrame,
    next_step_index: int | None,
    session_token: object,
    output_path: Path,
    formatting_context: dict[str, object],
) -> None:
    ...

def _finish_deferred_step_output_save(
    self,
    *,
    step_index: int,
    next_step_index: int | None,
    session_token: object,
    path: Path | None,
    error_message: str | None,
) -> None:
    ...
```

Implementation notes:

- Capture `session = self._pipeline_session`, `source_file = self._source_file`, and the metadata needed for formatting before starting the worker.
- Build the target output path on the UI thread before starting the worker. Prefer extracting `PipelineSession.build_step_output_path(step_index)` so naming stays centralized and path building does not register state.
- Do not call `PipelineSession.save_step_output()` from the worker unless it has first been refactored so the worker path does not mutate `step_output_paths`, `context`, or `metadata`.
- The worker may call `self._file_handler.save_data(...)` with captured immutable arguments, but all session/path registration must happen in `_finish_deferred_step_output_save()` on the UI thread.
- Use a session token, for example `id(self._pipeline_session)`, and ignore completion if the token no longer matches.
- Treat result data as immutable after step handoff. If any step implementation mutates the same DataFrame object after completion, replace `data.copy(deep=False)` with a safer snapshot for the deferred save path.
- Worker wraps only the file-write block in `try: ... except Exception as exc` and dispatches completion through `_dispatch_to_ui()`.
- Completion updates `_step_output_paths`, updates `self._pipeline_session.step_output_paths`, logs the saved path, updates run context, and optionally sets the next step input path if the next step still exists.

**Step 3: Preserve final-step behavior**

For final Step 4 manual completion:

- Keep `_current_data` as the export source of truth.
- Run `_auto_export_final_results()` from `_current_data` without waiting for intermediate autosave.
- Do not schedule Step 4 intermediate autosave before final export.
- If final export succeeds, skip Step 4 intermediate autosave unless a later test proves another consumer needs that parquet cache.
- If final export fails because `_current_data` is missing, report that as an export failure instead of waiting on a deferred cache path.

**Step 4: Verify**

Run:

```powershell
$env:PYTHONPATH='ms-core/src'; python -m pytest tests/test_gui_event_handlers.py -v --tb=short
```

Expected: pass.

---

## Task 5: Add Runtime Smoke For The Transition Contract

**Files:**
- Modify: `tests/test_gui_main_window_sidebar_labels.py` or create a new focused GUI smoke test file if this grows too large.

**Step 1: Add a smoke-style test**

The smoke test should instantiate `MainWindow`, simulate Step 1 completion, and assert:

- startup log contains the default preset details,
- current step becomes 1,
- visible step index becomes 1,
- Step 1 input is unchanged,
- Step 2 has in-memory data,
- deferred save can complete and then set Step 2 input path.

Keep this test lightweight. Do not create a large real Excel/parquet file.

**Step 2: Run focused GUI tests**

Run:

```powershell
$env:PYTHONPATH='ms-core/src'; python -m pytest tests/test_gui_event_handlers.py tests/test_gui_session_summary.py tests/test_gui_main_window_sidebar_labels.py tests/test_feature_filter_widget.py -v --tb=short
```

Expected: pass.

---

## Task 6: Verification

**Files:**
- No source changes unless previous tests reveal gaps.

**Step 1: Run GUI focused tests**

```powershell
$env:PYTHONPATH='ms-core/src'; python -m pytest tests/test_gui_event_handlers.py tests/test_gui_session_summary.py tests/test_gui_main_window_sidebar_labels.py tests/test_data_organizer_widget.py tests/test_istd_marker_widget.py tests/test_feature_filter_widget.py -v --tb=short
```

Expected: all pass.

**Step 2: Run full top-level tests**

```powershell
$env:PYTHONPATH='ms-core/src'; python -m pytest tests -v --tb=short
```

Expected: all pass.

**Step 3: Run MainWindow smoke**

```powershell
$env:PYTHONPATH='ms-core/src;src'; python -c "from ms_preprocessing.gui.main_window import MainWindow; app=MainWindow(); app.withdraw(); app.update_idletasks(); print(app.log_text.get('1.0','end')[:200]); app.destroy()"
```

Expected:

- app starts,
- default preset parameters appear in the log,
- no exceptions.

**Step 4: Check whitespace**

```powershell
git diff --check
```

Expected: no whitespace errors. CRLF warnings are acceptable in this Windows worktree.

---

## Acceptance Criteria

- Manual Step 1 completion visually transitions directly to Step 2 without showing a forced Step 1 complete repaint.
- No completion-path `update_idletasks()` runs before `_on_step_complete()` has switched the visible step.
- Step 2 can run from in-memory data even if intermediate autosave is still pending.
- Intermediate autosave failure is visible in the log and does not invalidate the in-memory pipeline.
- Background autosave does not mutate `PipelineSession` outside the UI thread.
- Final export still works from `_current_data`.
- Startup log includes the default Run All preset details.
- No animation is introduced.
- Focused GUI tests and full top-level tests pass.

---

## Rollback Plan

If deferred autosave introduces instability:

1. Keep Task 1 and Task 2, because removing forced repaint and early visual restore are still valid.
2. Temporarily switch `_schedule_step_output_save()` to `after_idle` instead of a background thread.
3. Keep the transition-first ordering so the user sees Step 2 before any save work starts.
4. Re-run the GUI focused tests and document the remaining freeze risk.

---

## Notes For Implementation

- Do not add animation until the UI thread is no longer blocked.
- Do not route manual Step 1-3 completion through Run All worker code.
- Do not let deferred save completion mutate a newer session after a new file is loaded.
- Avoid broad cleanup in this pass. The target is completion transaction correctness.
