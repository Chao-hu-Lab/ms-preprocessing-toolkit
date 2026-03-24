# Step4 Zero-Missing + Pipeline Performance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Step 4 treat `0` as missing (including QC), and speed up the end-to-end workflow by defaulting to parquet-backed intermediate flow while preserving final Excel deliverables.

**Architecture:** Change imputation masks in the Step 4 core processor to include zeros, extend imputation stats for traceability, then reduce repeated Excel I/O by using parquet for intermediate outputs and default-on cache behavior. Keep final exported artifact as `.xlsx` with formatting metadata.

**Tech Stack:** Python 3.14, pandas, numpy, openpyxl, pytest, customtkinter, ms-core + ms-preprocessing-toolkit.

---

## Preconditions

1. Work in two repos with clear roots:
- Toolkit root: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit`
- Core root: `C:/Users/user/Desktop/質譜數據工具箱/ms-core`
2. Run tests from toolkit root unless task explicitly says ms-core root.
3. Apply `@superpowers:test-driven-development` for every behavior change task.
4. Use `@superpowers:verification-before-completion` before closing each task.

### Task 1: Add Failing Tests for Zero-As-Missing Imputation

**Files:**
- Modify: `tests/test_feature_filter.py`
- Test: `tests/test_feature_filter.py`

**Step 1: Write failing tests**

```python
def test_imputation_treats_zero_as_missing_for_group_columns(filter_proc):
    df = pd.DataFrame(
        {
            "Mz/RT": ["Sample_Type", "100.0/1.0"],
            "Tolerance": ["na", "na"],
            "Case1": ["case", 0],
            "Case2": ["case", 8000],
            "Control1": ["control", 0],
            "Control2": ["control", 9000],
            "QC1": ["qc", 7000],
        }
    )
    result = filter_proc.process(df, qc_ratio_threshold=0.0)
    assert result.success
    out = result.data
    assert float(out.loc[1, "Case1"]) > 0
    assert float(out.loc[1, "Control1"]) > 0
```

```python
def test_imputation_treats_zero_as_missing_for_qc_columns(filter_proc):
    df = pd.DataFrame(
        {
            "Mz/RT": ["Sample_Type", "100.0/1.0"],
            "Tolerance": ["na", "na"],
            "Case1": ["case", 8000],
            "Case2": ["case", 8500],
            "Control1": ["control", 9000],
            "QC1": ["qc", 0],
            "QC2": ["qc", 6000],
        }
    )
    result = filter_proc.process(df, qc_ratio_threshold=0.0)
    assert result.success
    out = result.data
    assert float(out.loc[1, "QC1"]) > 0
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_feature_filter.py -k "zero_as_missing or treats_zero_as_missing" -v`
Expected: FAIL (current behavior leaves zero unchanged).

**Step 3: Commit failing tests**

```bash
git add tests/test_feature_filter.py
git commit -m "test: add failing tests for zero-as-missing imputation"
```

### Task 2: Implement Zero-As-Missing in Step 4 Core

**Files:**
- Modify: `../ms-core/src/ms_core/preprocessing/ms_quality_filter.py`
- Optional mirror update to avoid drift: `src/ms_preprocessing/core/feature_filter.py`
- Test: `tests/test_feature_filter.py`

**Step 1: Implement minimal code change (groups)**

```python
nan_mask = np.isnan(block)
zero_mask = (block == 0)
missing_mask = nan_mask | zero_mask
```

**Step 2: Implement minimal code change (QC)**

```python
nan_mask = np.isnan(block)
zero_mask = (block == 0)
missing_mask = nan_mask | zero_mask
```

**Step 3: Track split stats**

```python
stats = {
    "cells_imputed": 0,
    "cells_imputed_from_nan": 0,
    "cells_imputed_from_zero": 0,
    "imputation_method": "group_min_half",
}
```

Update counters by mask source before overwrite.

**Step 4: Run targeted tests**

Run: `pytest tests/test_feature_filter.py -k "imputation or zero_as_missing or treats_zero_as_missing" -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add ../ms-core/src/ms_core/preprocessing/ms_quality_filter.py src/ms_preprocessing/core/feature_filter.py tests/test_feature_filter.py
git commit -m "feat: treat zero values as missing in Step4 imputation"
```

### Task 3: Validate Stats and Backward-Compatible Fields

**Files:**
- Modify: `tests/test_feature_filter.py`
- Test: `tests/test_feature_filter.py`

**Step 1: Add stats assertions**

```python
assert "cells_imputed" in result.statistics
assert "cells_imputed_from_nan" in result.statistics
assert "cells_imputed_from_zero" in result.statistics
assert result.statistics["cells_imputed"] == (
    result.statistics["cells_imputed_from_nan"] + result.statistics["cells_imputed_from_zero"]
)
```

**Step 2: Run test**

Run: `pytest tests/test_feature_filter.py -k "stats" -v`
Expected: PASS.

**Step 3: Commit**

```bash
git add tests/test_feature_filter.py
git commit -m "test: verify Step4 imputation stats split and total consistency"
```

### Task 4: Default Parquet Cache to On

**Files:**
- Modify: `../ms-core/src/ms_core/preprocessing/settings.py`
- Optional mirror update: `src/ms_preprocessing/config/settings.py`
- Test: `tests/test_smoke_guardrails.py` (add setting assertion)

**Step 1: Add failing smoke assertion**

```python
from ms_core.preprocessing.settings import Settings

def test_parquet_cache_default_enabled():
    assert Settings.SAVE_PARQUET_CACHE is True
```

**Step 2: Run failing test**

Run: `pytest tests/test_smoke_guardrails.py -k parquet -v`
Expected: FAIL (currently False).

**Step 3: Flip default**

```python
SAVE_PARQUET_CACHE = True
```

**Step 4: Re-run smoke test**

Run: `pytest tests/test_smoke_guardrails.py -k parquet -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add ../ms-core/src/ms_core/preprocessing/settings.py src/ms_preprocessing/config/settings.py tests/test_smoke_guardrails.py
git commit -m "feat: enable parquet cache by default"
```

### Task 5: Switch GUI Intermediate Auto-Save to Parquet

**Files:**
- Modify: `src/ms_preprocessing/gui/main_window.py`
- Test: `tests/test_regressions.py` (or new `tests/test_main_window_flow.py` for save-path behavior)

**Step 1: Add failing test for step output extension behavior**

```python
def test_intermediate_steps_autosave_as_parquet(...):
    # Arrange: step_index in {0,1,2}
    # Act: call _save_step_output(step_index, data)
    # Assert: returned path suffix == ".parquet"
```

```python
def test_step4_autosave_keeps_excel(...):
    # Arrange: step_index == 3
    # Assert: returned path suffix == ".xlsx"
```

**Step 2: Run tests to verify fail**

Run: `pytest tests/test_regressions.py -k "autosave_as_parquet or step4_autosave" -v`
Expected: FAIL.

**Step 3: Implement minimal logic**

Suggested implementation:
- In `_save_step_output`, choose extension by step:
  - step 0-2 -> `.parquet`
  - step 3 -> `.xlsx`
- Keep `extra_sheets` write only for `.xlsx` path.
- Keep existing logs and `_step_output_paths` updates.

**Step 4: Run tests**

Run: `pytest tests/test_regressions.py -k "autosave_as_parquet or step4_autosave" -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/ms_preprocessing/gui/main_window.py tests/test_regressions.py
git commit -m "perf: save intermediate GUI step outputs as parquet"
```

### Task 6: User Dataset Verification and Performance Baseline

**Files:**
- Create: `tests/test_step4_user_dataset_verification.py` (optional integration marker)
- Create: `scripts/benchmark_step4_io.py`

**Step 1: Add benchmark script**

Include:
- Input path argument
- Threshold args (`--bg`, `--skew`, `--diff`, `--qc`)
- Timers for load / process / save
- Counts for post-Step4 NaN/zero in imputation target columns

**Step 2: Run benchmark on provided dataset**

Run:
`python scripts/benchmark_step4_io.py --input OUTPUT/STEP3_VERIFY_STEP1_validation_dataset.xlsx --bg 0.5 --skew 0.66 --diff 0.5 --qc 0.4`

Expected:
- `cells_imputed_from_zero > 0`
- `post_zero_count == 0` for target columns
- measurable warm-cache speedup.

**Step 3: Commit**

```bash
git add scripts/benchmark_step4_io.py tests/test_step4_user_dataset_verification.py
git commit -m "test: add user-dataset verification and io benchmark script"
```

### Task 7: Documentation Update

**Files:**
- Modify: `README.md`
- Modify: `docs/plans/2026-03-04-step4-zero-impute-and-performance-design.md` (status/results appendix)

**Step 1: Update README behavior notes**

Add concise notes:
- Step 4 now treats zero as missing for imputation.
- Intermediate processing prefers parquet cache by default.
- Final outputs remain `.xlsx`.

**Step 2: Verify docs build/readability**

Run: `rg -n "zero as missing|parquet|Step 4" README.md docs/plans/*.md`
Expected: updated entries found.

**Step 3: Commit**

```bash
git add README.md docs/plans/2026-03-04-step4-zero-impute-and-performance-design.md
git commit -m "docs: document zero-imputation default and parquet-first intermediate flow"
```

## Final Verification Checklist

Run full suite relevant to touched areas:

1. `pytest tests/test_feature_filter.py -v`
2. `pytest tests/test_regressions.py -v`
3. `pytest tests/test_smoke_guardrails.py -v`
4. User dataset benchmark command from Task 6

Expected:
- All tests pass.
- User dataset verification confirms zeros are imputed in Step 4 target columns.
- Runtime improvement observed for repeated runs due default cache/intermediate parquet flow.
