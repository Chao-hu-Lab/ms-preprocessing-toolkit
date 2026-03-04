# Step4 Zero-Impute + Pipeline Performance Design

Date: 2026-03-04
Status: Implemented
Scope:
- Make Step 4 imputation treat `0` as missing by default (no toggle).
- Accelerate end-to-end workflow (read, compute, write) with default-on parquet cache strategy.

## 1. Goals

Functional goals:
- In Step 4, treat both `NaN` and `0` as missing values for imputation.
- Apply this rule to all sample intensity columns, including QC columns.
- Keep existing fill-value logic (group min positive / 2, with existing special-case threshold rule).

Performance goals:
- Reduce repeated large `.xlsx` I/O cost in multi-step processing.
- Keep user-facing behavior simple: default fast path without extra parameters.
- Preserve final Excel export compatibility for downstream users.

Non-goals:
- No user-facing switch to restore legacy "zero is valid observed value" imputation behavior.
- No algorithmic rewrite of Step 1-3 scientific logic.
- No change to `deleted_feature` sheet semantics.

## 2. Current State and Bottlenecks

Observed from project behavior and profiling on large files:
- Main bottleneck is Excel I/O (`openpyxl` read/write), not Step 4 vectorized math.
- Parquet cache infrastructure exists, but default cache flag is off, so most runs still use Excel path.
- Step 4 imputation currently only uses `np.isnan(...)` masks, so `0` is not imputed.

Impact:
- Large datasets show `cells_imputed = 0` when data uses `0` placeholders instead of `NaN`.
- Repeated step-to-step Excel saves/loads cause long runtime in GUI and CLI workflows.

## 3. Proposed Design

### 3.1 Dataflow and Performance Strategy (Default On)

Design:
- Enable parquet cache by default in settings (`SAVE_PARQUET_CACHE = True`).
- Keep final outputs as `.xlsx` for user deliverables.
- Use parquet cache for internal reload paths whenever cache is valid/newer.

Behavior by workflow:
- GUI single-step / run-all:
  - Continue producing expected step outputs.
  - Internal subsequent reads preferentially use parquet cache to avoid repeated Excel parsing.
- CLI:
  - Keep command behavior and output file contract.
  - Use cache for faster reloads in repeated runs on the same input/output path.

Compatibility:
- If parquet cache missing/invalid, fall back to Excel path automatically.
- Formatting metadata continues to be tracked via sidecar metadata path.

### 3.2 Step 4 Imputation Rule Change

Current:
- Missing mask = `isnan(value)` only.

New:
- Missing mask = `isnan(value) OR value == 0`.
- Apply to:
  - Group sample columns
  - QC columns

Fill values:
- Keep existing formulas:
  - General: row-wise positive minimum / 2
  - Existing special case: `signal_threshold`

Statistics:
- Keep existing `cells_imputed` (total).
- Add:
  - `cells_imputed_from_nan`
  - `cells_imputed_from_zero`
- Keep `imputed_cells` coordinates for blue-font marking (both sources included).

### 3.3 Sheet Semantics

- `RawIntensity`: contains post-filter, post-imputation data.
- `deleted_feature`: remains an audit sheet of removed rows and is not imputed by Step 4.
- This avoids mixing "output for downstream analysis" with "removed-feature trace".

## 4. Error Handling and Fallbacks

- If parquet write fails:
  - Log warning, continue with Excel output (non-fatal).
- If parquet read fails or metadata mismatch:
  - Fallback to Excel read.
- If dataset has duplicate column labels and cache cannot be safely written:
  - Keep existing guard behavior and continue without cache.
- If imputation encounters rows without positive values:
  - Use positive fallback (`signal_threshold / 2`) instead of keeping `0`.

## 5. Testing and Verification Plan

### 5.1 Unit/Behavioral tests

Add/adjust Step 4 tests to cover:
- `0` in group columns gets imputed.
- `0` in QC columns gets imputed.
- Mixed `NaN` + `0` both counted and imputed.
- Stats contain:
  - `cells_imputed`
  - `cells_imputed_from_nan`
  - `cells_imputed_from_zero`

### 5.2 Regression case (user-provided dataset)

Input:
- `OUTPUT/STEP3_VERIFY_STEP1_drLiao_HNC_Urine_recheck_20260303_142706.xlsx`
- Thresholds: `bg=0.5`, `skew=0.66`, `diff=0.5`, `qc_ratio=0.4`

Expected:
- Post-Step4 target intensity columns contain no `NaN` and no `0`.
- `cells_imputed_from_zero > 0`.
- Scientific filtering stats remain consistent except for expected imputation-related deltas.

### 5.3 Performance checks

Measure before/after wall-clock for:
- First run (cold cache)
- Second run (warm cache)

Track separately:
- Load time
- Step 4 compute time
- Save time

Acceptance:
- Warm-cache rerun shows meaningful speedup versus current baseline.
- No regression in output structure and required sheets.

## 6. Rollout Notes

- This is a behavior-changing default for imputation semantics.
- Communicate in release notes:
  - "`0` is now treated as missing in Step 4 by default."
  - "Parquet cache now enabled by default to improve performance."

## 7. Open Risks

- Some legacy analyses may have intended `0` as true observed values; this is now intentionally overridden by product decision.
- Large Excel final export can still dominate total runtime for very large files; cache mostly improves repeated processing and intermediate reloads.

## 8. Decision Summary

Approved decisions:
- Use mixed performance strategy (default-on parquet cache, keep Excel deliverables).
- Step 4 treats `0` as missing for all relevant columns (including QC).
- No opt-out toggle for legacy behavior.

## 9. Implementation Results Appendix (2026-03-04)

Implemented outcomes:
- Step 4 imputation now uses missing mask: `isnan OR == 0` for group and QC blocks.
- Imputation statistics now include:
  - `cells_imputed_from_nan`
  - `cells_imputed_from_zero`
- For rows with no positive values in an imputation block, fallback fill is now positive (`signal_threshold / 2`) to avoid residual zero placeholders.
- GUI step auto-save behavior now uses:
  - Step 1-3: `.parquet`
  - Step 4: `.xlsx`
- Parquet cache default is enabled (`SAVE_PARQUET_CACHE = True`).

User dataset verification (`STEP3_VERIFY_STEP1_drLiao_HNC_Urine_recheck_20260303_142706.xlsx`, thresholds `bg=0.5/skew=0.66/diff=0.5/qc=0.4`):
- `cells_imputed_from_zero = 1267825`
- `post_zero_count = 0`
- `post_nan_count = 0`
- Warm-cache load format: `parquet`
- Warm-cache speedup (cold load vs warm load): `216.669497x` on benchmark run.
