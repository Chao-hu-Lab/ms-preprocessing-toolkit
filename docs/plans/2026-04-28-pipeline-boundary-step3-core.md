# Step3 Core Boundary Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Move degeneracy annotation and duplicate intensity merge policy out of `DuplicateRemover` while keeping Step3 behavior unchanged.

**Architecture:** `DuplicateRemover` remains the public Step3 facade. New modules own annotation and merge-policy details, and `DuplicateRemover` delegates through compatibility wrappers.

**Tech Stack:** Python, pandas, numpy, pytest, `ms-core`.

---

## Ownership

Can modify:

- `ms-core/src/ms_core/preprocessing/duplicate_remover.py`
- `ms-core/src/ms_core/preprocessing/degeneracy_annotation.py`
- `ms-core/src/ms_core/preprocessing/duplicate_intensity_merge.py`
- `ms-core/tests/test_degeneracy_annotation.py`
- `ms-core/tests/test_duplicate_intensity_merge.py`

Do not modify:

- Step4 modules
- top-level toolkit files
- GUI/CLI files
- submodule pointer
- `ms-core/tests/testing_markers.py`

## Task 1: Extract Degeneracy Annotation

Step 1: Write failing tests in `ms-core/tests/test_degeneracy_annotation.py`.

Required tests:

- annotates base and `[M+Na]+` adduct rows
- rejects low-correlation adduct-like pairs
- returns empty stats for empty input
- loads valid custom adduct table
- falls back to built-in table for missing or invalid custom table

Run:

```powershell
Push-Location ms-core
python -m pytest tests\test_degeneracy_annotation.py -v --tb=short
Pop-Location
```

Expected RED:

- `ModuleNotFoundError` for `ms_core.preprocessing.degeneracy_annotation`.

Step 2: Implement `ms-core/src/ms_core/preprocessing/degeneracy_annotation.py`.

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

Move these responsibilities:

- annotation column defaults
- adduct matching
- adduct table loading
- default adduct table
- correlation column selection
- Pearson correlation calculation

Step 3: Convert `DuplicateRemover._annotate_degeneracy()` to a thin wrapper.

Step 4: Verify:

```powershell
Push-Location ms-core
python -m pytest tests\test_degeneracy_annotation.py tests\test_pipeline.py -v --tb=short
Pop-Location
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\core\test_duplicate_remover.py tests\adapters\test_adapter_duplicate_remover.py -v --tb=short
```

## Task 2: Extract Duplicate Intensity Merge Policy

Step 1: Write failing tests in `ms-core/tests/test_duplicate_intensity_merge.py`.

Required tests:

- `per_sample_max` upgrades overlapping donor values
- `fill_gaps` preserves legacy overlap behavior
- zeros, blanks, and NaN are treated as missing
- merge stats report recovered and upgraded data points
- protected representatives can still receive per-sample upgrades

Run:

```powershell
Push-Location ms-core
python -m pytest tests\test_duplicate_intensity_merge.py -v --tb=short
Pop-Location
```

Expected RED:

- missing `duplicate_intensity_merge` module.

Step 2: Implement `ms-core/src/ms_core/preprocessing/duplicate_intensity_merge.py`.

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

Move:

- `MergeMode`
- merge mode normalization
- positive-value coercion
- duplicate group intensity merge policy

Step 3: Convert `DuplicateRemover._merge_duplicate_groups()` to a thin wrapper.

Step 4: Verify:

```powershell
Push-Location ms-core
python -m pytest tests\test_duplicate_intensity_merge.py tests\test_degeneracy_annotation.py tests\test_pipeline.py -v --tb=short
Pop-Location
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\core\test_duplicate_remover.py tests\adapters\test_adapter_duplicate_remover.py -v --tb=short
```

## Deliverable

Report:

- changed files
- RED and GREEN commands
- whether `DuplicateRemover.process()` output shape changed
- any wrapper methods left for compatibility
