# Step 4 Threshold Toggle Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add independent on/off switches for all four Step 4 thresholds so users can choose which filtering rules are active without changing the default behavior.

**Architecture:** Extend the Step 4 widget with four boolean switches, disable each threshold input when its rule is off, and pass the booleans through `get_parameters()` into the processor. Update the core filter logic so each rule is only applied when its switch is enabled; when all switches are off, Step 4 still performs imputation but does not delete features because of threshold rules.

**Tech Stack:** Python, pandas, numpy, customtkinter, pytest

---

### Task 1: Add failing core tests for rule toggles

**Files:**
- Modify: `tests/test_feature_filter.py`

**Step 1: Write the failing test**

Add tests that disable each rule and assert the matching deletion behavior is skipped while other rules still work.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_feature_filter.py -k "disable" -v`
Expected: FAIL because the processor does not accept enable flags yet.

**Step 3: Write minimal implementation**

Add boolean processor parameters for the four rules and use them inside `_filter_features(...)`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_feature_filter.py -k "disable" -v`
Expected: PASS

### Task 2: Add failing GUI tests for Step 4 switches

**Files:**
- Create: `tests/test_feature_filter_widget.py`

**Step 1: Write the failing test**

Add tests that instantiate `FeatureFilterWidget`, confirm all switches default to on, and confirm `get_parameters()` returns the new booleans. Add a test that turns one switch off and verifies its slider/entry become disabled.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_feature_filter_widget.py -v`
Expected: FAIL because the widget does not expose the switches yet.

**Step 3: Write minimal implementation**

Add four `CTkSwitch` controls, state synchronization helpers, and parameter export wiring.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_feature_filter_widget.py -v`
Expected: PASS

### Task 3: Implement the Step 4 GUI toggle behavior

**Files:**
- Modify: `src/ms_preprocessing/gui/widgets/feature_filter_widget.py`

**Step 1: Wire the widget**

Create switches for background, skew, diff, and QC ratio. Keep them enabled by default.

**Step 2: Add UI state sync**

When a rule is off, disable the matching slider and entry. When it is on, restore them to normal state.

**Step 3: Propagate parameters**

Return the four booleans from `get_parameters()` and preserve the current threshold values.

**Step 4: Run widget tests**

Run: `pytest tests/test_feature_filter_widget.py -v`
Expected: PASS

### Task 4: Implement processor rule gating

**Files:**
- Modify: `src/ms_preprocessing/core/feature_filter.py`

**Step 1: Extend API**

Accept `enable_background_threshold`, `enable_skew_threshold`, `enable_diff_threshold`, and `enable_qc_ratio_threshold` in `process(...)`.

**Step 2: Apply rule gating**

Only compute and enforce the matching keep/delete mask when the corresponding flag is enabled. Keep current default behavior by defaulting all flags to `True`.

**Step 3: Preserve stats and metadata**

Expose the enabled flags in metadata so the GUI session can remember what was applied.

**Step 4: Run core tests**

Run: `pytest tests/test_feature_filter.py -v`
Expected: PASS

### Task 5: Verify the integrated change

**Files:**
- Modify: `tests/test_gui_pipeline_session.py`
- Optional review: `src/ms_preprocessing/gui/pipeline_session.py`

**Step 1: Add/adjust session assertion**

Confirm Step 4 parameter snapshots can store the new boolean flags.

**Step 2: Run focused verification**

Run: `pytest tests/test_feature_filter.py tests/test_feature_filter_widget.py tests/test_gui_pipeline_session.py -v`
Expected: PASS
