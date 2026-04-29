# Step1 DataOrganizer Facade Slimming Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Slim `DataOrganizer` into a thin Step1 core facade while preserving the current Step1 output contract.

**Architecture:** Keep `DataOrganizer.process()` as the public orchestration entrypoint. Move raw matrix layout, normal/statistics shared preparation, and output assembly details into focused helpers without changing `ProcessingResult.data`, `statistics`, `metadata`, or SampleInfo naming behavior.

**Tech Stack:** Python, pandas, pytest, `ms-core` preprocessing modules, git submodule workflow.

---

## Ownership

Can modify:

- `ms-core/src/ms_core/preprocessing/data_organizer.py`
- new helper modules under `ms-core/src/ms_core/preprocessing/` only when they directly reduce `DataOrganizer` responsibility
- focused tests matching `ms-core/tests/test_data_organizer*.py`

Must not modify:

- top-level GUI, CLI, workflow, adapter, or marker files
- `src/ms_preprocessing/`
- calibration modules
- `CombinedTsvPreprocessor` behavior except existing delegation wrappers from `DataOrganizer`
- top-level submodule pointer until the `ms-core` work is committed and pushed

## Contract To Preserve

- `DataOrganizer.process()` remains the only public Step1 orchestration entrypoint.
- Existing public/compatibility methods remain callable unless a test proves they are unused private internals.
- `ProcessingResult.data`, `statistics`, `metadata["mode"]`, `metadata["header_mapping"]`, `metadata["sample_mapping"]`, and `metadata["sample_info"]` keep current shape and values.
- RawIntensity sample columns and `SampleInfo.Sample_Name` continue to match for rerun compatibility.
- `process_combined()`, `false_positive_fix()`, `post_vba_cleanup()`, and `process_combined_and_fix()` keep delegating to `CombinedTsvPreprocessor`.

## Implementation Sequence

### Task 1: Lock facade behavior before extraction

Write or extend focused tests for:

- normalization mode keeps current RawIntensity columns, Sample_Type row, statistics keys, and SampleInfo metadata
- statistics mode keeps separate Mz/RT output columns and current metadata
- input Sample Type row still overrides detected types
- existing SampleInfo naming tests still pass

Run:

```powershell
Push-Location ms-core
python -m pytest tests\test_data_organizer_sample_info_names.py tests\test_data_organizer_false_positive_fix.py -v --tb=short
Pop-Location
```

Expected before implementation: facade contract tests should pass against the current behavior. Helper-module tests may be RED only when they target newly introduced helper APIs that do not exist yet.

### Task 2: Extract raw matrix layout helpers

Move layout-only responsibilities out of the facade:

- pre-merged Mz/RT header detection
- pre-merged Mz/RT expansion
- leading metadata column relocation
- input Sample Type row extraction and sample type value normalization if doing so reduces duplicate normal/statistics code

Keep `DataOrganizer` wrapper methods when tests or downstream code call them directly.

### Task 3: Extract shared normal/statistics preparation

Remove duplicated preparation from `process()` and `_process_statistics_mode()`:

- validate after metadata relocation
- initialize base statistics
- parse method file and injection sequence
- merge explicit `sample_type_mapping`
- simplify headers and normalize input-provided sample type overrides

The helper should return a small explicit intermediate object rather than a loose dict when practical.
If a helper API is introduced, write its focused RED test before moving logic into that helper.

### Task 4: Extract output assembly

Move final structure assembly out of the facade:

- Sample_Type row insertion
- SampleInfo building call and `_col_name` cleanup
- injection-order column reorder
- final numeric conversion
- statistics-mode restoration of separate Mz and RT columns

Do not change output column order, row count, metadata keys, or statistics keys.

### Task 5: Keep combined TSV as delegation only

Do not rewrite combined TSV behavior in this branch. If touching combined wrappers, add a focused regression proving the wrappers still delegate and the existing combined TSV tests pass.

## Verification

Focused checks:

```powershell
Push-Location ms-core
python -m pytest tests\test_data_organizer_sample_info_names.py tests\test_data_organizer_false_positive_fix.py tests\test_sample_info_builder.py tests\test_method_sequence.py tests\test_sample_identity.py -v --tb=short -x
Pop-Location
```

Run combined TSV checks only if combined wrapper code changes:

```powershell
Push-Location ms-core
python -m pytest tests\test_combined_tsv_preprocessor.py -v --tb=short -x
Pop-Location
```

Final core check before handoff:

```powershell
Push-Location ms-core
python -m pytest tests\ -v --tb=short -x
Pop-Location
```

## Handoff

Report:

- helper modules created and why each one exists
- `DataOrganizer` methods left as compatibility wrappers
- confirmation that output contract tests passed
- any public method intentionally left in `data_organizer.py`
- whether `ms-core` branch was pushed and ready for a core PR
