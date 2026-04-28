# Step4 Core Boundary Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Move group detection, ratio calculation, filter decisions, and output shaping out of `FeatureFilter` while keeping Step4 behavior unchanged.

**Architecture:** `FeatureFilter` remains the public Step4 facade. New modules own pure calculations and output shaping, and `FeatureFilter` delegates through compatibility wrappers.

**Tech Stack:** Python, pandas, numpy, pytest, `ms-core`.

---

## Ownership

Can modify:

- `ms-core/src/ms_core/preprocessing/ms_quality_filter.py`
- `ms-core/src/ms_core/preprocessing/feature_groups.py`
- `ms-core/src/ms_core/preprocessing/detection_ratios.py`
- `ms-core/src/ms_core/preprocessing/feature_filter_decisions.py`
- `ms-core/src/ms_core/preprocessing/feature_filter_output.py`
- focused Step4 tests created by this plan

Do not modify:

- Step3 modules
- top-level toolkit files
- GUI/CLI files
- submodule pointer
- `ms-core/tests/testing_markers.py`

## Task 1: Extract Group Detection

Step 1: Write failing tests in `ms-core/tests/test_feature_groups.py`.

Required tests:

- detects analysis groups from `Sample_Type` row
- detects QC columns
- respects excluded types from config
- handles missing fixed columns consistently with current Step4
- supports `count_analysis_groups()` compatibility

Run:

```powershell
Push-Location ms-core
python -m pytest tests\test_feature_groups.py -v --tb=short
Pop-Location
```

Expected RED:

- missing `feature_groups` module.

Step 2: Implement `FeatureGroupDetector`.

Target interface:

```python
class FeatureGroupDetector:
    def detect(self, df: pd.DataFrame) -> dict[str, object]:
        ...
```

Step 3: Convert `FeatureFilter._detect_sample_types()` to a wrapper.

## Task 2: Extract Detection Ratios

Step 1: Write failing tests in `ms-core/tests/test_detection_ratios.py`.

Required tests:

- creates group ratio columns
- creates QC ratio column when QC exists
- omits QC ratio when QC does not exist
- returns numeric block with values, all columns, and column-position mapping
- preserves `Sample_Type` header row values as `"na"`

Run:

```powershell
Push-Location ms-core
python -m pytest tests\test_detection_ratios.py -v --tb=short
Pop-Location
```

Expected RED:

- missing `detection_ratios` module.

Step 2: Implement `DetectionRatioCalculator`.

Target interface:

```python
class DetectionRatioCalculator:
    def calculate(
        self,
        df: pd.DataFrame,
        group_info: dict[str, object],
    ) -> tuple[pd.DataFrame, dict[str, str], dict[str, object]]:
        ...
```

Step 3: Convert `FeatureFilter._calculate_ratios()` to a wrapper.

## Task 3: Extract Decision Table

Step 1: Write failing tests in `ms-core/tests/test_feature_filter_decisions.py`.

Required tests:

- Wilson lower bound for small-N groups
- stable gate
- MNAR high/low gate
- QC zero forced-delete gate
- QC low forced-delete gate
- intensity fold-change gate
- protected row override
- unique contribution stats

Run:

```powershell
Push-Location ms-core
python -m pytest tests\test_feature_filter_decisions.py -v --tb=short
Pop-Location
```

Expected RED:

- missing `feature_filter_decisions` module.

Step 2: Implement:

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
    def decide(self, ...) -> FeatureFilterDecisionResult:
        ...
```

Keep formulas identical to current `FeatureFilter._filter_features()`.

## Task 4: Extract Output Builder

Step 1: Write failing tests in `ms-core/tests/test_feature_filter_output.py`.

Required tests:

- zero-to-NaN touches only sample/QC data columns after the header row
- deleted features preserve expected row shape
- `is_Presence_Absence_Marker` column follows MNAR mask
- protected row remapping remains stable

Run:

```powershell
Push-Location ms-core
python -m pytest tests\test_feature_filter_output.py -v --tb=short
Pop-Location
```

Expected RED:

- missing `feature_filter_output` module.

Step 2: Implement `FeatureFilterOutputBuilder`.

Move these responsibilities:

- filtered dataframe construction
- deleted feature row collection
- protected row remapping
- `is_Presence_Absence_Marker` column construction
- zero-to-NaN conversion for sample/QC data columns
- output-shaping stats such as `zeros_converted_to_nan`

Step 3: Convert `FeatureFilter._filter_features()` to orchestrate decision table + output builder.

Step 4: Move the current zero-to-NaN block from `FeatureFilter.process()` into
`FeatureFilterOutputBuilder` so `FeatureFilter.process()` stays an orchestration
facade. Keep progress reporting in `process()`, but not the dataframe mutation
logic.

## Verification

```powershell
Push-Location ms-core
python -m pytest tests\test_feature_groups.py tests\test_detection_ratios.py tests\test_feature_filter_decisions.py tests\test_feature_filter_output.py tests\test_feature_filter_small_n.py tests\test_pipeline.py -v --tb=short
Pop-Location
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\core\test_feature_filter.py tests\adapters\test_adapter_feature_filter.py tests\test_feature_filter_widget.py tests\test_feature_filter_presets.py -v --tb=short
```

## Deliverable

Report:

- changed files
- RED and GREEN commands
- whether `FeatureFilter.process()` output shape changed
- wrapper methods left for compatibility
